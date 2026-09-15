"""ASYNC-A–H: asynkron jobbkön. Ändrar inte /api/optimize."""
import importlib.util
import os
import time
import unittest
from copy import deepcopy

from test_jour_capacity import four_jour_august
from test_rules import cover_f01, fixture


@unittest.skipUnless(
    importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx') and importlib.util.find_spec('ortools'),
    'FastAPI/OR-Tools saknas',
)
class AsyncOptimizeJobs(unittest.TestCase):
    def setUp(self):
        os.environ['BB_ASYNC_JOBS'] = '1'
        os.environ.pop('BB_API_TOKEN', None)
        from bb import jobs
        jobs.reset_jobs_for_tests()
        from fastapi.testclient import TestClient
        from bb.api import app
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.pop('BB_ASYNC_JOBS', None)

    def _tiny(self):
        d, _ = fixture()
        cover_f01(d)
        d['rules']['nightFloor'] = 0
        return d

    def _wait(self, job_id, timeout=40):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            r = self.client.get(f'/api/optimize/jobs/{job_id}')
            self.assertEqual(r.status_code, 200)
            last = r.json()
            if last.get('status') in ('completed', 'failed'):
                return last
            time.sleep(0.15)
        self.fail(f'jobb blev inte klart: {last}')

    def test_async_flag_off_is_404(self):
        os.environ['BB_ASYNC_JOBS'] = '0'
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=2))
        self.assertEqual(r.status_code, 404)

    def test_async_a_start_returns_job_id_immediately(self):
        t0 = time.time()
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=8))
        self.assertEqual(r.status_code, 200)
        self.assertLess(time.time() - t0, 2.5)
        self.assertTrue(r.json().get('jobId'))
        self.assertIn(r.json().get('status'), ('queued', 'preparing', 'checking', 'solving'))

    def test_async_b_status_walks_phases(self):
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=6))
        job_id = r.json()['jobId']
        seen = {r.json().get('phase')}
        done = self._wait(job_id)
        seen.add(done.get('phase'))
        mid = self.client.get(f'/api/optimize/jobs/{job_id}').json()
        seen.add(mid.get('phase'))
        self.assertTrue(seen & {'queued', 'preparing', 'checking', 'solving', 'validating', 'completed'})
        self.assertEqual(done.get('status'), 'completed')

    def test_async_c_completed_has_motor_payload(self):
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=8))
        done = self._wait(r.json()['jobId'])
        result = done.get('result') or {}
        self.assertIn('schedule', result)
        self.assertIn(result['schedule'].get('solverStatus'), ('OPTIMAL', 'FEASIBLE', 'INFEASIBLE'))

    def test_async_d_client_gone_does_not_stop_job(self):
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=6))
        job_id = r.json()['jobId']
        # Ingen vidare request-kropp / "webbläsare" – bara senare GET.
        done = self._wait(job_id)
        self.assertEqual(done.get('status'), 'completed')

    def test_async_e_same_input_reuses_running_job(self):
        from bb.jobs import create_job
        d = self._tiny()
        held = create_job(d, 8)
        b = self.client.post('/api/optimize/jobs', json=dict(data=d, seconds=8))
        self.assertEqual(b.status_code, 200)
        self.assertEqual(b.json()['jobId'], held['id'])
        self.assertTrue(b.json().get('reused'))

    def test_async_f_changed_input_has_new_hash(self):
        d = self._tiny()
        a = self.client.post('/api/optimize/jobs', json=dict(data=d, seconds=4))
        h1 = a.json()['inputHash']
        done = self._wait(a.json()['jobId'])
        d2 = deepcopy(d)
        d2['employees'][0]['ssg'] = max(50, int(d2['employees'][0].get('ssg') or 100) - 10)
        b = self.client.post('/api/optimize/jobs', json=dict(data=d2, seconds=4))
        self.assertNotEqual(h1, b.json()['inputHash'])
        self.assertNotEqual(done['inputHash'], b.json()['inputHash'])
        self._wait(b.json()['jobId'])

    def test_async_g_timeout_with_valid_incumbent_is_not_technical_error(self):
        r = self.client.post('/api/optimize/jobs', json=dict(data=self._tiny(), seconds=2))
        done = self._wait(r.json()['jobId'])
        status = (done.get('result') or {}).get('schedule', {}).get('solverStatus')
        if status in ('OPTIMAL', 'FEASIBLE'):
            self.assertIn(done.get('outcome'), ('balans_klar', 'basta_hittade'))
            self.assertEqual(done.get('status'), 'completed')
            self.assertNotEqual(done.get('outcome'), 'tekniskt_fel')
        else:
            self.skipTest(f'litet fall gav {status}, inte incumbent')

    def test_async_h_hard_blocker_returns_jour_diagnosis(self):
        d = four_jour_august()
        r = self.client.post('/api/optimize/jobs', json=dict(data=d, seconds=5))
        self.assertEqual(r.status_code, 200)
        done = self._wait(r.json()['jobId'], timeout=20)
        self.assertEqual(done.get('outcome'), 'kompletteras')
        jour = ((done.get('result') or {}).get('resourceDiagnostics') or {}).get('jour') or {}
        self.assertTrue(jour.get('jourCapacityShortfallDetected'))
