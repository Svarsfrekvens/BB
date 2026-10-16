"""The additive Flora routes must preserve the deployed pilot's API behavior."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from bb.api import app


class FloraPilotCompatibility(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"BB_API_TOKEN": "test-token-not-a-real-secret", "BB_ASYNC_JOBS": "0"})
        self.env.start()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test-token-not-a-real-secret"}

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_existing_health_auth_and_open_render_root_are_unchanged(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/health").status_code, 401)
        health = self.client.get("/api/health", headers=self.headers)
        self.assertEqual(health.status_code, 200)
        self.assertIn("limits", health.json())
        self.assertIn("flora", health.json())

    def test_openapi_retains_all_pilot_routes_and_adds_flora(self):
        schema = self.client.get("/openapi.json").json()
        for path in ("/", "/api/health", "/api/validate", "/api/optimize", "/api/optimize/jobs",
                     "/api/optimize/jobs/{job_id}", "/api/flora/jobs", "/api/flora/jobs/{job_id}"):
            self.assertIn(path, schema["paths"])

    def test_existing_optimize_async_flag_and_bad_data_semantics_unchanged(self):
        self.assertEqual(self.client.post("/api/optimize/jobs", json={"data": {}}, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.post("/api/optimize", json={"data": {}}, headers=self.headers).status_code, 422)

    def test_flora_requires_existing_token_and_server_owner(self):
        self.assertEqual(self.client.post("/api/flora/jobs", json={}).status_code, 401)
        self.assertEqual(self.client.post("/api/flora/jobs", json={}, headers=self.headers).status_code, 403)

    def test_remote_flora_requires_explicit_flag_and_token(self):
        remote = TestClient(app, client=("203.0.113.17", 5000))
        headers = {**self.headers, "X-BB-Job-Owner": "org:fictional-org"}
        try:
            with patch.dict(os.environ, {"BB_FLORA_REMOTE_ENABLED": "0"}):
                self.assertEqual(remote.post("/api/flora/jobs", json={}, headers=headers).status_code, 403)
            with patch.dict(os.environ, {"BB_FLORA_REMOTE_ENABLED": "1"}):
                # Correctly authorized: invalid body reaches source validation.
                self.assertEqual(remote.post("/api/flora/jobs", json={}, headers=headers).status_code, 422)
                self.assertEqual(remote.post("/api/flora/jobs", json={}).status_code, 401)
        finally:
            remote.close()

    def test_flora_shutdown_runs_without_touching_generic_queue(self):
        from bb import jobs as pilot_jobs
        self.assertNotEqual(pilot_jobs.__name__, "bb.flora_jobs")
        with patch("bb.flora_jobs.close_managers") as close, patch("bb.jobs.reset_jobs_for_tests") as reset:
            with TestClient(app) as client:
                self.assertEqual(client.get("/").status_code, 200)
            close.assert_called_once()
            reset.assert_not_called()

    def test_cors_defaults_are_unchanged(self):
        response = self.client.options("/api/optimize", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        # The original pilot middleware authenticates /api OPTIONS too. Do not
        # weaken that existing behavior as a side effect of adding Flora.
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
