from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from bb.api import app
from bb.availability_import import check_case, prepare_case, source_identity
from bb.availability import solve_case, validate_case
from bb.engine_methods import prepare
from bb.flora_jobs import JobStore, run_worker
from availability_fixtures import sample


class AvailabilityMethodTests(unittest.TestCase):
    def test_fresh_solver_retains_unknown_need_and_vacancy_without_inventing_staff(self):
        request, profile = sample()
        before = deepcopy((request, profile))
        case = prepare(profile, request)
        result = solve_case(case, seconds=1, workers=1)
        self.assertIn(result['solver_status'], ('OPTIMAL', 'FEASIBLE'))
        self.assertEqual(result['after']['fully_covered_needs'], 1)
        self.assertEqual(result['after']['total_needs'], 2)
        self.assertEqual(result['unassigned_need_ids'], ['n2'])
        self.assertEqual(result['unassigned_needs'][0]['reason'], 'NO_VERIFIED_PERFORMER')
        self.assertEqual({s['person_id'] for s in result['schedule']['segments']}, {'p1'})
        self.assertEqual(result['after']['ordinary_gross_minutes'], 240)
        self.assertIsNone(result['after']['ordinary_net_minutes'])
        self.assertIsNone(result['cost_effect']['temporary_paid_cost_change'])
        self.assertFalse(result['time_accounting']['paid_time_verified'])
        self.assertTrue(result['time_accounting']['ordinary_Ar_preserved'])
        self.assertFalse(result['business_schedule_approved'])
        self.assertEqual(result['validation']['overall'], 'UNKNOWN')
        self.assertEqual(result['validation']['violations'], [])
        self.assertEqual(result['before']['vacant_minutes'], 240)
        self.assertIsNone(result['after']['vacant_minutes'])
        self.assertEqual((request, profile), before)

    def test_source_changes_require_explicit_review_even_with_same_file_hash(self):
        for mutate in (
            lambda x: x['customer_needs'][0].update(duration_minutes=40),
            lambda x: x['staff'][0].update(day_allowed=True),
            lambda x: x['metadata']['periods'][1].update(end='2026-06-29'),
            lambda x: x['schedule_segments'][1].update(person_id='p1'),
        ):
            request, profile = sample(); mutate(request['input'])
            with self.assertRaisesRegex(ValueError, 'indataversion'):
                prepare(profile, request)

    def test_routing_metadata_and_row_order_do_not_change_source_identity(self):
        request, _ = sample(); raw = request['input']; before = source_identity(raw)
        raw['metadata'].update(business_id='another-authenticated-owner', data_use='development', import_warnings=['display'])
        raw['customer_needs'].reverse(); raw['schedule_segments'].reverse()
        self.assertEqual(source_identity(raw), before)

    def test_client_cannot_add_unsupported_decisions_or_choose_strategy(self):
        request, profile = sample(); request['scenario']['workspace']={'contacts':{'k1':{'kp':'p1'}}}
        with self.assertRaisesRegex(ValueError, 'kontaktpersonsbeslut'): prepare(profile,request)
        request, profile = sample(); request['objective_mode']='coverage_then_workload_then_temporary'
        with self.assertRaisesRegex(ValueError, 'behovstäckning'): prepare(profile,request)
        request, profile = sample(); profile['engine_strategy']='unknown'
        with self.assertRaisesRegex(ValueError, 'stöds inte'): prepare(profile,request)

    def test_reviewed_domains_cannot_contain_old_solution_or_unknown_capacity(self):
        request, profile=sample()
        profile['reviewed_case']['selected_duties']=[]
        with self.assertRaisesRegex(ValueError, 'sparat motorresultat'): prepare(profile,request)
        request, profile=sample(); profile['reviewed_case']['employees'][0]['availability_status']='UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'tillgänglighet'): prepare(profile,request)
        request, profile=sample(); profile['reviewed_case']['needs'][1]['eligible_employee_ids']=['p1']
        with self.assertRaisesRegex(ValueError, 'olöst behörighetsvillkor'): prepare(profile,request)

    def test_independent_validator_rejects_invented_assignment_after_solver(self):
        request, profile=sample(); case=prepare(profile,request)
        result=solve_case(case,seconds=1,workers=1)
        modified=deepcopy(result)
        modified['raw_solution']['assignments'].append(dict(need_id='n2',employee_id='p1',candidate_id='c1',
            start=case['needs'][1]['earliest'],end=case['needs'][1]['earliest']+30))
        checked=validate_case(case,modified)
        self.assertEqual(checked['overall'],'FAIL')
        self.assertTrue(any(v['rule_id']=='need_eligibility' for v in checked['violations']))

    def test_original_duty_has_the_same_four_hour_minimum(self):
        request, profile=sample(); case=prepare(profile,request)
        case['employees'][0]['planned_Ar_target_minutes']=180
        c=case['candidates'][0]
        c.update(is_original=True,is_new_or_shortened=False,end=c['start']+180,work=[[c['start'],c['start']+180]])
        result=solve_case(case,seconds=1,workers=1)
        self.assertEqual(result['solver_status'],'INFEASIBLE')
        self.assertEqual(result['schedule']['segments'],[])
        self.assertIsNone(result['after']['ordinary_gross_minutes'])

    def test_independent_minimum_also_rejects_a_retained_original_short_duty(self):
        request, profile=sample(); case=prepare(profile,request)
        result=solve_case(case,seconds=1,workers=1)
        duty=result['raw_solution']['selected_duties'][0]
        duty.update(is_original=True,is_new_or_shortened=False,end=duty['start']+180,work=[[duty['start'],duty['start']+180]])
        case['candidates'][0].update(deepcopy(duty))
        case['employees'][0]['planned_Ar_target_minutes']=180
        checked=validate_case(case,result)
        self.assertTrue(any(v['rule_id']=='minimum_whole_pass' for v in checked['violations']))


