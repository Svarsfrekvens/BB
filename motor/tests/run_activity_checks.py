"""Pure import/model/validator/API checks. Search, jobs, SQL and network forbidden."""
import argparse
import contextlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ortools.sat.python import cp_model
from run_typed_windows_checks import probes


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    counts={}
    def blocked(name):
        counts[name]=0
        def fail(*a,**k):counts[name]+=1;raise AssertionError('Forbidden: '+name)
        return fail
    with contextlib.ExitStack() as stack:
        for target in ['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.flora_jobs.get_manager',
            'bb.engine_api.get_manager','bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit',
            'bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']:
            stack.enter_context(patch(target,side_effect=blocked(target)))
        for method in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
            if hasattr(cp_model.CpSolver,method):stack.enter_context(patch.object(cp_model.CpSolver,method,side_effect=blocked('CpSolver.'+method)))
        suite=unittest.defaultTestLoader.loadTestsFromNames(['test_planning_activities','test_typed_windows_contract','test_flora_import.ImportTest'])
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        report=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),
            api_regression=probes(),forbidden_calls=counts)
        from test_planning_activities import probe_aggregate,case_for,result_for
        (out/'activity-review-example.json').write_text(json.dumps(probe_aggregate(),ensure_ascii=False,indent=2)+'\n')
        if result.wasSuccessful():
            _,export=result_for(case_for())
            (out/'synthetic-activity-result.json').write_text(json.dumps(export,ensure_ascii=False,indent=2)+'\n')
        (out/'test-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        assert not any(counts.values()),counts
        if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':main()
