"""A–H: filbaserad async-persistens. Ändrar inte solve()."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_rules import cover_f01, fixture

from bb import jobs


def _tiny():
    d, _ = fixture()
    cover_f01(d)
    d['rules']['nightFloor'] = 0
    return d


def _result(outcome='balans_klar'):
    return {
        'schedule': {
            'solverStatus': 'FEASIBLE',
            'uncoveredMinutes': 0,
            'shifts': [{'id': 's1'}],
            'assignments': [],
            'explanation': 'test',
        },
        'validation': {'valid': True, 'errors': [], 'warnings': []},
        'summary': {'mark': outcome},
    }


class JobStorePersistens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ['BB_JOB_STORE_DIR'] = self.tmp.name
        os.environ['BB_ASYNC_JOBS'] = '1'
        jobs.reset_jobs_for_tests()

    def tearDown(self):
        jobs.reset_jobs_for_tests()
        os.environ.pop('BB_JOB_STORE_DIR', None)
        os.environ.pop('BB_ASYNC_JOBS', None)
        self.tmp.cleanup()

    def _restart(self):
        jobs.reset_jobs_for_tests()
        jobs.ensure_loaded()

    def test_a_completed_survives_restart(self):
        job = jobs.create_job(_tiny(), 8)
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        job_id = job['id']
        self._restart()
        got = jobs.get_job(job_id)
        self.assertIsNotNone(got)
        self.assertEqual(got.get('status'), 'completed')
        self.assertEqual(got.get('outcome'), 'balans_klar')
        self.assertEqual((got.get('result') or {}).get('summary', {}).get('mark'), 'balans_klar')

    def test_b_balans_klar_before_frontend_fetch(self):
        job = jobs.create_job(_tiny(), 8)
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        job_id = job['id']
        self._restart()
        view = jobs.public_view(jobs.get_job(job_id), include_result=True)
        self.assertEqual(view.get('outcome'), 'balans_klar')
        self.assertTrue((view.get('result') or {}).get('validation', {}).get('valid'))

    def test_c_running_fail_closed_no_incumbent(self):
        job = jobs.create_job(_tiny(), 8)
        jobs._set(job, status='solving', phase='solving', phaseText='Skapar balans',
                  result=_result('incumbent'))
        job_id = job['id']
        self._restart()
        got = jobs.get_job(job_id)
        self.assertEqual(got.get('status'), 'failed')
        self.assertEqual(got.get('outcome'), 'tekniskt_fel')
        self.assertIsNone(got.get('result'))
        self.assertIn('startades om', got.get('phaseText') or '')
        self.assertIn('startades om', got.get('error') or '')

    def test_d_queued_fail_closed(self):
        job = jobs.create_job(_tiny(), 8)
        job_id = job['id']
        self.assertEqual(job.get('status'), 'queued')
        self._restart()
        got = jobs.get_job(job_id)
        self.assertEqual(got.get('status'), 'failed')
        self.assertEqual(got.get('outcome'), 'tekniskt_fel')
        self.assertIsNone(got.get('result'))

    def test_e_input_hash_survives_reload(self):
        data = _tiny()
        job = jobs.create_job(data, 8)
        h = job['inputHash']
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        self._restart()
        got = jobs.get_job(job['id'])
        self.assertEqual(got.get('inputHash'), h)
        self.assertNotIn('data', got or {})
        blob = Path(self.tmp.name, f"{job['id']}.json").read_text(encoding='utf-8')
        self.assertNotIn('"data"', blob)

    def test_a_get_api_after_restart(self):
        if not __import__('importlib.util').util.find_spec('fastapi'):
            self.skipTest('FastAPI saknas')
        from fastapi.testclient import TestClient
        from bb.api import app
        job = jobs.create_job(_tiny(), 8)
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        job_id = job['id']
        self._restart()
        r = TestClient(app).get(f'/api/optimize/jobs/{job_id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get('outcome'), 'balans_klar')
        self.assertTrue((r.json().get('result') or {}).get('schedule'))

    def test_completed_not_reused_as_active(self):
        data = _tiny()
        job = jobs.create_job(data, 8)
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        self._restart()
        self.assertIsNone(jobs.find_active(job['inputHash']))

    def test_file_has_wall_clock(self):
        job = jobs.create_job(_tiny(), 8)
        raw = json.loads(Path(self.tmp.name, f"{job['id']}.json").read_text(encoding='utf-8'))
        self.assertTrue(str(raw.get('createdAtIso') or '').startswith('20'))
        self.assertTrue(str(raw.get('updatedAtIso') or '').startswith('20'))


class JobStoreInMemoryFallback(unittest.TestCase):
    def setUp(self):
        os.environ.pop('BB_JOB_STORE_DIR', None)
        jobs.reset_jobs_for_tests()

    def tearDown(self):
        jobs.reset_jobs_for_tests()

    def test_h_without_store_dir_lost_after_restart(self):
        job = jobs.create_job(_tiny(), 8)
        jobs._set(job, status='completed', phase='completed', outcome='balans_klar',
                  result=_result(), phaseText='Balans klar')
        job_id = job['id']
        jobs.reset_jobs_for_tests()
        jobs.ensure_loaded()
        self.assertIsNone(jobs.get_job(job_id))


class JobStoreDoesNotTouchSolve(unittest.TestCase):
    def test_execute_still_calls_solve_for_short_period(self):
        os.environ.pop('BB_JOB_STORE_DIR', None)
        jobs.reset_jobs_for_tests()
        fake = _result()
        job = jobs.create_job(_tiny(), 8)
        with patch('bb.jobs.solve', return_value=fake) as slv:
            jobs.execute(job)
        slv.assert_called_once()
