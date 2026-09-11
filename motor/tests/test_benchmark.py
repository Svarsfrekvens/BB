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


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: benchmark körs inte')
class BenchmarkScenarios(unittest.TestCase):
    def _assert_perf(self, row):
        perf = row['performance']
        missing = PERF_KEYS - set(perf)
        self.assertFalse(missing, missing)
        self.assertIn(perf['solverStatus'], ['OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'UNKNOWN'])
        self.assertEqual(row['generator']['needlessDays'], [])
        self.assertEqual(row['generator']['tooShort'], [])
        self.assertLessEqual(row['generator']['perDayMax'], 24)
        self.assertIn('performance', (row['result'].get('diagnostics') or {}))
        return perf

    def test_liten(self):
        row = run_benchmark('liten')
        perf = self._assert_perf(row)
        self.assertEqual(perf['planningMode'], 'generateFromNeeds')
        self.assertEqual(perf['employees'], 7)
        self.assertEqual(perf['planningDays'], 28)

    def test_normal(self):
        row = run_benchmark('normal')
        self._assert_perf(row)

    def test_storre(self):
        row = run_benchmark('storre')
        self._assert_perf(row)

    def test_stress(self):
        row = run_benchmark('stress')
        perf = self._assert_perf(row)
        self.assertEqual(perf['employees'], 25)
        self.assertGreaterEqual(perf['personShiftCombinationsBeforeFilter'], perf['personShiftCombinationsAfterFilter'] or 0)
