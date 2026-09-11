import importlib.util
import unittest
from copy import deepcopy
from test_rules import fixture
from bb.validate import validate
from bb.solver import solve


@unittest.skipUnless(importlib.util.find_spec('ortools'),'OR-Tools saknas: solver-tester är INTE körda')
class SolverTests(unittest.TestCase):
    def test_real_solver_produces_valid_solution(self):
        d,_=fixture();r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertTrue(validate(d,r['schedule'])['valid']);self.assertEqual(len(r['schedule']['assignments']),1);self.assertEqual(r['schedule']['uncovered'],[])
    def test_no_qualified_staff_leaves_need_uncovered(self):
        d,_=fixture();d['employees'][0]['skills']=[];r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertEqual(r['schedule']['assignments'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_double_staff_with_one_person_reports_half_uncovered(self):
        d,_=fixture();d['interventions'][0]['doubleStaff']=True;r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_two_distinct_staff_and_simultaneous_double(self):
        d,_=fixture();d['interventions'][0]['doubleStaff']=True;d['employees'].append({**d['employees'][0],'id':'e2','code':'M02'});r=solve(d,5);a=r['schedule']['assignments'];self.assertEqual(len({x['employeeId'] for x in a}),2);self.assertEqual(len({x['start'] for x in a}),1);self.assertTrue(r['validation']['valid']);self.assertEqual(r['schedule']['uncovered'],[])
    def test_absent_employee_cannot_be_used(self):
        d,_=fixture();d['absences']=[dict(id='a',employeeId='e1',start='2026-09-07',end='2026-09-13')];r=solve(d,5)
        self.assertEqual(r['schedule']['assignments'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1)
    def test_rest_boundary_is_not_relaxed(self):
        d,s=fixture();d['boundaryShifts']=[{**s['shifts'][0],'id':'before','date':'2026-09-06','start':'13:00','end':'21:00'}];r=solve(d,5)
        self.assertEqual(r['schedule']['shifts'],[]);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1)
    def test_fixed_schedule_input_is_unchanged(self):
        d,_=fixture();old=deepcopy(d);solve(d,5);self.assertEqual(d,old)
    def test_overlap_reports_one_uncovered_instead_of_breaking_rules(self):
        d,_=fixture();d['interventions'].append({**d['interventions'][0],'id':'t2'});r=solve(d,5)
        self.assertEqual(len(r['schedule']['assignments']),1);self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1);self.assertTrue(r['validation']['valid'])
    def test_flexible_tasks_can_be_sequenced(self):
        d,_=fixture();d['interventions'][0].update(type='flexible',latestEnd='11:00');d['interventions'].append({**d['interventions'][0],'id':'t2'});r=solve(d,5);self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE']);self.assertTrue(r['validation']['valid']);self.assertEqual(r['schedule']['uncovered'],[])
    def test_required_employee_is_honoured(self):
        d,_=fixture()
        d['employees'].append({**d['employees'][0],'id':'e2','code':'M02'})
        d['interventions'][0]['requiredEmployeeId']='e2'
        r=solve(d,8)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE'])
        for a in r['schedule']['assignments']:
            self.assertEqual(a['employeeId'],'e2')
    def test_dated_ssg_caps_hours(self):
        d,_=fixture()
        d['employees'][0]['ssgWindows']=[dict(start='2026-09-07',end='2026-09-13',ssg=0)]
        r=solve(d,5)
        self.assertIn(r['schedule']['solverStatus'],['OPTIMAL','FEASIBLE'])
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']),1)

    def test_solver_time_budget_diagnostics(self):
        d,_=fixture()
        r=solve(d,5)
        perf=(r.get('diagnostics') or {}).get('performance') or {}
        self.assertGreater(perf['requestedSolveBudgetMs'], 0)
        self.assertIn('actualCoverageSolveMs', perf)
        self.assertIn('actualCostSolveMs', perf)
        self.assertIn('actualQualitySolveMs', perf)
        self.assertEqual(len(perf['remainingBudgetBeforeEachPhaseMs']), 3)
        self.assertGreaterEqual(perf['remainingBudgetBeforeEachPhaseMs'][0]['remainingBudgetBeforePhaseMs'], 4000)
        self.assertGreaterEqual(perf['totalSolverMs'], 0)
        self.assertNotEqual(perf.get('timeoutReason'), 'budget_exhausted_before_phase')
        self.assertGreaterEqual(perf['supportCombinationsBeforePruning'], perf['supportCombinationsAfterPruning'])

    def test_lexico_locks_and_hints(self):
        d,_=fixture()
        r=solve(d,5)
        perf=(r.get('diagnostics') or {}).get('performance') or {}
        self.assertTrue(perf['coverageIncumbentAvailable'])
        self.assertTrue(perf['coverageTargetLocked'])
        self.assertTrue(perf['costIncumbentAvailable'])
        phases=perf['hintVariablesAppliedPerPhase']
        self.assertGreaterEqual(len(phases), 2)
        self.assertGreater(sum(p.get('hintVariablesApplied') or 0 for p in phases), 0)
        lex=(r['schedule'].get('lexicographic') or {})
        self.assertEqual(lex.get('uncoveredMinutes'), 0)

    def test_ui_summary_object(self):
        d,_=fixture()
        r=solve(d,5)
        s=r['summary']
        for key in ('status','coveragePercent','customerNearPercent','cost','hardViolations','warnings',
                    'changedShiftCount','lockedShiftCount','explanationSummary','performanceSummary'):
            self.assertIn(key, s)
        self.assertIn(s['status'], ['OPTIMAL','FEASIBLE'])
        self.assertEqual(s['hardViolations'], [])
        self.assertTrue(s['explanationSummary'])
        self.assertIn('täckt', s['performanceSummary'].lower())

    def test_model_build_diagnostics(self):
        d,_=fixture()
        r=solve(d,5)
        perf=(r.get('diagnostics') or {}).get('performance') or {}
        self.assertGreaterEqual(perf['modelBuildTotalMs'], 0)
        self.assertGreaterEqual(perf['constraintBuildMs'], 0)
        self.assertGreaterEqual(perf['assignmentBuildMs'], 0)
        self.assertGreaterEqual(perf['indexBuildMs'], 0)
        self.assertGreaterEqual(perf['shiftVariablesBeforePruning'], perf['shiftVariablesAfterPruning'])
