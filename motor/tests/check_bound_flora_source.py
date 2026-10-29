"""Read-only local contract proof from explicitly supplied private snapshots.

No Render access, job, solver, database or registration. Outputs containing source
rows stay in the caller's private directory; public report contains counts/hashes.
"""
import argparse,contextlib,json,os,sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from ortools.sat.python import cp_model
from bb.api import app
from bb.business_profiles import profile_for
from bb.engine_methods import prepare
from bb.flora import _normalize
from bb.flora_jobs import normalize_request,digest
from bb.availability_import import source_identity


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private',type=Path,required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    load=lambda name:json.loads((args.private/name).read_text())
    raw=load('exact-input.json');registry=load('bb-business-profiles.json');before=load('selected-profile-before.json');default=load('default-profile.json')
    pin=json.loads(Path(__file__).resolve().parents[1].joinpath('bb/flora_source_binding.json').read_text())
    owner='org:'+pin['business_id'];route=registry['workspaces'][owner]
    target=route['dataset_profiles'][pin['dataset_id']]
    def read(path,label):
        if path=='/local/registry':return deepcopy(registry)
        if path==target:return deepcopy(before)
        if path==route['profile_path']:return deepcopy(default)
        raise AssertionError('Unexpected profile lookup')
    counts={}
    def blocked(name):
        counts[name]=0
        def fail(*a,**k):counts[name]+=1;raise AssertionError('Forbidden operation: '+name)
        return fail
    results=[]
    with contextlib.ExitStack() as stack:
        for name in ['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.engine_api.get_manager','bb.flora_jobs.get_manager',
            'bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit','bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']:
            stack.enter_context(patch(name,side_effect=blocked(name)))
        for name in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
            if hasattr(cp_model.CpSolver,name):stack.enter_context(patch.object(cp_model.CpSolver,name,side_effect=blocked('CpSolver.'+name)))
        stack.enter_context(patch.dict(os.environ,{'BB_ENGINE_PROFILE_REGISTRY':'/local/registry','BB_API_TOKEN':'local-proof-token','BB_ENGINE_REMOTE_ENABLED':'1'}))
        stack.enter_context(patch('bb.business_profiles._read',side_effect=read))
        assert source_identity(raw)==pin['source_identity']
        assert raw['metadata']['source_file_sha256']==pin['source_file_sha256']
        assert 'source_layout' not in raw['metadata'] and 'history_period_id' not in raw['metadata']
        body={'input':raw};request=normalize_request(body)
        bound,profile_hash,scope,context=profile_for(owner,request)
        assert {k:v for k,v in bound.items() if k not in ['source_identity','source_file_sha256']}==before
        case=prepare(bound,request)
        # No fictitious successful schedule: this exports source evidence only.
        export=_normalize(case,{},{});basis=export['source_basis']
        assert basis['kind']=='VERIFIED_UPLOADED_ORIGINAL' and basis['verification']=='EXACT_SERVER_REVIEWED_INPUT'
        assert basis['source_identity']==pin['source_identity'] and basis['source_file_sha256']==pin['source_file_sha256']
        assert basis['segments']==[dict(segment_id=r['segment_id'],person_id=r.get('person_id'),start=r['start'],end=r['end'],code=r['source_code']) for r in raw['schedule_segments']]
        assert not export['schedule']['segments']
        for name,value in [('positive-source-basis.json',basis),('positive-source-export.json',export),('selected-profile-bound.json',bound)]:
            f=args.private/name;f.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n');f.chmod(0o600)
        mutations=[]
        def md(key,value):return lambda r:r['metadata'].__setitem__(key,value)
        for key,value in [('source_file_sha256','b'*64),('dataset_id','FOREIGN'),('business_id','foreign'),('data_use','operational'),
            ('timezone','UTC'),('planning_period_id','other'),('source_layout','invented-layout'),('history_period_id','invented-history'),('schema_version','bb-input/1.0')]:
            mutations.append((key,md(key,value)))
        mutations.extend([
            ('period',lambda r:r['metadata']['periods'][-1].__setitem__('end','2026-06-08')),
            ('segment_time',lambda r:r['schedule_segments'][0].__setitem__('end',r['schedule_segments'][0]['end'][:11]+'23:59')),
            ('segment_person',lambda r:r['schedule_segments'][0].__setitem__('person_id','foreign')),
            ('segment_code',lambda r:r['schedule_segments'][0].__setitem__('source_code','INVALID')),
            ('need_row',lambda r:r['customer_needs'][0].__setitem__('duration_minutes',999))])
        for table,key in [('staff','person_id'),('customers','customer_id'),('schedule_segments','segment_id'),('customer_needs','need_id')]:
            mutations.extend([(table+'_duplicate',lambda r,t=table:r[t].append(deepcopy(r[t][0]))),
                (table+'_missing_id',lambda r,t=table,k=key:r[t][0].pop(k)),
                (table+'_blank_id',lambda r,t=table,k=key:r[t][0].__setitem__(k,'')),
                (table+'_missing_row',lambda r,t=table:r[t].pop())])
        with TestClient(app) as client:
            headers={'Authorization':'Bearer local-proof-token','X-BB-Job-Owner':owner,'Idempotency-Key':'STOP/BEFORE_MANAGER'}
            positive=client.post('/api/engine/jobs',json=body,headers=headers)
            assert positive.status_code==422 and positive.json()['detail']=='Ogiltig körningsnyckel.'
            results.append(dict(case='correct_input_preflight',status='PASS',http=422,code='DELIBERATE_IDEMPOTENCY_STOP'))
            for name,mutate in mutations:
                changed=deepcopy(raw);mutate(changed)
                response=client.post('/api/engine/jobs',json={'input':changed},headers=headers)
                detail=response.json().get('detail')
                passed=response.status_code==422 and detail!='Ogiltig körningsnyckel.'
                code=detail.get('code') if isinstance(detail,dict) else 'REQUEST_VALIDATION'
                results.append(dict(case=name,status='PASS' if passed else 'FAIL',http=response.status_code,code=code))
            response=client.post('/api/engine/jobs',json=body)
            results.append(dict(case='missing_auth',status='PASS' if response.status_code==401 else 'FAIL',http=response.status_code,code='AUTH_REQUIRED'))
        assert not any(counts.values())
    report=dict(profile_path=target,profile_id=bound['profile_id'],base_profile_hash=digest(before),bound_profile_hash=profile_hash,
        only_added_fields=['source_identity','source_file_sha256'],source_identity=basis['source_identity'],source_file_sha256=basis['source_file_sha256'],
        source_counts={k:len(raw[k]) for k in ['staff','customers','schedule_segments','customer_needs','business_rules','vc_answers']},
        source_segments=len(basis['segments']),all_original_segments_identical=True,legacy_fields_remain_absent=True,
        no_schedule_or_solver_result_created=True,positive_basis_sha256=digest(basis),forbidden_calls=counts,results=results)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    failed=[r['case'] for r in results if r['status']!='PASS']
    print(json.dumps({'checks':len(results),'failed':failed,'source_basis_segments':len(basis['segments']),'forbidden_calls':sum(counts.values())}))
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
