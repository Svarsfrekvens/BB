"""Three synthetic businesses exercise the actual import, solver and validator."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from bb.api import app
from bb.flora_jobs import JobStore, digest, run_worker
from bb.flora_import import prepare_case
from test_flora_import import sample
from test_flora_method import fixture


def business_sample(business, duration=30, boundary='03:00'):
    raw, profile = sample();raw.pop('source_archive')
    raw['metadata'].update(schema_version='bb-input/1.0',business_id=business,data_use='development')
    periods=[dict(id='history',start='2026-04-13',end='2026-05-10'),dict(id='next',start='2026-05-11',end='2026-06-07')]
    raw['metadata']['periods']=periods
    for row,day in zip(raw['schedule_segments'],['2026-05-10','2026-05-11','2026-05-12']):
        row['start']=day+row['start'][10:];row['end']=day+row['end'][10:]
    raw['customer_needs'][0].update(date='2026-05-11',duration_minutes=duration)
    profile.update(business_id=business,data_use='development',profile_id=business+'-reviewed',
                   review_provenance={'source':'synthetic-reviewed-decisions','reviewed_at':'2026-10-18'},
                   applicable_periods=deepcopy(periods),config=deepcopy(fixture()['config']))
    profile['candidate_windows'][0]['date']='2026-05-11'
    body=dict(input=raw,seconds=1,scenario={'absence_mode':'preserve','workspace':{'unit_rules':{
        'day_boundaries':{'next':{'person-a':{'time':boundary,'confirmed_at':'2026-10-18','source':business+' decision'}}}}}})
    return body,profile


class BusinessEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.registry={'schema_version':'bb-business-profiles/1.0','workspaces':{}}
        self.bodies={};self.profiles={}
        for business,duration,boundary in [('unit-a',20,'03:00'),('unit-b',30,'07:00'),('unit-c',40,'21:00')]:
            body,profile=business_sample(business,duration,boundary)
            path=self.root/(business+'.json');path.write_text(json.dumps(profile))
            self.bodies[business]=body;self.profiles[business]=profile
            self.registry['workspaces']['org:'+business]=dict(business_id=business,data_use='development',profile_path=str(path))
        self.registry_path=self.root/'registry.json';self.save_registry()
        self.store=JobStore(self.root/'jobs.sqlite3');self.manager=Mock(store=self.store)
        self.env=patch.dict(os.environ,{'BB_API_TOKEN':'test-token','BB_ENGINE_PROFILE_REGISTRY':str(self.registry_path),'BB_ENGINE_REMOTE_ENABLED':'1'});self.env.start()
        self.manager_patch=patch('bb.engine_api.get_manager',return_value=self.manager);self.manager_patch.start()
        self.client=TestClient(app)

    def tearDown(self):
        self.client.close();self.manager_patch.stop();self.env.stop();self.temp.cleanup()
    def save_registry(self):self.registry_path.write_text(json.dumps(self.registry))
    def headers(self,business='unit-a'):
        return {'Authorization':'Bearer test-token','X-BB-Job-Owner':'org:'+business}
    def submit(self,business='unit-a',body=None,extra=None):
        return self.client.post('/api/engine/jobs',json=body or self.bodies[business],headers={**self.headers(business),**(extra or {})})

    def test_three_businesses_run_real_engine_and_keep_results_separate(self):
        before=deepcopy(self.bodies);jobs={}
        for business in self.bodies:
            response=self.submit(business);self.assertEqual(response.status_code,202,response.text)
            job=response.json();jobs[business]=job['id']
            duplicate=self.submit(business).json();self.assertEqual(duplicate['id'],job['id']);self.assertTrue(duplicate['deduplicated'])
            job_id,lease=self.store.claim();run_worker(str(self.store.path),job_id,lease)
            result=self.client.get('/api/engine/jobs/'+job_id,headers=self.headers(business)).json()
            self.assertEqual(result['status'],'succeeded',result);output=result['result']
            self.assertEqual(output['after']['fully_covered_needs'],1)
            self.assertEqual(output['validation']['checked_status'],'PASS')
            self.assertEqual(output['validation']['overall'],'UNKNOWN')
            self.assertFalse(output['business_schedule_approved'])
            self.assertEqual(output['provenance']['engine_context']['business_id'],business)
            self.assertFalse(output['provenance']['automatic_learning'])
            self.assertEqual(output['rule_policy']['business_id'],business)
            self.assertEqual(output['rule_policy']['version'],'bb-shared-principles/1.0')
            self.assertEqual(output['rule_policy']['planning_limits']['status'],'NOT_SELECTED')
            submitted=self.client.get('/api/engine/jobs/'+job_id+'/submitted-source',headers=self.headers(business))
            self.assertEqual(submitted.status_code,200,submitted.text)
            saved=submitted.json()
            self.assertEqual(saved['request']['input'],self.bodies[business]['input'])
            self.assertEqual(saved['input_hash'],digest(saved['request']['input']))
            self.assertEqual(saved['profile_hash'],output['provenance']['profile_hash'])
            self.assertFalse(saved['business_schedule_approved'])
            expected=self.bodies[business]['scenario']['workspace']['unit_rules']['day_boundaries']['next']['person-a']['time']
            self.assertEqual(output['daily_rest_parameters']['boundaries'][0]['time'],expected)
            certificate=output['validation']['certificates']['daily_rest_24h.json']
            self.assertEqual(certificate['version'],'fixed-daily-rest/1.0')
            self.assertEqual({w['person_id'] for w in certificate['windows']},{'person-a'})
            self.assertTrue(all(w['start'].endswith(expected) for w in certificate['windows']))
            self.assertFalse(certificate['other_business_decisions_inherited'])
            foreign=self.client.get('/api/engine/jobs/'+job_id,headers=self.headers('unit-b' if business!='unit-b' else 'unit-c'))
            self.assertEqual(foreign.status_code,404)
            self.assertEqual(self.client.get('/api/engine/jobs/'+job_id+'/submitted-source',headers=self.headers('unit-b' if business!='unit-b' else 'unit-c')).status_code,404)
            self.assertEqual(self.client.get('/api/flora/jobs/'+job_id,headers=self.headers(business)).status_code,404)
        self.assertEqual(len(set(jobs.values())),3);self.assertEqual(before,self.bodies)
        for business in self.profiles:
            self.assertEqual(json.loads((self.root/(business+'.json')).read_text()),self.profiles[business])

    def test_submitted_source_rejects_changed_saved_input_without_returning_rows(self):
        job_id=self.submit().json()['id']
        self.assertEqual(self.client.get('/api/engine/jobs/'+job_id+'/submitted-source',headers=self.headers()).status_code,503)
        claimed,lease=self.store.claim();self.assertEqual(claimed,job_id)
        run_worker(str(self.store.path),job_id,lease)
        with self.store.connect() as con:
            row=con.execute('SELECT request_json FROM jobs WHERE id=?',(job_id,)).fetchone()
            changed=json.loads(row['request_json']);changed['input']['customer_needs'][0]['duration_minutes']=999
            con.execute('UPDATE jobs SET request_json=? WHERE id=?',(json.dumps(changed),job_id))
        response=self.client.get('/api/engine/jobs/'+job_id+'/submitted-source',headers=self.headers())
        self.assertEqual(response.status_code,503)
        self.assertNotIn('customer_needs',response.text)

    def test_pass_preflight_reads_current_profile_without_solving_or_exposing_it(self):
        job_id=self.submit().json()['id']
        claimed,lease=self.store.claim();self.assertEqual(claimed,job_id)
        run_worker(str(self.store.path),job_id,lease)
        url='/api/engine/jobs/'+job_id+'/pass-preflight'
        with patch('bb.engine_methods.solve',side_effect=AssertionError('solver must not run')):
            response=self.client.get(url,headers=self.headers())
        self.assertEqual(response.status_code,200,response.text)
        report=response.json()
        self.assertEqual(report['schema_version'],'bb-engine-pass-preflight/1.0')
        self.assertTrue(report['current_profile_matches_saved_job'])
        self.assertEqual(sum(report['possible_pass_evidence'].values())+report['source_rows_excluded'],
                         report['source_rows_in_period'])
        self.assertEqual(len(report['unverified_source_segment_ids']),
                         report['possible_pass_evidence']['unverified'])
        self.assertEqual(len(set(report['unverified_source_segment_ids'])),
                         len(report['unverified_source_segment_ids']))
        self.assertFalse(report['future_result_guaranteed'])
        self.assertFalse(report['transfer_approved'])
        self.assertNotIn('segment_decisions',response.text)
        self.assertEqual(self.client.get(url,headers=self.headers('unit-b')).status_code,404)
        self.assertEqual(self.client.get(url).status_code,401)

    def test_job_build_commit_is_recorded_only_when_render_provides_a_full_hash(self):
        with patch.dict(os.environ,{'RENDER_GIT_COMMIT':'a'*40}):
            job=self.submit().json()
        self.assertEqual(job['build_commit'],'a'*40)
        read=self.client.get('/api/engine/jobs/'+job['id'],headers=self.headers())
        self.assertEqual(read.status_code,200)
        self.assertEqual(read.json()['build_commit'],'a'*40)

    def test_job_does_not_run_under_a_different_build_commit(self):
        with patch.dict(os.environ,{'RENDER_GIT_COMMIT':'a'*40}):
            job=self.submit().json()
        job_id,lease=self.store.claim()
        self.assertEqual(job_id,job['id'])
        with patch.dict(os.environ,{'RENDER_GIT_COMMIT':'b'*40}):
            run_worker(str(self.store.path),job_id,lease)
        read=self.client.get('/api/engine/jobs/'+job_id,headers=self.headers())
        self.assertEqual(read.status_code,200)
        saved=read.json()
        self.assertEqual(saved['status'],'failed')
        self.assertEqual(saved['error']['code'],'BUILD_CHANGED')
        self.assertIsNone(saved['result'])

    def test_client_cannot_choose_foreign_profile_or_override_context(self):
        self.assertEqual(self.submit('unit-a',self.bodies['unit-b']).status_code,422)
        body=deepcopy(self.bodies['unit-a']);body['profile_path']='/tmp/anything';body['engine_context']={'business_id':'unit-b'}
        response=self.submit(body=body);self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['engine_context']['business_id'],'unit-a')
        body['input']['metadata']['data_use']='operational';self.assertEqual(self.submit(body=body).status_code,422)

    def test_no_flora_fallback_or_foreign_business_profile(self):
        r=self.client.post('/api/engine/jobs',json=self.bodies['unit-a'],headers=self.headers('unknown'))
        self.assertEqual(r.status_code,503);self.assertEqual(r.json()['detail']['code'],'BUSINESS_PROFILE_REQUIRED')
        self.registry['workspaces']['org:unit-a']['profile_path']=str(self.root/'unit-b.json');self.save_registry()
        self.assertEqual(self.submit().json()['detail']['code'],'PROFILE_BINDING_MISMATCH');self.assertFalse(self.manager.wake.called)

    def test_missing_or_changed_inputs_fail_before_queue(self):
        for field in ('staff','schedule_segments','customer_needs'):
            body=deepcopy(self.bodies['unit-a']);body['input'][field].pop()
            r=self.submit(body=body);self.assertEqual(r.status_code,422,r.text)
        body=deepcopy(self.bodies['unit-a']);body['input']['metadata']['periods'][1]['end']='2026-06-08'
        self.assertEqual(self.submit(body=body).status_code,422);self.assertFalse(self.manager.wake.called)

    def test_new_duration_uses_upload_not_prior_example(self):
        body=deepcopy(self.bodies['unit-a']);body['input']['customer_needs'][0]['duration_minutes']=45
        case=prepare_case(body['input'],self.profiles['unit-a'],body['scenario']);self.assertEqual(case['needs'][0]['duration'],45)
        first=self.submit().json();second=self.submit(body=body).json()
        self.assertNotEqual(first['id'],second['id']);self.assertNotEqual(first['input_hash'],second['input_hash'])

    def test_reviewed_dataset_variant_preserves_default_and_checks_uploaded_rows(self):
        variant=deepcopy(self.profiles['unit-a']);variant['profile_id']='unit-a-original'
        path=self.root/'unit-a-original.json';path.write_text(json.dumps(variant))
        self.registry['workspaces']['org:unit-a']['dataset_profiles']={'ORIGINAL':str(path)}
        self.save_registry()
        original=deepcopy(self.bodies['unit-a']);original['input']['metadata']['dataset_id']='ORIGINAL'
        response=self.submit(body=original);self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(response.json()['engine_context']['profile_id'],'unit-a-original')
        self.assertEqual(self.submit().json()['engine_context']['profile_id'],'unit-a-reviewed')
        original['input']['schedule_segments'].pop()
        self.assertEqual(self.submit(body=original).status_code,422)

    def test_dataset_variant_cannot_cross_business_or_take_client_path(self):
        binding=self.registry['workspaces']['org:unit-a']
        binding['dataset_profiles']={'ORIGINAL':str(self.root/'unit-b.json')};self.save_registry()
        body=deepcopy(self.bodies['unit-a']);body['input']['metadata']['dataset_id']='ORIGINAL'
        response=self.submit(body=body)
        self.assertEqual(response.json()['detail']['code'],'PROFILE_BINDING_MISMATCH')
        binding['dataset_profiles']={'ORIGINAL':'relative.json'};self.save_registry()
        self.assertEqual(self.submit(body=body).json()['detail']['code'],'PROFILE_CONFIGURATION_INVALID')

    def test_reviewed_boundaries_survive_fresh_import_without_overwriting_explicit_choice(self):
        body=deepcopy(self.bodies['unit-a']);profile=deepcopy(self.profiles['unit-a'])
        reviewed=body['scenario']['workspace']['unit_rules'].pop('day_boundaries')
        profile['reviewed_day_boundaries']=reviewed
        before=deepcopy(body)
        case=prepare_case(body['input'],profile,body['scenario'])
        self.assertEqual(case['daily_rest_parameters']['boundaries'][0]['time'],'03:00')
        self.assertEqual(body,before)
        body['scenario']['workspace']['unit_rules']['day_boundaries']={}
        case=prepare_case(body['input'],profile,body['scenario'])
        self.assertEqual(case['daily_rest_parameters']['missing_person_ids'],['person-a'])
        body['scenario']['workspace']['unit_rules']['day_boundaries']=deepcopy(reviewed)
        body['scenario']['workspace']['unit_rules']['day_boundaries']['next']['person-a']['time']='07:00'
        case=prepare_case(body['input'],profile,body['scenario'])
        self.assertEqual(case['daily_rest_parameters']['boundaries'][0]['time'],'07:00')

    def test_capabilities_private_and_readiness_checks_file(self):
        self.assertEqual(self.client.get('/api/engine/capabilities').status_code,401)
        self.assertEqual(self.client.get('/api/engine/capabilities',headers={'Authorization':'Bearer test-token'}).status_code,403)
        output=self.client.get('/api/engine/capabilities',headers=self.headers()).json()
        self.assertEqual(output['shared_principles']['version'],'bb-shared-principles/1.0')
        self.assertEqual(output['profile_status'],'CONFIGURED_INPUT_REVIEW_REQUIRED')
        self.assertNotIn(str(self.root),json.dumps(output));self.assertNotIn('unit-b',json.dumps(output))
        (self.root/'unit-a.json').unlink()
        output=self.client.get('/api/engine/capabilities',headers=self.headers()).json()
        self.assertEqual(output['profile_status'],'NOT_CONFIGURED');self.assertEqual(self.submit().status_code,503)
        self.assertEqual(self.submit('unit-b').status_code,202)

    def test_purpose_change_hides_development_job(self):
        job=self.submit().json();self.registry['workspaces']['org:unit-a']['data_use']='operational';self.save_registry()
        self.assertEqual(self.client.get('/api/engine/jobs/'+job['id'],headers=self.headers()).status_code,404)

    def test_changed_profile_does_not_reuse_old_job(self):
        first=self.submit(extra={'Idempotency-Key':'test'}).json()
        profile=self.profiles['unit-a'];profile['review_provenance']['source']='new review'
        (self.root/'unit-a.json').write_text(json.dumps(profile))
        self.assertEqual(self.submit(extra={'Idempotency-Key':'test'}).status_code,409)
        self.assertNotEqual(first['id'],self.submit().json()['id'])

    def test_unreviewed_profile_and_embedded_result_rejected(self):
        profile=deepcopy(self.profiles['unit-a']);profile.pop('review_provenance')
        (self.root/'unit-a.json').write_text(json.dumps(profile));self.assertEqual(self.submit().status_code,503)
        profile=self.profiles['unit-a'];profile['solution']={'copied_result':True}
        (self.root/'unit-a.json').write_text(json.dumps(profile));self.assertEqual(self.submit().status_code,422)

    def test_shared_input_cannot_fall_back_through_legacy_route(self):
        response=self.client.post('/api/flora/jobs',json=self.bodies['unit-a'],headers=self.headers())
        self.assertEqual(response.status_code,422)
        self.assertIn('/api/engine/jobs',response.text)

    def test_remote_feature_flag_is_independent_of_flora(self):
        from bb.engine_api import verified_owner
        from fastapi import HTTPException
        request=Mock();request.client.host='203.0.113.10';request.headers=self.headers()
        with patch.dict(os.environ,{'BB_ENGINE_REMOTE_ENABLED':'0','BB_FLORA_REMOTE_ENABLED':'1'}):
            with self.assertRaises(HTTPException) as exc:verified_owner(request)
            self.assertEqual(exc.exception.status_code,403)


class StartupTests(unittest.TestCase):
    def test_failed_flora_installer_does_not_block_other_businesses_or_leak_output(self):
        from bb.startup import bootstrap_legacy_profile
        with patch.dict(os.environ,{'BB_FLORA_PROFILE':'/private/profile.json'}), patch('bb.startup.Path.is_file',return_value=True), patch('bb.startup.subprocess.run',return_value=Mock(returncode=1,stdout='SECRET',stderr='SECRET')), patch('builtins.print') as log:
            bootstrap_legacy_profile();self.assertNotIn('SECRET',str(log.call_args_list));self.assertIn('failed',str(log.call_args_list))

class LegacyReadinessTests(unittest.TestCase):
    def test_missing_profile_is_not_ready_just_because_path_is_set(self):
        from bb.flora_api import capabilities
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'missing.json'
            with patch.dict(os.environ,{'BB_FLORA_PROFILE':str(path)}):
                self.assertFalse(capabilities()['profile_configured'])
                path.write_text('{"schema_version":"bb-analysis-input-profile/1.0"}')
                self.assertTrue(capabilities()['profile_configured'])
                path.write_text('{"schema_version":"wrong"}')
                self.assertFalse(capabilities()['profile_configured'])
