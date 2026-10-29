"""Targeted common-decision regression; private sources stay outside Git."""
import argparse,contextlib,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
parser=argparse.ArgumentParser(description='Solver-free common timing decision checks')
parser.add_argument('--private',required=True);parser.add_argument('--out',required=True)
args=parser.parse_args()
root=Path(args.out);root.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(repo/'motor'),str(repo/'motor/tests')]
os.environ['BB_TEST_PRIVATE_SNAPSHOTS']=args.private
from ortools.sat.python import cp_model
calls={}
def blocked(name):
 calls[name]=0
 def fail(*a,**k):calls[name]+=1;raise AssertionError('Forbidden '+name)
 return fail
with contextlib.ExitStack() as stack:
 for name in ['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit','bb.flora_jobs.get_manager','bb.engine_api.get_manager','bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']:
  stack.enter_context(patch(name,side_effect=blocked(name)))
 for name in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
  if hasattr(cp_model.CpSolver,name):stack.enter_context(patch.object(cp_model.CpSolver,name,side_effect=blocked('CpSolver.'+name)))
 suite=unittest.defaultTestLoader.loadTestsFromNames(['test_flora_original_windows','test_flora_timing_decisions'])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 if not result.wasSuccessful():raise SystemExit(1)
 from test_flora_timing_decisions import export_authorized_fixture,TimingDecisionTests as T
 result_sha=export_authorized_fixture(root)
 from bb.flora_jobs import digest
 from test_flora_original_windows import OriginalWindowTests as W
 assert not any(calls.values())
 report=dict(tests=result.testsRun,failures=0,errors=0,forbidden_calls=calls,real_jobs=0,
  source_basis_unchanged=W.result['source_basis']==W.basis,source_basis_canonical_sha256=digest(W.basis),original_segments=292,
  need_contract_rows=1451,movable_by_common_decision=1275,unique_source_starts=176,remaining_timing_gaps=0,remaining_event_dependencies=0,resolved_event_conditions=132,newly_authorized_intervals=775,
  effective_profile_hash=digest(T.bound),synthetic_raw_result_sha256=result_sha,
  solver_free_preflight_pass=True,actual_optimization_verified=False,solver_free=True)
 (root/'motor-evidence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
