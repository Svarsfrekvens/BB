import importlib.util
import unittest
from bb.benchmark import SCENARIOS, build_scenario, generator_guardrails, run_benchmark
from bb.generate import generate_shift_templates


PERF_KEYS = {
    'planningMode', 'employees', 'planningDays', 'customerNeedIntervals',
    'generatedShiftTemplates', 'generatedTemplatesPerDayMax', 'generatedTemplatesTotal',
    'personShiftCombinationsBeforeFilter', 'personShiftCombinationsAfterFilter', 'filteredShare',
    'solverVariables', 'solverConstraints', 'preCheckTimeMs', 'generateTimeMs', 'solveTimeMs',
    'validateTimeMs', 'totalTimeMs', 'solverStatus', 'targets',
    'supportCombinationsBeforePruning', 'supportCombinationsAfterPruning', 'supportPrunedPercent',
    'assignmentVariables', 'totalVariables', 'totalConstraints',
    'generationMs', 'precheckMs', 'supportBuildMs', 'solverMs', 'validationMs', 'totalMs',
    'requestedSolveBudgetMs', 'actualCoverageSolveMs', 'actualCostSolveMs', 'actualQualitySolveMs',
    'remainingBudgetBeforeEachPhaseMs', 'totalSolverMs',
}


class BenchmarkGuardrails(unittest.TestCase):
    def test_liten_generator_stays_bounded(self):
        d = build_scenario('liten')
        g = generator_guardrails(d)
        self.assertEqual(g['suspiciousMinuteStarts'], [])
        self.assertEqual(g['tooShort'], [])
        self.assertEqual(g['needlessDays'], [])
        self.assertLessEqual(g['stats']['perDayMax'], 24)
        self.assertLessEqual(g['stats']['total'], 48)
        tm = generate_shift_templates(d)
        self.assertTrue(tm)
        self.assertFalse(any(t['start'].count(':') != 1 for t in tm))

    def test_scale_and_constraint_catalog(self):
        self.assertIn('liten', SCENARIOS)
        self.assertEqual(SCENARIOS['liten']['category'], 'scale')
        self.assertEqual(SCENARIOS['night']['category'], 'constraint')


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: benchmark körs inte')
class BenchmarkScaleA(unittest.TestCase):
    def _assert_perf(self, row):
        perf = row['performance']
        missing = PERF_KEYS - set(perf)
        self.assertFalse(missing, missing)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN'])
        self.assertEqual(row['generator']['needlessDays'], [])
        self.assertEqual(row['generator']['tooShort'], [])
        self.assertLessEqual(row['generator']['perDayMax'], 24)
        self.assertGreaterEqual(perf['supportCombinationsBeforePruning'], perf['supportCombinationsAfterPruning'] or 0)
        self.assertEqual(row['category'], 'scale')
        self.assertGreater(perf['requestedSolveBudgetMs'], 0)
        self.assertIsInstance(perf['remainingBudgetBeforeEachPhaseMs'], list)
        return perf

    def test_liten_coverable_and_kpi_split(self):
        row = run_benchmark('liten')
        perf = self._assert_perf(row)
        self.assertEqual(perf['planningMode'], 'generateFromNeeds')
        self.assertEqual(perf['employees'], 7)
        self.assertEqual(perf['planningDays'], 28)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(perf['coveredNeedPct'], 100)
        self.assertLess(perf['customerNearPct'], 99)
        self.assertLess(perf['totalMs'], 60000)

    def test_normal(self):
        row = run_benchmark('normal')
        perf = self._assert_perf(row)
        self.assertEqual(perf['employees'], 10)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(perf['coveredNeedPct'], 100)

    def test_storre(self):
        row = run_benchmark('storre')
        perf = self._assert_perf(row)
        self.assertEqual(perf['employees'], 15)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(perf['coveredNeedPct'], 100)

    def test_stress(self):
        row = run_benchmark('stress')
        perf = self._assert_perf(row)
        self.assertEqual(perf['employees'], 25)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'UNKNOWN'])
        self.assertLess(perf['totalMs'], 180000)
        self.assertNotEqual(perf.get('timeoutReason'), 'budget_exhausted_before_phase')


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: benchmark körs inte')
class BenchmarkConstraintB(unittest.TestCase):
    def test_night_shortage_explains(self):
        row = run_benchmark('night')
        sch = row['result']['schedule']
        self.assertEqual(row['category'], 'constraint')
        self.assertIn(sch['solverStatus'], ['INFEASIBLE', 'FEASIBLE', 'UNKNOWN'])
        self.assertTrue(sch['explanation'])
        self.assertLess(row['performance']['totalMs'], 60000)

    def test_skill_shortage_explains(self):
        row = run_benchmark('skill')
        self.assertIn(row['result']['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE'])
        self.assertTrue(row['result']['schedule']['explanation'])

    def test_ssg_shortage_explains(self):
        row = run_benchmark('ssg')
        self.assertIn(row['result']['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN'])
        self.assertTrue(row['result']['schedule']['explanation'])

    def test_absence_shortage_explains(self):
        row = run_benchmark('absence')
        self.assertIn(row['result']['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE'])
        self.assertTrue(row['result']['schedule']['explanation'])
