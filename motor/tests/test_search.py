import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from test_rules import fixture
from bb.solver import solve


SOLVER_SRC = Path(__file__).resolve().parents[1].joinpath('bb', 'solver.py').read_text(encoding='utf-8')


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class SearchFeasibilityFirst(unittest.TestCase):
    def _phases(self, r):
        return (r['schedule'].get('lexicographic') or {}).get('phases') or []

    def test_search_a_zero_gap_possible_returns_zero_coverage(self):
        d, _ = fixture()
        r = solve(d, 5)
        lex = r['schedule']['lexicographic']
        names = [p['name'] for p in lex['phases']]
        self.assertIn('zeroGap', names)
        zg = next(p for p in lex['phases'] if p['name'] == 'zeroGap')
        self.assertIn(zg['status'], ('OPTIMAL', 'FEASIBLE'))
        self.assertEqual(lex['uncoveredMinutes'], 0)
        self.assertTrue(lex['coverageProven'])
        self.assertEqual(r['schedule']['uncovered'], [])
        self.assertNotIn('coverage', names)

    def test_search_b_zero_gap_infeasible_falls_back_to_best_feasible(self):
        d, _ = fixture()
        d['employees'][0]['skills'] = []
        r = solve(d, 5)
        lex = r['schedule']['lexicographic']
        names = [p['name'] for p in lex['phases']]
        self.assertEqual(names[0], 'zeroGap')
        self.assertEqual(lex['phases'][0]['status'], 'INFEASIBLE')
        self.assertIn('coverage', names)
        self.assertGreater(lex['uncoveredMinutes'], 0)
        self.assertFalse(lex['coverageProven'])
        self.assertIn(r['schedule']['solverStatus'], ('OPTIMAL', 'FEASIBLE'))
        self.assertTrue(r['validation']['valid'])

    def test_search_c_zero_gap_unknown_uses_coverage_fallback(self):
        from ortools.sat.python import cp_model
        orig = cp_model.CpSolver.solve
        n = {'i': 0}

        def wrapped(self, model, callback=None):
            n['i'] += 1
            if n['i'] == 1:
                return cp_model.UNKNOWN
            if callback is None:
                return orig(self, model)
            return orig(self, model, callback)

        d, _ = fixture()
        with patch.object(cp_model.CpSolver, 'solve', wrapped):
            r = solve(d, 5)
        lex = r['schedule']['lexicographic']
        self.assertEqual(lex['phases'][0]['name'], 'zeroGap')
        self.assertEqual(lex['phases'][0]['status'], 'UNKNOWN')
        self.assertIn('coverage', [p['name'] for p in lex['phases']])
        self.assertIn(r['schedule']['solverStatus'], ('OPTIMAL', 'FEASIBLE'))
        self.assertGreater(len(r['schedule']['assignments']), 0)

    def test_search_d_phase0_does_not_hint_gap_count(self):
        self.assertNotIn("add_hint(gap,o['count'])", SOLVER_SRC)
        self.assertNotIn('add_hint(gap, o[\'count\'])', SOLVER_SRC)
        self.assertIn('sat.add_hint(sat.get_int_var_from_proto_index(gap.index), 0)', SOLVER_SRC)

    def test_search_e_phase0b_can_use_incumbent_shift_ones(self):
        self.assertIn("zeroGapB", SOLVER_SRC)
        self.assertIn('shift_ones', SOLVER_SRC)
        self.assertIn("int(last_solver.value(c['x']))==1", SOLVER_SRC)
        self.assertIn('only_ones=True', SOLVER_SRC)

    def test_search_f_cost_quality_cannot_worsen_locked_zero_coverage(self):
        d, _ = fixture()
        r = solve(d, 5)
        lex = r['schedule']['lexicographic']
        self.assertEqual(lex['uncoveredMinutes'], 0)
        after_lock = False
        for p in lex['phases']:
            if p['name'] in ('cost', 'quality') and p['status'] != 'SKIPPED':
                after_lock = True
        self.assertTrue(after_lock)
        self.assertEqual(r['schedule']['uncoveredMinutes'], 0)
        self.assertEqual(r['schedule']['uncovered'], [])

    def test_lex_stop_coverage_skips_cost_quality(self):
        d, _ = fixture()
        d['employees'][0]['skills'] = []
        r = solve(d, 5, lex_stop='coverage')
        names = [p['name'] for p in self._phases(r)]
        self.assertEqual(names[0], 'zeroGap')
        self.assertIn('coverage', names)
        self.assertNotIn('cost', names)
        self.assertNotIn('quality', names)
        self.assertGreater(r['schedule']['lexicographic']['uncoveredMinutes'], 0)

    def test_cost_waits_for_small_coverage_gap(self):
        from bb.solver import coverage_ready_for_cost, COVERAGE_ABS_GAP, COVERAGE_REL_GAP
        self.assertEqual(COVERAGE_ABS_GAP, 30)
        self.assertEqual(COVERAGE_REL_GAP, 0.10)
        self.assertTrue(coverage_ready_for_cost(dict(code='OPTIMAL', uncoveredMinutes=100, bound=100)))
        self.assertTrue(coverage_ready_for_cost(dict(code='FEASIBLE', uncoveredMinutes=0, bound=0)))
        self.assertTrue(coverage_ready_for_cost(dict(code='FEASIBLE', uncoveredMinutes=100, bound=91)))
        self.assertFalse(coverage_ready_for_cost(dict(code='FEASIBLE', uncoveredMinutes=100, bound=80)))
        self.assertFalse(coverage_ready_for_cost(dict(code='FEASIBLE', uncoveredMinutes=3586, bound=1112)))
        self.assertFalse(coverage_ready_for_cost(dict(code='FEASIBLE', uncoveredMinutes=6279, bound=420)))
