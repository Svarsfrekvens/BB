"""Bounded check runner: no network, solver, subprocess, SQLite or job manager."""
import argparse,contextlib,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ortools.sat.python import cp_model
from fastapi.testclient import TestClient
from bb.api import app
from bb.flora_jobs import normalize_request, JobStore
from bb.engine_methods import prepare
from test_business_engine import business_sample


def probes():
    body,profile=business_sample('synthetic-window')
    registry={'schema_version':'bb-business-profiles/1.0','workspaces':{'org:synthetic-window':{
        'business_id':'synthetic-window','data_use':'development','profile_path':'/synthetic/profile.json',
        'dataset_profiles':{'SYNTHETIC':'/synthetic/profile.json'}}}}
    def read(path,label):
        from copy import deepcopy
        return deepcopy(registry if path=='/synthetic/registry.json' else profile)
    from copy import deepcopy
    def md(k,v):return lambda b:b['input']['metadata'].update({k:v})
    cases=[('valid_body_guard',lambda b:None),('business_id',md('business_id','foreign')),
           ('data_use',md('data_use','operational')),('schema_version',md('schema_version','unknown')),
           ('period',lambda b:b['input']['metadata']['periods'][1].update(end='2026-06-08')),
           ('file_sha_legacy',md('source_file_sha256','b'*64)),('dataset_legacy',md('dataset_id','unknown')),
           ('profile_claim_legacy',md('profile_id','client-cannot-select')),
           ('profile_hash_claim_legacy',md('profile_hash','b'*64))]
    result=[]
    with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic-token','BB_ENGINE_PROFILE_REGISTRY':'/synthetic/registry.json','BB_ENGINE_REMOTE_ENABLED':'1'}),patch('bb.business_profiles._read',side_effect=read):
        client=TestClient(app)
        for name,mutate in cases:
            b=deepcopy(body);mutate(b)
            # Invalid key is checked after prepare and before get_manager. No job submission.
            response=client.post('/api/engine/jobs',json=b,headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'org:synthetic-window','Idempotency-Key':'STOP/BEFORE_MANAGER'})
            result.append({'case':name,'http':response.status_code,'detail':response.json().get('detail')})
        response=client.post('/api/engine/jobs',json=body)
        result.append({'case':'missing_auth','http':response.status_code,'detail':response.json().get('detail')})
        for field,value in [('business_id','foreign'),('profile_id','')]:
            old=profile[field];profile[field]=value
            response=client.get('/api/engine/capabilities',headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'org:synthetic-window'})
            result.append({'case':'profile_binding_'+field,'http':response.status_code,'profile_status':response.json().get('profile_status'),'code':response.json().get('profile_error_code')})
            profile[field]=old
        # Public status envelope only: no JobStore constructed or SQL connection.
        for status in ['queued','running','succeeded','failed']:
            row=dict(id='a'*32,status=status,input_hash='b'*64,created_at='synthetic',started_at=None,finished_at=None,
                     error_json=None,result_json=None,method_hash=None,build_commit=None)
            assert JobStore.public(row)['status']==status
        client.close()
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--probes-only',action='store_true');a=p.parse_args()
    output=Path(a.out);output.mkdir(parents=True,exist_ok=True)
    counts={};guards=[]
    def blocked(name):
        def stop(*args,**kwargs):counts[name]=counts.get(name,0)+1;raise AssertionError('Forbidden operation: '+name)
        return stop
    with contextlib.ExitStack() as stack:
        targets=['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.flora_jobs.get_manager',
                 'bb.engine_api.get_manager','bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit',
                 'bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']
        for target in targets:
            counts[target]=0;stack.enter_context(patch(target,side_effect=blocked(target)))
        for method in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
            if hasattr(cp_model.CpSolver,method):
                key='CpSolver.'+method;counts[key]=0;stack.enter_context(patch.object(cp_model.CpSolver,method,side_effect=blocked(key)))
        report={'probes':probes()}
        if not a.probes_only:
            suite=unittest.defaultTestLoader.loadTestsFromNames(['test_typed_windows_contract','test_flora_import.ImportTest'])
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            report.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())
            from test_typed_windows_contract import flora_fixture,flora_result,availability_fixture,availability_result
            b,pf=flora_fixture();c=prepare(pf,normalize_request(b));_,out=flora_result(c)
            (output/'synthetic-flora-export.json').write_text(json.dumps({'input':b['input'],'result':out},ensure_ascii=False,indent=2)+'\n')
            b,pf=availability_fixture();c=prepare(pf,normalize_request(b));_,out=availability_result(c)
            (output/'synthetic-availability-export.json').write_text(json.dumps({'input':b['input'],'result':out},ensure_ascii=False,indent=2)+'\n')
        report['forbidden_calls']=counts
        assert not any(counts.values()),counts
        (output/'python-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        if not a.probes_only and not report['success']:raise SystemExit(1)
if __name__=='__main__':main()
