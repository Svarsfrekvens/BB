"""Pure grouping and authenticated read-only checks. Never create a job/database/model."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from bb.api import app
from bb.flora_jobs import digest
from bb.flora.grouping import occasions, global_limit, VERIFIED, UNVERIFIED
from bb.flora.daily_rest import assess


def sample(rows):
    return dict(origin='2026-05-11T00:00', horizon=2880,
                config={'min_daily_rest':660,'known_from':0,'known_to':2880},
                staff=[{'id':'a'}], references={'import':{'segments':rows}},
                daily_rest_parameters={'period_id':'P2','boundaries':[{'person_id':'a','period_id':'P2','minute_of_day':0}]})


def row(key, start, end, code='Ar', **kw):
    return dict(id=key, person='a', start=start, end=end, code=code, **kw)


class GroupingSafety(unittest.TestCase):
    def test_source_cell_is_not_evidence_and_unknown_propagates(self):
        rows=[row('cell-1',0,360,'Jo'),row('cell-2',360,1440)]
        case=sample(rows)
        groups=occasions(case, {'segments':rows})
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['grouping_status'],UNVERIFIED)
        report=assess(case, {'segments':rows})
        self.assertEqual(report['status'],'UNKNOWN')
        for field in ('night_jour_status','max_24h_status','compensation_status'):
            self.assertEqual(report['conditional_jour_duties'][0][field],'UNKNOWN')

    def test_explicit_membership_must_be_complete_and_unchanged(self):
        rows=[row('cell-1',0,360,'Jo',whole_duty_id='G01'),row('cell-2',360,1440,whole_duty_id='G01')]
        case=sample(rows)
        self.assertEqual(occasions(case,{'segments':rows})[0]['grouping_status'],VERIFIED)
        for altered in [rows[:1], [dict(rows[0],start=1),rows[1]], [dict(r,person='b') for r in rows]]:
            self.assertTrue(all(g['grouping_status']==UNVERIFIED for g in occasions(case,{'segments':altered})))

    def test_client_label_and_nearby_times_cannot_prove_group(self):
        rows=[row('x',0,60),row('y',60,120)]
        self.assertEqual(len(occasions(sample([]),{'segments':[dict(r,whole_duty_id='G01') for r in rows]})),2)
        self.assertTrue(all(g['grouping_status']==UNVERIFIED for g in occasions(sample([]),{'segments':rows})))

    def test_global_limit_needs_versioned_selection(self):
        case=sample([]);case['config']['max_whole_duty_minutes']=1440
        self.assertIsNone(global_limit(case))
        case['rule_policy']={'version':'bb-shared-principles/1.0','planning_limits':{'status':'NOT_SELECTED','decision':{'max_whole_duty_minutes':1440,'source':'synthetic test only','confirmed_at':'2026-10-28'}}}
        self.assertIsNone(global_limit(case))
        case['rule_policy']['planning_limits']['status']='SELECTED'
        self.assertEqual(global_limit(case),1440)


class AttestationSafety(unittest.TestCase):
    def test_mounted_bytes_and_allowlist_with_auth_and_contract(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'profile.json';r=Path(tmp)/'registry.json'
            profile=dict(schema_version='bb-analysis-input-profile/1.0',profile_id='p',business_id='b',data_use='development',
                         review_provenance={'source':'synthetic','reviewed_at':'2026-10-28'},source={'raw_workbook_sha256':'a'*64},
                         period_id='P2',applicable_periods=[{'id':'P2','start':'2026-05-11','end':'2026-06-07'}],
                         private_data='NEVER_RETURN_THIS')
            p.write_text(json.dumps(profile));period={**profile['applicable_periods'][0],'timezone':'Europe/Stockholm'}
            contract=dict(version='bb-request-binding/1.0',source_file_sha256='a'*64,dataset_id='d',business_id='b',profile_id='p',profile_hash=digest(profile),data_use='development',schema_version='flora-bb-input/1.0',period=period)
            registry=dict(schema_version='bb-business-profiles/1.0',workspaces={'org:b':dict(business_id='b',data_use='development',profile_path=str(p),dataset_profiles={'d':str(p)},request_contracts={'d':contract})})
            r.write_text(json.dumps(registry))
            with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic','BB_ENGINE_PROFILE_REGISTRY':str(r),'RENDER_GIT_COMMIT':'test-commit'}), patch('bb.engine_api.get_manager',side_effect=AssertionError('manager forbidden')), patch('sqlite3.connect',side_effect=AssertionError('database forbidden')):
                client=TestClient(app)
                url='/api/engine/profile-attestation?dataset_id=d';headers={'Authorization':'Bearer synthetic','X-BB-Job-Owner':'org:b'}
                self.assertEqual(client.get(url).status_code,401)
                self.assertEqual(client.get(url,headers={'Authorization':'Bearer synthetic'}).status_code,403)
                response=client.get(url,headers=headers)
                self.assertEqual(response.status_code,200)
                data=response.json()
                self.assertEqual(data['profile_file_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
                self.assertEqual(data['profile_hash'],digest(profile))
                self.assertEqual(set(data),{'schema_version','profile_file_sha256','profile_hash','profile_id','business_id','dataset_id','period','data_use','motor_commit','contract_version'})
                self.assertNotIn('NEVER_RETURN_THIS',response.text)
                self.assertEqual(client.get(url,headers={**headers,'X-BB-Job-Owner':'org:wrong'}).status_code,422)
                self.assertEqual(client.get('/api/engine/profile-attestation?dataset_id=unknown',headers=headers).status_code,422)
                # Exercise the real HTTP auth/router/normalizer/binding with a stop
                # at the next pure precheck. No manager or persistence is entered.
                from fastapi import HTTPException
                md={k:copy.deepcopy(v) for k,v in contract.items() if k!='version'}
                md.update(timezone=period['timezone'],periods=profile['applicable_periods'])
                body={'input':{'metadata':md,'staff':[],'customers':[],'schedule_segments':[], 'customer_needs':[],'business_rules':[]}}
                codes={'source_file_sha256':'SOURCE_FILE_SHA_MISMATCH','dataset_id':'DATASET_MISMATCH',
                       'business_id':'BUSINESS_MISMATCH','profile_id':'PROFILE_UNKNOWN', 'profile_hash':'PROFILE_HASH_MISMATCH',
                       'data_use':'DATA_USE_MISMATCH','schema_version':'SCHEMA_VERSION_UNSUPPORTED','period':'PERIOD_MISMATCH'}
                with patch('bb.engine_methods.prepare',side_effect=HTTPException(598,'LOCAL_NEXT_PRECHECK_ONLY')) as precheck:
                    for field,code in codes.items():
                        for missing in (False,True):
                            changed=copy.deepcopy(body)
                            if missing: changed['input']['metadata'].pop(field)
                            else: changed['input']['metadata'][field]='wrong'
                            response=client.post('/api/engine/jobs',json=changed,headers=headers)
                            self.assertEqual(response.status_code,422,(field,missing,response.text))
                            self.assertEqual(response.json()['detail']['code'],code)
                    changed=copy.deepcopy(body);changed['metadata']={'observations':[{'expectedProfileHash':'wrong'}]}
                    response=client.post('/api/engine/jobs',json=changed,headers=headers)
                    self.assertEqual(response.json()['detail']['code'],'PROFILE_HASH_MISMATCH')
                    self.assertEqual(client.post('/api/engine/jobs',json=body).status_code,401)
                    self.assertEqual(precheck.call_count,0)
                    self.assertEqual(client.post('/api/engine/jobs',json=body,headers=headers).status_code,598)
                    self.assertEqual(precheck.call_count,1)
                registry['workspaces']['org:b'].pop('request_contracts');r.write_text(json.dumps(registry))
                self.assertEqual(client.get(url,headers=headers).status_code,503)


if __name__=='__main__':
    unittest.main()
