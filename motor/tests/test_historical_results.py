"""Only local TestClient + temporary SQLite. Never call solve or remote services."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from bb.api import app
from bb.flora import _normalize
from bb.flora_import import prepare_case
from bb.flora_jobs import digest
from test_business_engine import business_sample


class HistoricalResultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        body, self.profile = business_sample('unit-a')
        self.raw = body['input']
        self.raw['metadata'].pop('business_id')
        self.raw['metadata'].pop('data_use')
        self.raw['metadata'].update(dataset_id='synthetic-history', source_file_sha256=sha256(b'synthetic original').hexdigest())
        case = prepare_case(self.raw, self.profile, body['scenario'])
        self.result = _normalize(case, {'segments': case['references']['import']['segments'],
            'placements': [], 'breaks': [], 'stages': []}, {'overall': 'UNKNOWN', 'rules': [
                {'rule_id': 'synthetic-unknown', 'status': 'UNKNOWN', 'message': 'Unknown'}],
                'violations': [], 'unknowns': [{'rule_id': 'synthetic-unknown', 'message': 'Unknown'}]})
        self.configure(self.raw, self.profile, json.dumps(self.result).encode(), b'synthetic original', body['scenario'])
        self.headers = {'Authorization': 'Bearer synthetic-service', 'X-BB-Job-Owner': 'org:unit-a'}
        self.admin = {**self.headers, 'X-BB-Historical-Registrar': 'synthetic-registrar'}
        self.url = '/api/engine/historical-results'
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        for name in ('bb.engine_methods.solve', 'bb.flora._solve', 'bb.engine_api.get_manager', 'socket.create_connection'):
            guard = patch(name, side_effect=AssertionError('No solver, job manager or network allowed'))
            guard.start(); self.addCleanup(guard.stop)

    def write(self, name, value):
        p = self.root / name
        p.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return str(p)

    def configure(self, raw, profile, result_bytes, source_bytes, scenario):
        self.write('profile.json', profile)
        self.write('input.json', raw)
        self.write('result.json', result_bytes)
        self.write('source.xlsx', source_bytes)
        def spec(name):
            p = self.root / name
            return dict(path=str(p), sha256=sha256(p.read_bytes()).hexdigest())
        business = profile['business_id']
        self.owner = 'org:' + business
        self.registry = {'schema_version': 'bb-business-profiles/1.0', 'workspaces': {
            self.owner: dict(business_id=business, data_use='development', profile_path=str(self.root/'profile.json')),
            'org:other': dict(business_id='other', data_use='development', profile_path=str(self.root/'profile.json'))}}
        self.write('profiles.json', self.registry)
        self.entry = dict(owner=self.owner, business_id=business, dataset_id=raw['metadata']['dataset_id'],
            source_file=spec('source.xlsx'), input_file=spec('input.json'), result_file=spec('result.json'),
            input_hash=digest(raw), profile_id=profile['profile_id'], profile_hash=digest(profile),
            period=json.loads(result_bytes)['period'], scenario=scenario,
            review={'reviewed_by':'isolated-test-operator', 'evidence':'synthetic test manifest'},
            origin={'kind':'historical-local','computed_at':None,'solver_commit':None,'export_commit':None})
        self.save_manifest()
        env = patch.dict(os.environ, {'BB_API_TOKEN':'synthetic-service', 'BB_HISTORICAL_REGISTRAR_TOKEN':'synthetic-registrar',
            'BB_ENGINE_REMOTE_ENABLED':'1', 'BB_ENGINE_PROFILE_REGISTRY':str(self.root/'profiles.json'),
            'BB_HISTORICAL_ARTIFACTS':str(self.root/'manifest.json'), 'BB_HISTORICAL_DB':str(self.root/'historical.sqlite3'),
            'BB_JOB_DB':str(self.root/'jobs.sqlite3')})
        env.start(); self.addCleanup(env.stop)

    def save_manifest(self, extra=None):
        self.write('manifest.json', {'schema_version':'bb-historical-artifacts/1.0', 'artifacts':{'reviewed':self.entry, **(extra or {})}})

    def post(self, headers=None, body=None):
        return self.client.post(self.url, headers=self.admin if headers is None else headers, json={'artifact_id':'reviewed'} if body is None else body)

    def count(self):
        p = self.root/'historical.sqlite3'
        if not p.exists(): return 0
        with sqlite3.connect(p) as con:
            return con.execute('SELECT count(*) FROM historical_results').fetchone()[0]

    def test_registration_and_read_preserve_bytes_status_and_unknown_origin(self):
        response = self.post(); self.assertEqual(response.status_code, 201)
        receipt = response.json(); self.assertTrue(receipt['registration_id'].startswith('hist_'))
        self.assertIsNone(receipt['origin']['computed_at']); self.assertIsNone(receipt['origin']['solver_commit'])
        read = self.client.get(self.url+'/'+receipt['registration_id'], headers=self.headers)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.json()['result_json'].encode(), (self.root/'result.json').read_bytes())
        self.assertEqual(json.loads(read.json()['result_json']), self.result)
        self.assertNotIn('status', receipt); self.assertNotIn('job_id', receipt)
        self.assertFalse((self.root/'jobs.sqlite3').exists())
        self.assertEqual((self.root/'historical.sqlite3').stat().st_mode & 0o777,0o600)

    def test_unauthenticated_and_gateway_only_cannot_register(self):
        self.assertEqual(self.post(headers={}).status_code, 401)
        self.assertEqual(self.post(headers=self.headers).status_code, 403)
        self.assertEqual(self.post(headers={**self.admin, 'X-BB-Job-Owner':'org:other'}).status_code, 404)
        self.assertEqual(self.count(), 0)

    def test_read_denies_missing_session_wrong_service_and_other_owner(self):
        rid = self.post().json()['registration_id']
        for headers, status in [({},401), ({**self.headers,'Authorization':'Bearer wrong'},401),
                                ({**self.headers,'X-BB-Job-Owner':'org:other'},404)]:
            self.assertEqual(self.client.get(self.url+'/'+rid, headers=headers).status_code,status)

    def test_no_local_unauthenticated_bypass(self):
        with patch.dict(os.environ, {'BB_API_TOKEN':''}):
            self.assertEqual(self.client.get(self.url+'/hist_'+'a'*32, headers=self.headers).status_code,401)
            self.assertEqual(self.post().status_code,401)

    def test_registrar_must_be_configured_separately(self):
        for value in ('', 'synthetic-service'):
            with patch.dict(os.environ, {'BB_HISTORICAL_REGISTRAR_TOKEN':value}):
                self.assertEqual(self.post().status_code,503)
        self.assertEqual(self.count(),0)

    def test_client_cannot_attest_hash_owner_status_or_path(self):
        for key in ('trusted','business_id','input_hash','profile_hash','source_file','review','result'):
            self.assertEqual(self.post(body={'artifact_id':'reviewed',key:'client-claim'}).status_code,422)
        self.assertEqual(self.count(),0)

    def test_changed_file_rejected_atomically(self):
        for name in ('source.xlsx','input.json','result.json'):
            before=(self.root/name).read_bytes();self.write(name,before+b' ')
            self.assertEqual(self.post().status_code,422);self.assertEqual(self.count(),0)
            self.write(name,before)

    def test_wrong_manifest_period_rejected(self):
        self.entry['period']['end']='2026-06-08';self.save_manifest()
        self.assertEqual(self.post().status_code,422);self.assertEqual(self.count(),0)

    def test_wrong_profile_rejected(self):
        self.profile['profile_id']='wrong-reviewed-profile';self.write('profile.json',self.profile)
        self.assertEqual(self.post().status_code,422);self.assertEqual(self.count(),0)

    def test_input_change_cannot_bypass_profile_checks_with_updated_hash(self):
        self.raw['customer_needs'][0]['customer_id']='another-customer';self.write('input.json',self.raw)
        self.entry['input_file']['sha256']=sha256((self.root/'input.json').read_bytes()).hexdigest()
        self.entry['input_hash']=digest(self.raw);self.save_manifest()
        response=self.post();self.assertEqual(response.status_code,422);self.assertEqual(self.count(),0)
        self.assertNotIn('another-customer',response.text)

    def test_changed_domain_rejected_even_if_manifest_file_hash_updated(self):
        self.result['placement_domain_contract']['needs'][0]['start_intervals'][0]['latest']='2026-05-11T23:00+02:00'
        self.write('result.json',self.result)
        self.entry['result_file']['sha256']=sha256((self.root/'result.json').read_bytes()).hexdigest();self.save_manifest()
        self.assertEqual(self.post().status_code,422);self.assertEqual(self.count(),0)

    def test_duplicates_aliases_and_concurrent_requests_share_one_record(self):
        self.save_manifest({'alias':deepcopy(self.entry)})
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:self.post(),range(4)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,200,200,201])
        self.assertEqual(len({r.json()['registration_id'] for r in responses}),1)
        alias=self.post(body={'artifact_id':'alias'})
        self.assertEqual(alias.status_code,200);self.assertEqual(alias.json(),responses[0].json())
        self.assertEqual(self.count(),1)

    def test_conflicting_origin_for_same_artifact_is_not_another_registration(self):
        first=self.post().json()
        self.entry['origin']['solver_commit']='a'*40;self.save_manifest()
        self.assertEqual(self.post().status_code,409);self.assertEqual(self.count(),1)
        read=self.client.get(self.url+'/'+first['registration_id'],headers=self.headers)
        self.assertIsNone(read.json()['origin']['solver_commit'])

    def test_read_survives_source_removal_but_not_corrupt_storage(self):
        rid=self.post().json()['registration_id'];(self.root/'result.json').unlink()
        self.assertEqual(self.client.get(self.url+'/'+rid,headers=self.headers).status_code,200)
        with sqlite3.connect(self.root/'historical.sqlite3') as con:
            con.execute('UPDATE historical_results SET result_bytes=?',(b'{}',))
        self.assertEqual(self.client.get(self.url+'/'+rid,headers=self.headers).status_code,503)

    def test_removed_workspace_binding_revokes_read(self):
        rid=self.post().json()['registration_id']
        self.registry['workspaces']={};self.write('profiles.json',self.registry)
        self.assertEqual(self.client.get(self.url+'/'+rid,headers=self.headers).status_code,403)

    def test_job_database_cannot_be_used_for_receipts(self):
        with patch.dict(os.environ, {'BB_HISTORICAL_DB':str(self.root/'jobs.sqlite3')}):
            self.assertEqual(self.post().status_code,503)
        self.assertFalse((self.root/'jobs.sqlite3').exists())


class ActualFloraTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('BB_FLORA_HISTORICAL_DIR'), 'Private Flora is opt-in')
    def test_actual_registration_and_read_without_solver_or_source_mutation(self):
        root=Path(os.environ['BB_FLORA_HISTORICAL_DIR'])
        raw=json.loads((root/'input/engine-input.json').read_bytes())
        profile=json.loads((root/'input/profile.json').read_bytes())
        source=(root/'input/flora_3_motorunderlag_2026-10-24.xlsx').read_bytes()
        result=(root/'output/result-with-domains.json').read_bytes()
        # Reviewed 10B identities, not trust inferred from arbitrary supplied files.
        self.assertEqual(sha256(source).hexdigest(),'19e777012ea1e5df4c53d08258386e96aba9f645d001cf2b13c1a15e05ba22f7')
        self.assertEqual(digest(raw),'0d6f1b548b9b35207334ede7749e2d8ac8ee38373da58e70e97290c8b5cf68c8')
        self.assertEqual(digest(profile),'264b72d35b606a8b8c0583383d992dfc3ca513b0f73b0a222d5dcb347eda2794')
        self.assertEqual(sha256(result).hexdigest(),'544604b39b8794b5278ca1cd235cd8be1a7cd38a61eb8a9cc514b95b56fea7c4')
        harness=HistoricalResultsTest();harness.setUp()
        self.addCleanup(harness.doCleanups)
        harness.configure(raw,profile,result,source,{})
        # Use the original files, including their exact serialization, for the
        # actual registration. Synthetic negatives stay on separate copies.
        for key,name,expected in (
            ('source_file','input/flora_3_motorunderlag_2026-10-24.xlsx','19e777012ea1e5df4c53d08258386e96aba9f645d001cf2b13c1a15e05ba22f7'),
            ('input_file','input/engine-input.json','a518d42700e4cd70c34f905425af5ce9a5f51bce3836a608295a6116068f48c3'),
            ('result_file','output/result-with-domains.json','544604b39b8794b5278ca1cd235cd8be1a7cd38a61eb8a9cc514b95b56fea7c4')):
            harness.entry[key]={'path':str(root/name),'sha256':expected}
        harness.registry['workspaces'][harness.owner]['profile_path']=str(root/'input/profile.json')
        harness.write('profiles.json',harness.registry)
        harness.entry['review']={'reviewed_by':'isolated-test-operator','evidence':'Approved D1 and Etapp 10B exact historical identities'}
        harness.entry['origin'].update(solver_commit='724216913985158b9f4a16fa18c71d5b60ea1e49',export_commit='3ce17ef88800750f4814de1b9dbd4abc11bbc028')
        harness.save_manifest()
        harness.headers['X-BB-Job-Owner']=harness.owner;harness.admin['X-BB-Job-Owner']=harness.owner
        registered=harness.post();self.assertEqual(registered.status_code,201,'Private registration failed; no payload logged')
        read=harness.client.get(harness.url+'/'+registered.json()['registration_id'],headers=harness.headers)
        self.assertEqual(read.status_code,200)
        self.assertEqual(sha256(read.json()['result_json'].encode()).hexdigest(),sha256(result).hexdigest())
        self.assertEqual(sha256((root/'output/result-with-domains.json').read_bytes()).hexdigest(),sha256(result).hexdigest())
        self.assertFalse((harness.root/'jobs.sqlite3').exists())
        evidence=os.environ.get('BB_HISTORICAL_TEST_RECEIPT')
        if evidence:
            target=Path(evidence)
            with target.open('w',encoding='utf-8') as f:json.dump(read.json(),f,ensure_ascii=False)
            target.chmod(0o600)
