"""Exact original-source certificate; all fixtures synthetic, no search or IO."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bb.api import app
from bb.flora import _normalize, validate_case
from bb.engine_methods import prepare
from bb.flora_jobs import normalize_request, digest
from bb.flora_import import FloraImportError
from bb.availability_import import source_identity
from test_typed_windows_contract import flora_fixture, flora_result


def reviewed_fixture():
    body, profile = flora_fixture()
    body['input']['vc_answers'] = []
    body['input']['metadata'].pop('history_period_id', None)
    body['input']['metadata'].pop('source_layout', None)
    raw = normalize_request(body)['input']
    profile['source_identity'] = source_identity(raw)
    profile['source_file_sha256'] = raw['metadata']['source_file_sha256']
    return body, profile


def export_fixture():
    body, profile = reviewed_fixture()
    case = prepare(profile, normalize_request(body))
    raw, result = flora_result(case)
    return body, profile, case, raw, result


class SourceBasisTests(unittest.TestCase):
    def test_complete_proof_uses_all_original_source_rows(self):
        body, profile, case, raw, result = export_fixture()
        proof = result['source_basis']
        self.assertEqual(proof, dict(kind='VERIFIED_UPLOADED_ORIGINAL',
            verification='EXACT_SERVER_REVIEWED_INPUT', source_identity=profile['source_identity'],
            source_file_sha256=body['input']['metadata']['source_file_sha256'],
            segments=[dict(segment_id=r['segment_id'], person_id=r['person_id'], start=r['start'],
                end=r['end'], code=r['source_code']) for r in body['input']['schedule_segments']]))
        self.assertEqual(result['method'], 'joint-shifts-breaks-needs/v1')
        self.assertTrue(result['review_required'])
        self.assertFalse(result['business_schedule_approved'])
        self.assertEqual(result['validation']['overall'], 'UNKNOWN')

    def test_no_proof_from_profile_name_or_workbook_hash_alone(self):
        body, profile = reviewed_fixture()
        profile.pop('source_identity'); profile.pop('source_file_sha256')
        profile['profile_id'] = 'flora-original-upload-morning-plan-historical-pass-20261021'
        case = prepare(profile, normalize_request(body))
        self.assertNotIn('source_basis', flora_result(case)[1])

    def test_client_cannot_supply_server_review_pin_or_certificate(self):
        body, profile = reviewed_fixture()
        profile.pop('source_identity'); profile.pop('source_file_sha256')
        body['input']['metadata']['source_identity'] = digest(body['input'])
        body['input']['metadata']['source_basis'] = {'verification':'EXACT_SERVER_REVIEWED_INPUT'}
        self.assertNotIn('source_basis', flora_result(prepare(profile, normalize_request(body)))[1])

    def test_changed_source_time_with_same_workbook_sha_is_not_original(self):
        body, profile = reviewed_fixture()
        body['input']['schedule_segments'][0]['end'] = '2027-01-03T16:17'
        with self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_changed_duration_with_same_workbook_sha_is_not_original(self):
        body, profile = reviewed_fixture()
        body['input']['customer_needs'][0]['duration_minutes'] = 59
        with self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_dataset_and_source_facts_are_in_exact_pin(self):
        for key in ['dataset_id','source_file_sha256']:
            body, profile = reviewed_fixture()
            body['input']['metadata'][key] = 'b'*64
            with self.subTest(key=key),self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_malformed_or_mismatched_server_pin_is_rejected(self):
        for value in ['', 'a'*63, 'x'*64, 123, 'b'*64]:
            body, profile = reviewed_fixture()
            profile['source_identity'] = value
            with self.subTest(value=value),self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_missing_or_invalid_file_sha_never_gets_complete_proof(self):
        for value in [None, '', 'z'*64, 'a'*63]:
            body, profile = reviewed_fixture()
            body['input']['metadata']['source_file_sha256'] = value
            profile['source_identity'] = source_identity(normalize_request(body)['input'])
            with self.subTest(value=value),self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_server_file_hash_must_match(self):
        for value in [None, 'b'*64]:
            body, profile = reviewed_fixture()
            profile['source_file_sha256'] = value
            with self.subTest(value=value),self.assertRaises(FloraImportError):prepare(profile, normalize_request(body))

    def test_source_is_not_replaced_by_optimized_or_excluded_rows(self):
        body, profile, case, raw, result = export_fixture()
        original = deepcopy(result['source_basis'])
        raw['segments'] = [dict(id='generated-candidate',person='person-a',start=600,end=840,code='Ar')]
        result = _normalize(case,raw,{})
        self.assertEqual(result['source_basis'],original)
        self.assertNotIn('generated-candidate',{r['segment_id'] for r in original['segments']})
        self.assertIn('absence-row',{r['segment_id'] for r in original['segments']})
        self.assertIn('history-row',{r['segment_id'] for r in original['segments']})

    def test_import_and_export_do_not_mutate_source_or_profile(self):
        body, profile = reviewed_fixture()
        before = deepcopy((body,profile))
        case = prepare(profile,normalize_request(body))
        _, result = flora_result(case)
        result['source_basis']['segments'][0]['code']='changed-result'
        self.assertEqual((body,profile),before)
        self.assertNotEqual(case['integration']['source_basis']['segments'][0]['code'],'changed-result')

    def test_original_snapshot_change_after_import_stops_export(self):
        body, profile, case, raw, result = export_fixture()
        case['import_provenance']['upload']['schedule_segments'][0]['end']='2027-01-03T17:00'
        with self.assertRaises(ValueError):_normalize(case,raw,{})

    def test_export_adds_only_source_basis(self):
        body, profile, case, raw, result = export_fixture()
        legacy = deepcopy(case)
        legacy['integration'].pop('source_basis')
        other = _normalize(legacy,raw,result['validation'])
        result.pop('source_basis')
        self.assertEqual(result,other)

    def test_exact_pin_preflight_stops_before_job_manager(self):
        body, profile = reviewed_fixture()
        registry={'schema_version':'bb-business-profiles/1.0','workspaces':{'org:synthetic-window':{
            'business_id':'synthetic-window','data_use':'development','profile_path':'/synthetic/profile'}}}
        def read(path,label):return deepcopy(registry if path=='/synthetic/registry' else profile)
        with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic-token','BB_ENGINE_PROFILE_REGISTRY':'/synthetic/registry','BB_ENGINE_REMOTE_ENABLED':'1'}),patch('bb.business_profiles._read',side_effect=read):
            with TestClient(app) as client:
                headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'org:synthetic-window',
                         'Idempotency-Key':'STOP/BEFORE_MANAGER'}
                accepted=client.post('/api/engine/jobs',json=body,headers=headers)
                self.assertEqual(accepted.status_code,422)
                self.assertEqual(accepted.json()['detail'],'Ogiltig körningsnyckel.')
                body['input']['customer_needs'][0]['duration_minutes']=59
                rejected=client.post('/api/engine/jobs',json=body,headers=headers)
                self.assertEqual(rejected.status_code,422)
                self.assertEqual(rejected.json()['detail']['code'],'INPUT_REVIEW_REQUIRED')

    def test_absent_legacy_metadata_hashes_as_null_without_mutation(self):
        body, profile = reviewed_fixture(); raw=body['input']; before=deepcopy(raw)
        explicit=deepcopy(raw);explicit['metadata'].update(source_layout=None,history_period_id=None)
        self.assertEqual(source_identity(raw),source_identity(explicit))
        case=prepare(profile,normalize_request(body))
        self.assertNotIn('source_layout',case['import_provenance']['upload']['metadata'])
        self.assertNotIn('history_period_id',case['import_provenance']['upload']['metadata'])
        self.assertEqual(raw,before)

    def test_routing_metadata_cannot_hide_behind_source_projection(self):
        for key,value in [('business_id','foreign'),('data_use','operational')]:
            body,profile=reviewed_fixture();body['input']['metadata'][key]=value
            self.assertEqual(source_identity(body['input']),profile['source_identity'])
            with self.subTest(key=key),self.assertRaises(FloraImportError):prepare(profile,normalize_request(body))

    def test_all_stable_id_lists_reject_duplicate_missing_or_blank_ids(self):
        body,profile=reviewed_fixture()
        for table,key in [('staff','person_id'),('customers','customer_id'),('schedule_segments','segment_id'),('customer_needs','need_id')]:
            for change in ['duplicate','missing','blank']:
                raw=deepcopy(body['input'])
                if change=='duplicate':raw[table].append(deepcopy(raw[table][0]))
                elif change=='missing':raw[table][0].pop(key)
                else:raw[table][0][key]=''
                with self.subTest(table=table,change=change),self.assertRaises(ValueError):source_identity(raw)

    def test_row_order_does_not_change_source_identity(self):
        body,profile=reviewed_fixture();raw=body['input']
        for key in ['staff','customers','schedule_segments','customer_needs']:raw[key].reverse()
        self.assertEqual(source_identity(raw),profile['source_identity'])
