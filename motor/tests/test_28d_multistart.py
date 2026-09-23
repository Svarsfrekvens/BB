"""28d async multi-start. Ändrar inte solverconstraints eller /api/optimize."""
from __future__ import annotations

import importlib.util
import os
import unittest
from copy import deepcopy
from unittest.mock import patch

from test_rules import cover_f01, fixture

from bb.jobs import classify, create_job, execute, reset_jobs_for_tests
from bb.multistart import (
    MULTI_START_SEEDS,
    MULTI_START_SECONDS,
    MULTI_START_WORKERS,
    godkannbar_resultat,
    is_28d_period,
    uncovered_minutes,
)


def as_28d(data):
    d = deepcopy(data)
    d['workplace']['start'] = '2026-08-03'
    d['workplace']['end'] = '2026-08-30'
    cover_f01(d)
    return d


def fake_result(unc, status='FEASIBLE', valid=True, errors=None, seed_tag=None):
    errors = list(errors or [])
    return {
        'schedule': {
            'solverStatus': status,
            'uncoveredMinutes': unc,
            'shifts': [{'id': 's1', 'employeeId': 'e1'}] if status in ('FEASIBLE', 'OPTIMAL') else [],
            'assignments': [{'occurrenceId': 't1'}] if status in ('FEASIBLE', 'OPTIMAL') else [],
            'explanation': '',
            'lexicographic': {'uncoveredMinutes': unc},
        },
        'validation': {'valid': valid and not errors, 'errors': errors, 'warnings': []},
        'summary': {'seedTag': seed_tag, 'uncoveredMinutes': unc},
        'diagnostics': {},
        'resourceDiagnostics': {},
    }


class PeriodDetection(unittest.TestCase):
    def test_7d_is_not_28d(self):
        d, _ = fixture()
        self.assertFalse(is_28d_period(d))

    def test_galaxen_dates_are_28d(self):
        d, _ = fixture()
        self.assertTrue(is_28d_period(as_28d(d)))

    def test_constants(self):
        self.assertEqual(MULTI_START_WORKERS, 4)
        self.assertEqual(MULTI_START_SECONDS, 240)
        self.assertEqual(MULTI_START_SEEDS, (41, 42, 43, 44))


class Godkannbar(unittest.TestCase):
    def test_100_and_zero_hard(self):
        self.assertTrue(godkannbar_resultat(fake_result(0)))

    def test_99_is_not(self):
        self.assertFalse(godkannbar_resultat(fake_result(1)))

    def test_skill_blocks(self):
        self.assertFalse(
            godkannbar_resultat(fake_result(0, valid=False, errors=[{'rule': 'TASK_SKILL'}]))
        )


class Execute28d(unittest.TestCase):
    def setUp(self):
        reset_jobs_for_tests()
        d, _ = fixture()
        self.data = as_28d(d)

    def _run(self, side_effect):
        job = create_job(self.data, 900)
        with patch('bb.multistart.run_solve_attempt', side_effect=side_effect) as mocked:
            execute(job)
        return job, mocked

    def test_28d_uses_4_workers_and_240s(self):
        job, mocked = self._run(lambda *a, **k: (fake_result(0, seed_tag=a[3]), None))
        self.assertTrue(job.get('result'))
        self.assertGreaterEqual(mocked.call_count, 1)
        args, kwargs = mocked.call_args
        data, seconds, workers, seed = args[:4] if args else (
            kwargs.get('data'),
            kwargs.get('seconds'),
            kwargs.get('workers'),
            kwargs.get('seed'),
        )
        self.assertEqual(workers, 4)
        self.assertEqual(seconds, 240)
        self.assertEqual(seed, 41)

    def test_seeds_in_order_and_stop_at_100(self):
        calls = []

        def fake(data, seconds, workers, seed):
            calls.append(seed)
            if seed == 41:
                return fake_result(200, seed_tag=41), None
            return fake_result(0, seed_tag=42), None

        job, mocked = self._run(fake)
        self.assertEqual(calls, [41, 42])
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual((job.get('result') or {}).get('summary', {}).get('seedTag'), 42)
        self.assertEqual(job.get('outcome'), 'balans_klar')

    def test_next_seed_only_if_not_godkannbar(self):
        def fake(data, seconds, workers, seed):
            return fake_result(0, seed_tag=41), None

        _, mocked = self._run(fake)
        self.assertEqual(mocked.call_count, 1)

    def test_keeps_best_valid_and_max_four(self):
        mapping = {41: 400, 42: 50, 43: 80, 44: 60}

        def fake(data, seconds, workers, seed):
            return fake_result(mapping[seed], seed_tag=seed), None

        job, mocked = self._run(fake)
        self.assertEqual(mocked.call_count, 4)
        self.assertEqual((job.get('result') or {}).get('summary', {}).get('seedTag'), 42)
        self.assertEqual(uncovered_minutes(job.get('result')), 50)
        self.assertEqual(job.get('outcome'), 'basta_hittade')
        self.assertEqual(job.get('status'), 'completed')

    def test_hard_errors_lose_to_valid_incumbent(self):
        def fake(data, seconds, workers, seed):
            if seed == 41:
                return fake_result(0, valid=False, errors=[{'rule': 'REST'}], seed_tag=41), None
            if seed == 42:
                return fake_result(30, seed_tag=42), None
            return fake_result(40, seed_tag=seed), None

        job, mocked = self._run(fake)
        self.assertEqual(mocked.call_count, 4)
        self.assertEqual((job.get('result') or {}).get('summary', {}).get('seedTag'), 42)

    def test_shorter_period_does_not_multistart(self):
        d, _ = fixture()
        job = create_job(d, 30)
        with patch('bb.multistart.run_solve_attempt') as ms, patch(
            'bb.jobs.solve', return_value=fake_result(0)
        ) as slv:
            execute(job)
        ms.assert_not_called()
        slv.assert_called_once()
        kwargs = slv.call_args.kwargs
        self.assertFalse(kwargs.get('sat_params'))


@unittest.skipUnless(
    importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx') and importlib.util.find_spec('ortools'),
    'FastAPI/OR-Tools saknas',
)
class SyncUnchanged(unittest.TestCase):
    def setUp(self):
        os.environ['BB_ASYNC_JOBS'] = '1'
        os.environ.pop('BB_API_TOKEN', None)
        reset_jobs_for_tests()
        from fastapi.testclient import TestClient
        from bb.api import app

        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop('BB_ASYNC_JOBS', None)

    def test_sync_optimize_does_not_use_multistart(self):
        d, _ = fixture()
        with patch('bb.multistart.run_28d_job') as ms, patch(
            'bb.solver.solve', return_value=fake_result(0)
        ):
            r = self.client.post('/api/optimize', json=dict(data=as_28d(d), seconds=20))
        self.assertEqual(r.status_code, 200)
        ms.assert_not_called()


class ClassifyDoesNotBypassGodkann(unittest.TestCase):
    def test_partial_coverage_is_basta_hittade_not_balans_klar(self):
        r = fake_result(12, status='OPTIMAL')
        self.assertFalse(godkannbar_resultat(r))
        self.assertEqual(classify(r), 'balans_klar')
