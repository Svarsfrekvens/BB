"""Sync 300 s, async upp till 900 s. Absoluta tak oförändrade."""
import importlib.util
import unittest

from test_rules import fixture
from bb.limits import (
    ASYNC_MAX_SOLVE_SECONDS,
    CEILING_MAX_OCCURRENCES,
    CEILING_MAX_SUPPORT_COMBINATIONS,
    SOLVE_MAX_SECONDS,
    SYNC_MAX_SOLVE_SECONDS,
    clamp_solve_seconds,
)


class TimeBudgetClamp(unittest.TestCase):
    def test_sync_stays_at_300(self):
        self.assertEqual(SYNC_MAX_SOLVE_SECONDS, 300)
        self.assertEqual(clamp_solve_seconds(600, SYNC_MAX_SOLVE_SECONDS), 300)
        self.assertEqual(clamp_solve_seconds(900, SYNC_MAX_SOLVE_SECONDS), 300)

    def test_async_allows_600_and_900(self):
        self.assertEqual(ASYNC_MAX_SOLVE_SECONDS, 900)
        self.assertEqual(SOLVE_MAX_SECONDS, 900)
        self.assertEqual(clamp_solve_seconds(600, ASYNC_MAX_SOLVE_SECONDS), 600)
        self.assertEqual(clamp_solve_seconds(900, ASYNC_MAX_SOLVE_SECONDS), 900)
        self.assertEqual(clamp_solve_seconds(1200, ASYNC_MAX_SOLVE_SECONDS), 900)

    def test_absolute_input_ceilings_unchanged(self):
        self.assertEqual(CEILING_MAX_OCCURRENCES, 4000)
        self.assertEqual(CEILING_MAX_SUPPORT_COMBINATIONS, 250000)


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas')
class SolveHonoursRaisedCeiling(unittest.TestCase):
    def test_direct_solve_keeps_budget_above_300(self):
        from bb.solver import solve
        d, _ = fixture()
        r = solve(d, 400)
        perf = ((r.get('diagnostics') or {}).get('performance') or {})
        self.assertEqual(perf.get('requestedSolveBudgetMs'), 400000)
        r2 = solve(d, 1200)
        perf2 = ((r2.get('diagnostics') or {}).get('performance') or {})
        self.assertEqual(perf2.get('requestedSolveBudgetMs'), 900000)
