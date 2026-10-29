"""Mandatory joint export: synthetic source and in-memory API only."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bb.api import app
from bb import need_windows
from bb.engine_methods import prepare
from bb.flora import _normalize, validate_case
from bb.flora_jobs import normalize_request
from bb.availability_import import source_identity
from test_source_basis import reviewed_fixture
from test_typed_windows_contract import flora_fixture, flora_result


def fixture():
    b,p=reviewed_fixture()
    unplaced=deepcopy(b['input']['customer_needs'][0]);unplaced.update(need_id='unplaced-need',window_semantics='EXECUTION_WINDOW',duration_minutes=10)
    b['input']['customer_needs'].append(unplaced)
    decision=deepcopy(p['need_decisions']['source-need']);decision['engine_id']='unplaced-engine'
    p['need_decisions']['unplaced-need']=decision
    outside=deepcopy(unplaced);outside.update(need_id='history-need',date='2027-01-03')
    b['input']['customer_needs'].append(outside)
    p['source_identity']=source_identity(b['input'])
    return b,p


class JointWindowExportTests(unittest.TestCase):
    def test_all_period_needs_including_unplaced_exactly_once(self):
        b,p=fixture();c=prepare(p,normalize_request(b));raw,out=flora_result(c)
        contract=out['need_window_contract']
        self.assertEqual(contract['version'],'bb-need-window/1.0')
        self.assertEqual([r['need_id'] for r in contract['needs']],['source-need','unplaced-need'])
        self.assertEqual(out['unassigned_need_ids'],['unplaced-need'])
        self.assertEqual(json.loads(json.dumps(out))['need_window_contract'],contract)
        for row in contract['needs']:
            source=next(n for n in b['input']['customer_needs'] if n['need_id']==row['need_id'])
            self.assertEqual(row['duration_minutes'],source['duration_minutes'])
            self.assertEqual(row['personnel_count'],source['personnel_count_candidate'])
        self.assertEqual(out['source_basis'],c['integration']['source_basis'])

    def test_missing_duplicate_extra_or_remapped_internal_needs_rejected(self):
        b,p=fixture();original=prepare(p,normalize_request(b))
        for field in ['source_needs','needs']:
            for mode in ['missing','duplicate','extra']:
                c=deepcopy(original)
                if mode=='missing':c[field].pop()
                elif mode=='duplicate':c[field].append(deepcopy(c[field][0]))
                else:
                    n=deepcopy(c[field][0]);n['id']='extra';c[field].append(n)
                with self.subTest(field=field,mode=mode),self.assertRaises(ValueError):_normalize(c,{}, {})
        c=deepcopy(original)
        c['integration']['need_id_map']['unplaced-engine']='source-need'
        with self.assertRaises(ValueError):_normalize(c,{}, {})

    def test_truncating_both_lists_still_fails_source_coverage(self):
        b,p=fixture();c=prepare(p,normalize_request(b))
        c['source_needs'].pop();c['needs'].pop()
        with self.assertRaisesRegex(ValueError,'planeringsperiodens'):_normalize(c,{}, {})

    def test_modeled_fields_cannot_diverge_from_export(self):
        b,p=fixture();original=prepare(p,normalize_request(b))
        for field,value in [('duration',61),('count',2),('window_semantics','EXECUTION_WINDOW'),('source_window_start',541),('source_window_end',561),('domains',[[540,559]])]:
            c=deepcopy(original);c['needs'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):_normalize(c,{}, {})

    def test_boundary_starts_and_late_finish(self):
        b,p=flora_fixture();c=prepare(p,normalize_request(b))
        for start in [539,561]:
            with self.subTest(start=start),self.assertRaises(ValueError):flora_result(c,start)
        for start in [540,560]:
            _,out=flora_result(c,start)
            self.assertGreater(out['schedule']['interventions'][0]['end'],out['need_window_contract']['needs'][0]['source_window_end'])

    def test_execution_end_must_fit(self):
        b,p=flora_fixture('EXECUTION_WINDOW',10);c=prepare(p,normalize_request(b))
        flora_result(c,550)
        with self.assertRaises(ValueError):flora_result(c,551)

    def test_explicit_two_person_need_is_exported_without_defaulting_to_one(self):
        b,p=flora_fixture()
        b['input']['customer_needs'][0].update(personnel_count_candidate=2,source_two_person_flag=True)
        p['need_decisions']['source-need']['expected']['source_two_person_flag']=True
        c=prepare(p,normalize_request(b))
        out=_normalize(c,{}, {})
        self.assertEqual(out['need_window_contract']['needs'][0]['personnel_count'],2)

    def test_duplicate_or_unknown_raw_placement_rejected(self):
        b,p=flora_fixture();c=prepare(p,normalize_request(b));raw,out=flora_result(c)
        for bad in [[raw['placements'][0]]*2,[dict(id='unknown',start=540)]]:
            with self.assertRaises(ValueError):_normalize(c,dict(raw,placements=bad),{})

    def test_invalid_executor_certificate_rejected_at_json_boundary(self):
        b,p=flora_fixture();c=prepare(p,normalize_request(b));raw,_=flora_result(c)
        v=validate_case(c,raw)
        v['certificates']['executors'][0]['start']='2027-01-04T09:21'
        with self.assertRaisesRegex(ValueError,'exporterad placering'):_normalize(c,raw,v)

    def test_missing_type_stops_api_before_job_manager(self):
        b,p=flora_fixture(None,10)
        registry={'schema_version':'bb-business-profiles/1.0','workspaces':{'org:synthetic-window':{'business_id':'synthetic-window','data_use':'development','profile_path':'/synthetic/profile.json'}}}
        with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic-token','BB_ENGINE_PROFILE_REGISTRY':'/synthetic/registry.json','BB_ENGINE_REMOTE_ENABLED':'1'}),patch('bb.business_profiles._read',side_effect=lambda path,label:deepcopy(registry if 'registry' in path else p)),patch('bb.engine_api.get_manager',side_effect=AssertionError('No job manager')) as manager:
            with TestClient(app) as client:
                r=client.post('/api/engine/jobs',json=b,headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'org:synthetic-window'})
            self.assertEqual(r.status_code,422)
            self.assertEqual(r.json()['detail']['code'],'INPUT_REVIEW_REQUIRED')
            self.assertIn('NEED_WINDOW_CONTRACT_REQUIRED',r.json()['detail']['message'])
            manager.assert_not_called()

    def test_export_rejects_duplicate_source_ids(self):
        b,p=fixture();c=prepare(p,normalize_request(b))
        with self.assertRaises(ValueError):need_windows.export(c['source_needs'],lambda n:'same',str,required=True)

    def test_source_basis_code_and_output_unchanged(self):
        b,p=fixture();before=deepcopy((b,p));c=prepare(p,normalize_request(b));_,out=flora_result(c)
        self.assertEqual(out['source_basis'],dict(kind='VERIFIED_UPLOADED_ORIGINAL',verification='EXACT_SERVER_REVIEWED_INPUT',source_identity=p['source_identity'],source_file_sha256=p['source_file_sha256'],segments=[dict(segment_id=r['segment_id'],person_id=r['person_id'],start=r['start'],end=r['end'],code=r['source_code']) for r in b['input']['schedule_segments']]))
        self.assertEqual((b,p),before)
