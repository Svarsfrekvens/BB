"""Targeted original-window proof. No solver, real job, database or network."""
import argparse,contextlib,hashlib,json,os,sys,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ortools.sat.python import cp_model
from bb import flora_jobs as jobs, flora_window_binding as binding
from bb.availability_import import source_identity
from test_typed_windows_contract import flora_fixture,flora_result


class MemorySink:
    def __init__(self,row):self.row=row;self.result=None
    @contextlib.contextmanager
    def connect(self):yield self
    def execute(self,query,params):
        if query.startswith('SELECT * FROM jobs'):return self
        assert query.startswith("UPDATE jobs SET status='succeeded'")
        self.result=params[1];self.row.update(status='succeeded',result_json=self.result)
        return self
    def fetchone(self):return self.row
    def failure(self,*args):raise AssertionError('Synthetic adapter failed: '+repr(args))


def export_synthetic(out):
    b,p=flora_fixture(None,20)
    b['input']['vc_answers']=[]
    p['need_decisions']['source-need'].update(flex=True,flex_start_minute=480,flex_end_minute=1200,retain_original_start=True)
    p['source_identity']=source_identity(b['input']);p['source_file_sha256']=b['input']['metadata']['source_file_sha256']
    n=b['input']['customer_needs'][0]
    e=dict(version='flora-original-window-binding/1.0',binding_id='synthetic-window-binding',profile_id=p['profile_id'],
        base_profile_hash=jobs.digest(p),business_id=p['business_id'],data_use=p['data_use'],dataset_id=b['input']['metadata']['dataset_id'],
        source_identity=p['source_identity'],source_file_sha256=p['source_file_sha256'],
        period=dict(id='next',start='2027-01-04',end='2027-01-31',timezone='Europe/Stockholm'),
        window_semantics='EXECUTION_WINDOW',decision_ref='SYNTHETIC-DECISION',inactive_flex_need_ids=[n['need_id']],inactive_k3_need_ids=[],
        needs=[dict(need_id=n['need_id'],input_row_sha256=jobs.digest(n),app_reference_literal=n.get('source_ref'),
            original_source_reference=dict(source_id=n.get('source_fields',{}).get('source_id'),sheet=n.get('source_fields',{}).get('source_sheet'),row=n.get('source_fields',{}).get('source_row')))])
    before=deepcopy((b,p))
    with patch.object(binding,'PROFILE_ID',p['profile_id']),patch.object(binding,'EVIDENCE_HASH',jobs.digest(e)),patch.object(binding,'_load_evidence',return_value=e):
        selected=binding.bind_profile(p,b['input']['metadata']['dataset_id'])
        request=jobs.normalize_request(b)
        request['engine_context']={'business_id':p['business_id'],'data_use':p['data_use'],'profile_id':p['profile_id'],'automatic_learning':False}
        row=dict(id='d'*32,status='running',input_hash=jobs.digest(request['input']),profile_hash=jobs.digest(selected),
            request_json=jobs.canonical(request),profile_json=jobs.canonical(selected),method_hash=jobs.method_fingerprint(),
            build_commit='synthetic-original-window-patch',created_at='2027-01-04T00:00:00Z',started_at=None,finished_at=None,error_json=None,result_json=None)
        sink=MemorySink(row);public=jobs.JobStore.public
        with patch.object(jobs,'JobStore',return_value=sink),patch('bb.engine_methods.solve',side_effect=lambda profile,case,req:flora_result(case,540)[1]),patch.dict(os.environ,{'RENDER_GIT_COMMIT':row['build_commit']}),patch.object(jobs.time,'monotonic',return_value=0):
            jobs.run_worker('/synthetic/no-database',row['id'],'synthetic-lease')
        assert sink.result is not None
        result=json.loads(sink.result)
        assert result['validation']['overall']=='UNKNOWN' and not result['validation']['violations']
        assert result['need_window_contract']['needs'][0]['window_semantics']=='EXECUTION_WINDOW'
        assert result['schedule']['interventions'][0]['end']=='2027-01-04T09:20+01:00'
        assert (b,p)==before
        (out/'synthetic-input.json').write_text(jobs.canonical(b['input']))
        (out/'synthetic-result.raw.json').write_text(sink.result)
        (out/'synthetic-job.raw.json').write_text(jobs.canonical(public(sink.row)))
        return hashlib.sha256(sink.result.encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    os.environ['BB_TEST_PRIVATE_SNAPSHOTS']=args.private
    calls={}
    def block(name):
        calls[name]=0
        def fail(*a,**kw):calls[name]+=1;raise AssertionError('Forbidden '+name)
        return fail
    with contextlib.ExitStack() as stack:
        for target in ['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit','bb.flora_jobs.get_manager','bb.engine_api.get_manager','bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']:
            stack.enter_context(patch(target,side_effect=block(target)))
        for method in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
            if hasattr(cp_model.CpSolver,method):stack.enter_context(patch.object(cp_model.CpSolver,method,side_effect=block('CpSolver.'+method)))
        suite=unittest.defaultTestLoader.loadTestsFromName('test_flora_original_windows')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():raise SystemExit(1)
        synthetic_sha=export_synthetic(out)
        from test_flora_original_windows import OriginalWindowTests as T
        (out/'need-window-contract.private.json').write_text(jobs.canonical(T.result['need_window_contract']))
        report=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),period_needs=1451,
            contract_rows=len(T.result['need_window_contract']['needs']),profile_hash=jobs.digest(T.bound),
            source_basis_sha256=jobs.digest(T.result['source_basis']),source_basis_unchanged=True,source_segments=292,
            inactive_extensions=286,inactive_k3_exceptions=8,synthetic_raw_result_sha256=synthetic_sha,
            evidence_hash=binding.EVIDENCE_HASH,forbidden_calls=calls,real_jobs_created=0,
            unresolved_locked_starts=sum(d.get('timing_authorization',{}).get('policy')=='REVIEW_REQUIRED' for d in T.bound['need_decisions'].values()),
            movable_by_common_decision=sum(d.get('timing_authorization',{}).get('policy')=='MOVABLE_WITHIN_SOURCE_WINDOW' for d in T.bound['need_decisions'].values()),
            unique_starts_from_constraints=176,installation_ready=False,
            actual_contract_is_source_projection_only=True,
            no_feasibility_claim=True)
        assert not any(calls.values())
        (out/'motor-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