class AvailabilityJobTests(unittest.TestCase):
    def test_shared_transfer_has_the_same_eight_mebibyte_bound_as_the_app(self):
        from bb.flora_api import json_body
        from fastapi import HTTPException
        import asyncio
        class Request:
            async def stream(self):
                yield b'"'+b'x'*(6*1024*1024)
                yield b'"'
        with self.assertRaises(HTTPException): asyncio.run(json_body(Request()))
        self.assertEqual(len(asyncio.run(json_body(Request(),max_body=8*1024*1024))),6*1024*1024)
        with self.assertRaises(HTTPException): asyncio.run(json_body(Request(),max_body=6*1024*1024+1))

    def test_authenticated_api_worker_and_read_keep_three_profiles_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); registry=dict(schema_version='bb-business-profiles/1.0',workspaces={})
            store=JobStore(root/'jobs.sqlite3'); bodies={}
            for business in ('synthetic-a','synthetic-b','synthetic-c'):
                request, profile=sample(business); bodies[business]=request
                path=root/(business+'.json');path.write_text(json.dumps(profile))
                registry['workspaces']['org:'+business]=dict(business_id=business,data_use='development',profile_path=str(path))
            path=root/'registry.json';path.write_text(json.dumps(registry))
            with patch.dict(os.environ,{'BB_API_TOKEN':'test','BB_ENGINE_PROFILE_REGISTRY':str(path)}), patch('bb.engine_api.get_manager',return_value=Mock(store=store)), TestClient(app) as client:
                def headers(business):return {'Authorization':'Bearer test','X-BB-Job-Owner':'org:'+business}
                for business, request in bodies.items():
                    created=client.post('/api/engine/jobs',json=request,headers=headers(business))
                    self.assertEqual(created.status_code,202,created.text)
                    job=created.json(); identity,lease=store.claim();self.assertEqual(identity,job['id'])
                    run_worker(str(store.path),identity,lease)
                    fetched=client.get('/api/engine/jobs/'+identity,headers=headers(business)).json()
                    self.assertEqual(fetched['status'],'succeeded',fetched)
                    result=fetched['result']
                    self.assertEqual(result['method'],'reviewed-availability/1.0')
                    self.assertEqual(result['after']['fully_covered_needs'],1)
                    self.assertEqual(result['provenance']['job_id'],identity)
                    self.assertEqual(result['provenance']['engine_context']['business_id'],business)
                    self.assertEqual(result['input_hash'],job['input_hash'])
                    other='synthetic-b' if business!='synthetic-b' else 'synthetic-a'
                    self.assertEqual(client.get('/api/engine/jobs/'+identity,headers=headers(other)).status_code,404)
                    duplicate=client.post('/api/engine/jobs',json=request,headers=headers(business)).json()
                    self.assertEqual(duplicate['id'],identity)
                    self.assertTrue(duplicate['deduplicated'])
                    changed=deepcopy(request);changed['input']['customer_needs'][0]['duration_minutes']=40
                    denied=client.post('/api/engine/jobs',json=changed,headers=headers(business))
                    self.assertEqual(denied.status_code,422,denied.text)
                mismatched=deepcopy(bodies['synthetic-a']);mismatched['input']['metadata']['business_id']='synthetic-b'
                self.assertEqual(client.post('/api/engine/jobs',json=mismatched,headers=headers('synthetic-a')).status_code,422)
