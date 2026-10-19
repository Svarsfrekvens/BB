"""Invented source rows exercise profile binding, solver and independent checks."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from availability_fixtures import sample
from bb.availability import solve_case, validate_case
from bb.availability_import import prepare_case, source_identity
from bb.concurrency_policy import source_row_digest
from bb.api import app
from bb.flora_jobs import JobStore, run_worker
from bb.profile_encoding import encode_profile


def fixture(modes=('SHARED', 'SHARED'), two_people=False, first_count=1, business='synthetic-a'):
    request, profile = sample(business)
    raw, case = request['input'], profile['reviewed_case']
    first = case['needs'][0]
    for n, row in zip(case['needs'], raw['customer_needs']):
        row.update(window_start=raw['customer_needs'][0]['window_start'],
            window_end=raw['customer_needs'][0]['window_end'], activity='Invented activity '+n['id'])
        n.update(earliest=first['earliest'], latest_end=first['latest_end'],
            locked_start=first['earliest'], eligible_employee_ids=['p1'], blockers=[])
    if two_people:
        person = deepcopy(case['employees'][0]);person['id']='p2';case['employees'].append(person)
        raw['staff'].append(dict(person_id='p2',alias='Second invented person'))
        source=deepcopy(raw['schedule_segments'][0]);source.update(segment_id='s2',sequence_id='pass2',person_id='p2')
        raw['schedule_segments'].append(source)
        original=deepcopy(case['source_schedule_segments'][0]);original.update(segment_id='s2',person_id='p2');case['source_schedule_segments'].append(original)
        candidate=deepcopy(case['candidates'][0]);candidate.update(id='c2',employee_id='p2');case['candidates'].append(candidate)
        for n in case['needs']:n['eligible_employee_ids']=['p1','p2']
    first['count']=first['count_confirmed']=first_count
    raw['customer_needs'][0]['personnel_count_candidate']=first_count
    profile['source_identity']=identity=source_identity(raw)
    if modes is not None:
        case['concurrency_policy']=dict(schema_version='bb-concurrency-policy/1.0',
            mode='EXPLICIT_PER_NEED_COMPATIBILITY',status='SCENARIO',decision_id='synthetic-sharing',
            source='Explicit invented user scenario',business_id=profile['business_id'],source_identity=identity,
            period_lo=case['period']['lo'],period_hi=case['period']['hi'])
        for n,row,mode in zip(case['needs'],raw['customer_needs'],modes):
            n['concurrency']=dict(mode=mode,decision_id='synthetic-sharing',source_ref='SYNTHETIC:'+n['id'],
                source_row_sha256=source_row_digest(row),reason='Invented explicit per-need decision')
    return request,profile


class ReviewedConcurrencyTests(unittest.TestCase):
    def solve(self, modes=('SHARED','SHARED'), **kwargs):
        request,profile=fixture(modes,**kwargs);case=prepare_case(request['input'],profile)
        return case,solve_case(case,seconds=1,workers=1)

    def test_shared_tasks_keep_both_rows_and_count_person_minutes_once(self):
        case,result=self.solve()
        self.assertEqual(result['after']['fully_covered_needs'],2)
        self.assertEqual(result['after']['ordinary_gross_minutes'],240)
        self.assertIsNone(result['after']['ordinary_net_minutes'])
        self.assertIsNone(result['cost_effect']['temporary_paid_cost_change'])
        self.assertEqual(result['validation']['violations'],[])
        self.assertEqual(result['concurrency']['assigned_person_minutes_once'],30)
        self.assertEqual(result['concurrency']['summed_need_duration_person_minutes'],60)
        self.assertEqual(result['concurrency']['maximum_simultaneous_by_person'],{'p1':2})
        self.assertEqual(len(result['schedule']['interventions']),2)
        self.assertTrue(all(r['concurrency']['mode']=='SHARED' for r in result['schedule']['interventions']))
        self.assertFalse(result['business_schedule_approved'])
        self.assertTrue(any(u['rule_id']=='practical_concurrency' for u in result['validation']['unknowns']))
        self.assertEqual(validate_case(case,result),result['validation'])

    def test_legacy_profile_does_not_enable_parallelism(self):
        _,result=self.solve(None)
        self.assertEqual(result['after']['fully_covered_needs'],1)
        self.assertNotIn('concurrency',result)

    def test_exclusive_and_unclassified_activity_cannot_share_the_person(self):
        for mode in ('EXCLUSIVE','UNCLASSIFIED'):
            with self.subTest(mode=mode):
                _,result=self.solve((mode,'SHARED'))
                self.assertEqual(result['after']['fully_covered_needs'],1)
                self.assertEqual(result['validation']['violations'],[])
                if mode=='UNCLASSIFIED':
                    self.assertTrue(any(u['rule_id']=='concurrency_classification' for u in result['validation']['unknowns']))

    def test_different_people_can_work_while_one_is_on_exclusive_task(self):
        _,result=self.solve(('EXCLUSIVE','SHARED'),two_people=True)
        self.assertEqual(result['after']['fully_covered_needs'],2)
        rows=result['raw_solution']['assignments']
        self.assertEqual(len({r['employee_id'] for r in rows}),2)

    def test_double_staffing_still_requires_distinct_people_with_the_same_interval(self):
        _,result=self.solve(two_people=True,first_count=2)
        self.assertEqual(result['after']['fully_covered_needs'],2)
        rows=[r for r in result['raw_solution']['assignments'] if r['need_id']=='n1']
        self.assertEqual(len({r['employee_id'] for r in rows}),2)
        self.assertEqual(len({(r['start'],r['end']) for r in rows}),1)
        self.assertEqual(result['concurrency']['assigned_person_minutes_once'],60)
        self.assertEqual(result['concurrency']['summed_need_duration_person_minutes'],90)

    def test_shared_tasks_never_pool_or_invent_another_persons_eligibility(self):
        request,profile=fixture(two_people=True,first_count=2)
        profile['reviewed_case']['needs'][0]['eligible_employee_ids']=['p1']
        case=prepare_case(request['input'],profile);result=solve_case(case,seconds=1,workers=1)
        self.assertEqual(result['unassigned_need_ids'],['n1'])

    def test_unknown_performer_remains_unassigned_even_when_activity_is_shared(self):
        request,profile=fixture();profile['reviewed_case']['needs'][1].update(eligible_employee_ids=[],blockers=['PERMISSION_UNKNOWN'])
        case=prepare_case(request['input'],profile);result=solve_case(case,seconds=1,workers=1)
        self.assertEqual(result['unassigned_need_ids'],['n2'])
        self.assertEqual(result['unassigned_needs'][0]['reason'],'NO_VERIFIED_PERFORMER')

    def test_independent_validator_rejects_exclusive_collision(self):
        case,result=self.solve();case['needs'][0]['concurrency']['mode']='EXCLUSIVE'
        checked=validate_case(case,result)
        self.assertTrue(any(v['rule_id']=='activity_capacity' for v in checked['violations']))

    def test_independent_validator_rejects_duplicate_person_for_double_staffing(self):
        case,result=self.solve(two_people=True,first_count=2)
        rows=[r for r in result['raw_solution']['assignments'] if r['need_id']=='n1']
        rows[1]['employee_id']=rows[0]['employee_id']
        self.assertTrue(any(v['rule_id']=='person_count' for v in validate_case(case,result)['violations']))

    def test_source_text_change_cannot_reuse_old_classification_even_with_updated_identity(self):
        request,profile=fixture();request['input']['customer_needs'][0]['activity']='Changed to shopping'
        profile['source_identity']=identity=source_identity(request['input'])
        profile['reviewed_case']['concurrency_policy']['source_identity']=identity
        with self.assertRaisesRegex(ValueError,'källrad'):
            prepare_case(request['input'],profile)

    def test_policy_cannot_follow_another_business_or_period(self):
        for key,value in [('business_id','synthetic-other'),('period_lo',0),('source_identity','0'*64)]:
            with self.subTest(key=key):
                request,profile=fixture();profile['reviewed_case']['concurrency_policy'][key]=value
                with self.assertRaises(ValueError):prepare_case(request['input'],profile)

    def test_missing_or_unsupported_decisions_fail_closed(self):
        for mutate in [lambda c:c.pop('concurrency_policy'),
                       lambda c:c['needs'][0].pop('concurrency'),
                       lambda c:c['concurrency_policy'].update(max_simultaneous=2),
                       lambda c:c['needs'][0]['concurrency'].update(mode='AUTO_FROM_TITLE')]:
            request,profile=fixture();mutate(profile['reviewed_case'])
            with self.assertRaises(ValueError):prepare_case(request['input'],profile)

    def test_validator_does_not_trust_tampered_policy_or_source_binding(self):
        for mutate in [lambda c:c['concurrency_policy'].update(business_id='other'),
                       lambda c:c['needs'][0]['concurrency'].update(source_row_sha256='0'*64),
                       lambda c:c['needs'][0]['original_submitted_row'].update(activity='Changed')]:
            case,result=self.solve();mutate(case)
            self.assertTrue(any(v['rule_id']=='concurrency_decision' for v in validate_case(case,result)['violations']))

    def test_model_and_preparation_do_not_modify_the_case_or_source(self):
        request,profile=fixture();before=deepcopy((request,profile))
        case=prepare_case(request['input'],profile);case_before=deepcopy(case)
        solve_case(case,seconds=1,workers=1)
        self.assertEqual((request,profile),before)
        self.assertEqual(case,case_before)

    def test_api_worker_and_reloaded_history_preserve_policy_and_three_businesses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);registry=dict(schema_version='bb-business-profiles/1.0',workspaces={})
            cases={};store=JobStore(root/'jobs.sqlite3')
            for business,modes in [('synthetic-a',('SHARED','SHARED')),('synthetic-b',('EXCLUSIVE','SHARED')),('synthetic-c',None)]:
                request,profile=fixture(modes,business=business);cases[business]=(request,profile)
                stored=encode_profile(profile,encoding='xz+base64') if business=='synthetic-a' else profile
                path=root/(business+'.json');path.write_text(json.dumps(stored))
                registry['workspaces']['org:'+business]=dict(business_id=business,data_use='development',profile_path=str(path))
            config=root/'registry.json';config.write_text(json.dumps(registry))
            with patch.dict(os.environ,{'BB_API_TOKEN':'test','BB_ENGINE_PROFILE_REGISTRY':str(config)}), \
                 patch('bb.engine_api.get_manager',return_value=Mock(store=store)), TestClient(app) as client:
                for business,(request,profile) in cases.items():
                    headers={'Authorization':'Bearer test','X-BB-Job-Owner':'org:'+business}
                    created=client.post('/api/engine/jobs',json=request,headers=headers)
                    self.assertEqual(created.status_code,202,created.text)
                    job=created.json();identity,lease=store.claim();self.assertEqual(identity,job['id'])
                    run_worker(str(store.path),identity,lease)
                    path='/api/engine/jobs/'+identity
                    first=client.get(path,headers=headers).json()
                    second=client.get(path,headers=headers).json()
                    self.assertEqual(first,second)
                    self.assertEqual(first['status'],'succeeded',first)
                    result=first['result'];expected=2 if business=='synthetic-a' else 1
                    self.assertEqual(result['after']['fully_covered_needs'],expected)
                    if 'concurrency_policy' in profile['reviewed_case']:
                        self.assertEqual(result['concurrency']['policy']['business_id'],business)
                        self.assertEqual(result['provenance']['concurrency_decision']['decision_id'],'synthetic-sharing')
                    duplicate=client.post('/api/engine/jobs',json=request,headers=headers).json()
                    self.assertEqual(duplicate['id'],identity)
                    self.assertTrue(duplicate['deduplicated'])
                    other='synthetic-b' if business!='synthetic-b' else 'synthetic-a'
                    wrong={'Authorization':'Bearer test','X-BB-Job-Owner':'org:'+other}
                    self.assertEqual(client.get(path,headers=wrong).status_code,404)

    def test_changed_reviewed_policy_creates_new_job_and_keeps_previous_result(self):
        request,profile=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'profile.json';path.write_text(json.dumps(profile));config=root/'registry.json'
            config.write_text(json.dumps(dict(schema_version='bb-business-profiles/1.0',workspaces={
                'org:synthetic-a':dict(business_id='synthetic-a',data_use='development',profile_path=str(path))})))
            store=JobStore(root/'jobs.sqlite3');headers={'Authorization':'Bearer test','X-BB-Job-Owner':'org:synthetic-a'}
            with patch.dict(os.environ,{'BB_API_TOKEN':'test','BB_ENGINE_PROFILE_REGISTRY':str(config)}), \
                 patch('bb.engine_api.get_manager',return_value=Mock(store=store)), TestClient(app) as client:
                first=client.post('/api/engine/jobs',json=request,headers=headers).json()
                identity,lease=store.claim();run_worker(str(store.path),identity,lease)
                before=client.get('/api/engine/jobs/'+identity,headers=headers).json()
                self.assertEqual(before['result']['after']['fully_covered_needs'],2)
                profile['reviewed_case']['needs'][0]['concurrency']['mode']='EXCLUSIVE'
                path.write_text(json.dumps(profile))
                second=client.post('/api/engine/jobs',json=request,headers=headers).json()
                self.assertNotEqual(second['id'],first['id'])
                self.assertFalse(second['deduplicated'])
                newer,lease=store.claim();run_worker(str(store.path),newer,lease)
                after=client.get('/api/engine/jobs/'+newer,headers=headers).json()
                self.assertEqual(after['result']['after']['fully_covered_needs'],1)
                self.assertEqual(client.get('/api/engine/jobs/'+identity,headers=headers).json(),before)


if __name__=='__main__':unittest.main()
