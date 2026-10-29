"""Common decision coverage and positive/negative solver-free timing tests."""
import contextlib, json, os
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from collections import Counter
from bb import flora_jobs as jobs, flora_window_binding as window, flora_timing_decisions as timing, need_windows
from bb.flora_import import prepare_case
from bb.engine_methods import prepare
from bb.availability_import import source_identity
from test_typed_windows_contract import flora_fixture, flora_result
from run_flora_original_windows import MemorySink


@contextlib.contextmanager
def synthetic_timing(policy='MOVABLE_WITHIN_SOURCE_WINDOW'):
    """A separate fictional decision; never substitutes into Flora's profile."""
    body,p=flora_fixture(None,10);body['input']['vc_answers']=[]
    p['source_identity']=source_identity(body['input']);p['source_file_sha256']=body['input']['metadata']['source_file_sha256']
    n=body['input']['customer_needs'][0]
    evidence=dict(version='flora-original-window-binding/1.0',binding_id='synthetic-window-binding',profile_id=p['profile_id'],
        base_profile_hash=jobs.digest(p),business_id=p['business_id'],data_use=p['data_use'],dataset_id=body['input']['metadata']['dataset_id'],
        source_identity=p['source_identity'],source_file_sha256=p['source_file_sha256'],
        period=dict(id='next',start='2027-01-04',end='2027-01-31',timezone='Europe/Stockholm'),
        window_semantics='EXECUTION_WINDOW',decision_ref='SYNTHETIC-INTERVAL',inactive_flex_need_ids=[],inactive_k3_need_ids=[],
        needs=[dict(need_id=n['need_id'],input_row_sha256=jobs.digest(n),app_reference_literal=n.get('source_ref'),
          original_source_reference=dict(source_id=None,sheet=None,row=n['source_fields']['source_row']))])
    decision=dict(version='flora-timing-decision/1.0',decision_id='SYNTHETIC-COMMON-DECISION',
        window_evidence_hash=jobs.digest(evidence),window_binding_id=evidence['binding_id'],
        **{k:evidence[k] for k in ('source_identity','source_file_sha256','profile_id','dataset_id','period')},
        groups=[dict(group_id='SYNTHETIC-G1',policy=policy,category='SYNTHETIC_UNBOUND_TASK',reason='EXPLICIT_SYNTHETIC_PERMISSION',need_ids=[n['need_id']])])
    with patch.object(window,'PROFILE_ID',p['profile_id']),patch.object(window,'EVIDENCE_HASH',jobs.digest(evidence)),patch.object(window,'_load_evidence',return_value=evidence),\
         patch.object(timing,'PROFILE_ID',p['profile_id']),patch.object(timing,'DECISION_HASH',jobs.digest(decision)),patch.object(timing,'_load',return_value=decision):
        bound=window.bind_profile(p,body['input']['metadata']['dataset_id'])
        yield body,bound


class TimingDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(os.environ['BB_TEST_PRIVATE_SNAPSHOTS'])
        cls.raw=json.loads((root/'exact-input.json').read_text());cls.old=json.loads((root/'selected-profile-bound.json').read_text())
        cls.bound=window.bind_profile(cls.old,'FLORA-RADATA');cls.case=prepare_case(cls.raw,cls.bound)

    def test_common_decision_exact_partition_and_no_inherited_exceptions(self):
        policies=Counter(d['timing_authorization']['policy'] for d in self.bound['need_decisions'].values())
        self.assertEqual(dict(policies),{'MOVABLE_WITHIN_SOURCE_WINDOW':500,'REVIEW_REQUIRED':775,'UNIQUE_SOURCE_START':176})
        categories=Counter(d['timing_authorization']['category'] for d in self.bound['need_decisions'].values() if d['timing_authorization']['policy']=='REVIEW_REQUIRED')
        self.assertEqual(dict(categories),{'MEAL_LOCKED':92,'MEDICATION_LOCKED':516,'EVENT_DEPENDENT':104,'REMINDER_BEFORE_FIXED_EVENT':63})
        for d in self.bound['need_decisions'].values():self.assertIs(d['flex'],False)
        self.assertEqual(self.bound['window_binding'],window._load_evidence())
        self.assertEqual(len(self.bound['window_binding']['inactive_flex_need_ids']),286)
        self.assertEqual(len(self.bound['window_binding']['inactive_k3_need_ids']),8)

    def test_preparations_are_separate_no_split_no_prior_evening_invention(self):
        byid={n['need_id']:n for n in self.raw['customer_needs']}
        for nid,d in self.bound['need_decisions'].items():
            n=byid[nid];a=d['timing_authorization'];title=n['activity'];desc=n['source_fields'].get('Beskrivning') or ''
            if title=='Frukost':self.assertEqual(a['category'],'MEAL_LOCKED')
            if title=='Matlagning' and 'Tillsyn vid måltider' in desc:self.assertEqual(a['category'],'COMPOSITE_PREPARATION_AND_MEAL')
            if title=='Matlagning' and 'tillagar lunch' in desc:self.assertEqual(a['category'],'LUNCH_PREPARATION')
            if n['medication'] or 'läkemedelslistan' in desc:self.assertEqual(a['category'],'MEDICATION_LOCKED')
        for n in self.case['needs']:
            self.assertEqual(n['domains'],[[n['source_window_start'],n['source_window_end']-n['duration']]])
        self.assertEqual(len(self.case['needs']),1451)

    def test_server_permission_cannot_be_added_removed_or_mutated(self):
        for action in ['remove','policy','hash','source','need_ids']:
            p=deepcopy(self.bound)
            if action=='remove':p.pop('timing_binding')
            elif action=='policy':next(iter(p['need_decisions'].values()))['timing_authorization']['policy']='MOVABLE_WITHOUT_LIMIT'
            elif action=='hash':p['timing_binding']['decision_id']='unreviewed'
            elif action=='source':p['timing_binding']['source_file_sha256']='b'*64
            else:p['timing_binding']['groups'][0]['need_ids']=[]
            with self.subTest(action=action),self.assertRaises(ValueError):window.verify_input(self.raw,p)

    def test_authorized_synthetic_need_moves_only_within_source_window(self):
        with synthetic_timing() as (b,p):
            case=prepare(p,jobs.normalize_request(b))
            # 09:00–09:20, duration 10: both starts 09:00 and 09:10 allowed.
            for start in [540,550]:
                raw,result=flora_result(case,start)
                self.assertEqual(result['need_window_contract']['needs'][0]['source_window_end'],'2027-01-04T09:20+01:00')
                self.assertEqual(result['validation']['overall'],'UNKNOWN')
            for start in [539,551]:
                with self.subTest(start=start),self.assertRaises(ValueError):flora_result(case,start)

    def test_locked_synthetic_need_stays_blocked_even_with_narrowed_domain(self):
        with synthetic_timing('REVIEW_REQUIRED') as (b,p):
            with self.assertRaisesRegex(ValueError,'NEED_TIMING_DECISION_REQUIRED: 1'):prepare(p,jobs.normalize_request(b))
            case=prepare_case(b['input'],p)
            for collection in ['source_needs','needs']:case[collection][0]['domains']=[[540,540]]
            with self.assertRaisesRegex(ValueError,'NEED_TIMING_DECISION_REQUIRED: 1'):need_windows.check_joint(case)

    def test_worker_rechecks_internal_permission_and_missing_marker(self):
        with synthetic_timing() as (b,p):
            case=prepare(p,jobs.normalize_request(b))
            bad=deepcopy(case)
            for key in ['source_needs','needs']:bad[key][0]['timing_authorization']['decision_id']='forged'
            with self.assertRaisesRegex(ValueError,'TIMING_DECISION_BINDING_MISMATCH'):need_windows.check_joint(bad)
            bad=deepcopy(case);bad['integration'].pop('timing_binding')
            with self.assertRaisesRegex(ValueError,'TIMING_DECISION_BINDING_MISMATCH'):need_windows.check_joint(bad)


def export_authorized_fixture(out):
    """Actual worker export, with deterministic solver-free fixture at 09:10."""
    with synthetic_timing() as (body,profile):
        request=jobs.normalize_request(body)
        request['engine_context']={'business_id':profile['business_id'],'data_use':profile['data_use'],'profile_id':profile['profile_id'],'automatic_learning':False}
        row=dict(id='e'*32,status='running',input_hash=jobs.digest(request['input']),profile_hash=jobs.digest(profile),
            request_json=jobs.canonical(request),profile_json=jobs.canonical(profile),method_hash=jobs.method_fingerprint(),
            build_commit='synthetic-patricia-contract',created_at='2027-01-04T00:00:00Z',started_at=None,finished_at=None,error_json=None,result_json=None)
        sink=MemorySink(row);public=jobs.JobStore.public
        with patch.object(jobs,'JobStore',return_value=sink),patch('bb.engine_methods.solve',side_effect=lambda p,c,r:flora_result(c,550)[1]),\
             patch.dict(os.environ,{'RENDER_GIT_COMMIT':row['build_commit']}),patch.object(jobs.time,'monotonic',return_value=0):
            jobs.run_worker('/synthetic/no-database',row['id'],'synthetic-lease')
        assert sink.result
        (out/'synthetic-input.json').write_text(jobs.canonical(body['input']))
        (out/'synthetic-result.raw.json').write_text(sink.result)
        (out/'synthetic-job.raw.json').write_text(jobs.canonical(public(sink.row)))
        return jobs.digest(json.loads(sink.result))
