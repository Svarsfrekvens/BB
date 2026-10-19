"""Meaningful contract, persistence, isolation and worker lifecycle checks."""
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from bb.flora_jobs import (JobStore, JobManager, IdempotencyConflict, JobInputError,
                     normalize_request, run_worker, database_path, digest,
                     process_identity, _proc_start_ticks)


def request_fixture():
    return dict(input={"metadata": {"schema_version": "flora-bb-input/1.0"},
                       "staff": [], "customers": [], "schedule_segments": [],
                       "customer_needs": [], "business_rules": []}, seconds=1)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name) / "jobs.sqlite3")
        self.request = normalize_request(request_fixture())
        self.profile = {"profile_id": "explicit-test-input"}

    def tearDown(self):
        self.temp.cleanup()

    def submit(self, owner="workspace-a", request=None, key=None):
        return self.store.submit(owner, request or self.request, self.profile, digest(self.profile), key)

    def test_concurrent_duplicate_clicks_create_one_job(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            answers = list(pool.map(lambda _: self.submit(), range(16)))
        self.assertEqual(len({job["id"] for job, _ in answers}), 1)
        self.assertEqual(sum(created for _, created in answers), 1)

    def test_owner_and_input_and_options_scope_deduplication(self):
        first, _ = self.submit()
        other, _ = self.submit("workspace-b")
        changed = {**self.request, "seconds": 2}
        options, _ = self.submit(request=changed)
        self.assertEqual(len({first["id"], other["id"], options["id"]}), 3)
        self.assertIsNone(self.store.get(first["id"], "workspace-b"))

    def test_explicit_idempotency_key_conflict(self):
        job, _ = self.submit(key="click-1")
        same, created = self.submit(key="click-1")
        self.assertEqual(job["id"], same["id"])
        self.assertFalse(created)
        with self.assertRaises(IdempotencyConflict):
            self.submit(request={**self.request, "seconds": 2}, key="click-1")

    def test_changed_day_boundary_is_a_new_run_with_same_source_hash(self):
        def request(clock):
            body=request_fixture()
            body['settings']={'unit_rules':{'day_boundaries':{'next':{'person-a':{
                'time':clock,'confirmed_at':'2026-10-17','source':'Explicit decision'}}}}}
            return normalize_request(body)
        first_request=request('03:00')
        self.assertEqual(first_request['scenario']['workspace']['unit_rules']['day_boundaries']['next']['person-a']['time'],'03:00')
        first,_=self.submit(request=first_request,key='boundary-1')
        second,created=self.submit(request=request('07:00'),key='boundary-2')
        self.assertTrue(created)
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(first['input_hash'],second['input_hash'])
        with self.assertRaises(IdempotencyConflict):
            self.submit(request=request('07:00'),key='boundary-1')

    def test_second_key_for_same_input_also_binds_its_fingerprint(self):
        job, _ = self.submit(key="click-1")
        same, created = self.submit(key="click-2")
        self.assertFalse(created)
        self.assertEqual(job["id"], same["id"])
        with self.assertRaises(IdempotencyConflict):
            self.submit(request={**self.request, "seconds": 2}, key="click-2")

    def test_persistence_and_interrupted_process_recovery(self):
        job, _ = self.submit()
        claimed = self.store.claim()
        self.assertEqual(claimed[0], job["id"])
        with self.store.connect() as con:
            con.execute("UPDATE jobs SET runner_pid=99999999 WHERE id=?", (job["id"],))
        reopened = JobStore(self.store.path)
        self.assertEqual(reopened.recover_interrupted(), 1)
        status = reopened.get(job["id"], "workspace-a")
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"]["code"], "INTERRUPTED")
        self.assertIsNone(status["result"])

    def test_only_one_process_can_claim_running_job_in_database(self):
        first, _ = self.submit()
        second, _ = self.submit(request={**self.request, "seconds": 2})
        claimed = self.store.claim()
        self.assertIn(claimed[0], (first["id"], second["id"]))
        other_store = JobStore(self.store.path)
        self.assertIsNone(other_store.claim())
        self.store.failure(claimed[0], claimed[1], "TEST", "Klar.")
        self.assertIsNotNone(other_store.claim())

    def test_reused_live_pid_with_old_identity_interrupts_and_releases_queue(self):
        first, _ = self.submit()
        job_id, lease = self.store.claim()
        queued, _ = self.submit(request={**self.request, "seconds": 2})
        identity = json.loads(process_identity(os.getpid()))
        identity["boot_id"] = "previous-container-or-boot"
        with self.store.connect() as con:
            # The PID is genuinely live, just as PID 1 can be after restart.
            con.execute("UPDATE jobs SET runner_pid=?,runner_identity=? WHERE id=?",
                        (os.getpid(), json.dumps(identity, sort_keys=True, separators=(",", ":")), job_id))
        self.assertEqual(self.store.recover_interrupted(), 1)
        recovered = self.store.get(first["id"], "workspace-a")
        self.assertEqual(recovered["error"]["code"], "INTERRUPTED")
        claimed = self.store.claim()
        self.assertEqual(claimed[0], queued["id"])
        self.store.failure(claimed[0], claimed[1], "TEST", "Klar.")

    def test_live_other_process_with_verified_identity_remains_running(self):
        job, _ = self.submit()
        job_id, lease = self.store.claim()
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            identity = process_identity(other.pid)
            self.assertIsNotNone(identity)
            with self.store.connect() as con:
                con.execute("UPDATE jobs SET runner_pid=?,runner_identity=? WHERE id=?", (other.pid, identity, job_id))
            self.assertEqual(self.store.recover_interrupted(), 0)
            self.assertEqual(self.store.get(job["id"], "workspace-a")["status"], "running")
            other.terminate()
            other.wait(timeout=5)
            self.assertEqual(self.store.recover_interrupted(), 1)
        finally:
            if other.poll() is None:
                other.kill()
                other.wait(timeout=5)

    def test_legacy_running_rows_without_identity_are_migrated_and_interrupted(self):
        job, _ = self.submit()
        job_id, lease = self.store.claim()
        with self.store.connect() as con:
            con.execute("ALTER TABLE jobs RENAME COLUMN runner_identity TO legacy_identity")
        reopened = JobStore(self.store.path)
        self.assertEqual(reopened.recover_interrupted(), 1)
        self.assertEqual(reopened.get(job["id"], "workspace-a")["error"]["code"], "INTERRUPTED")

    def test_actual_inflight_old_worker_cannot_overwrite_recovery_or_next_job(self):
        old, _ = self.submit()
        job_id, lease = self.store.claim()
        started = threading.Event()
        release = threading.Event()
        importer = types.ModuleType("bb.flora_import")
        importer.prepare_case = Mock(return_value={"actual_uploaded_case": True})
        method = types.ModuleType("bb.flora")
        method.check_case = Mock()
        def solve(*args, **kwargs):
            started.set()
            if not release.wait(3):
                raise RuntimeError("Test worker not released")
            return {"solver_status": "FEASIBLE", "review_required": True}
        method.solve_case = solve
        method.validate_case = Mock(return_value={"overall": "UNKNOWN", "rules": []})
        worker = threading.Thread(target=run_worker, args=(self.store.path, job_id, lease))
        with patch.dict("sys.modules", {"bb.flora_import": importer, "bb.flora": method}):
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                with self.store.connect() as con:
                    con.execute("UPDATE jobs SET runner_identity='previous-process' WHERE id=?", (job_id,))
                self.assertEqual(self.store.recover_interrupted(), 1)
                next_job, _ = self.submit(request={**self.request, "seconds": 2})
                next_id, next_lease = self.store.claim()
                self.assertEqual(next_id, next_job["id"])
                release.set()
                worker.join(timeout=3)
                self.assertFalse(worker.is_alive())
                result = self.store.get(old["id"], "workspace-a")
                self.assertEqual(result["status"], "failed")
                self.assertIsNone(result["result"])
                self.assertEqual(self.store.get(next_id, "workspace-a")["status"], "running")
                self.store.failure(next_id, next_lease, "TEST", "Klar.")
            finally:
                release.set()
                worker.join(timeout=3)

    def test_failed_retry_is_explicit_and_deduplicated(self):
        first, _ = self.submit()
        job_id, lease = self.store.claim()
        self.store.failure(job_id, lease, "TEST", "Ett begripligt fel.")
        retry = {**self.request, "retry_of": first["id"]}
        second, created = self.submit(request=retry)
        self.assertTrue(created)
        self.assertNotEqual(second["id"], first["id"])
        repeated, created = self.submit(request=retry)
        self.assertFalse(created)
        self.assertEqual(second["id"], repeated["id"])
        with self.assertRaises(JobInputError):
            self.store.submit("other", retry, self.profile, digest(self.profile))

    def test_worker_calls_import_solver_and_independent_validator(self):
        job, _ = self.submit()
        job_id, lease = self.store.claim()
        importer = types.ModuleType("bb.flora_import")
        importer.prepare_case = Mock(return_value={"actual_uploaded_case": True})
        method = types.ModuleType("bb.flora")
        method.check_case = Mock()
        method.solve_case = Mock(return_value={"solver_status": "FEASIBLE", "review_required": True})
        method.validate_case = Mock(return_value={"overall": "UNKNOWN", "rules": []})
        with patch.dict("sys.modules", {"bb.flora_import": importer, "bb.flora": method}):
            run_worker(self.store.path, job_id, lease)
        result = self.store.get(job["id"], "workspace-a")
        self.assertEqual(result["status"], "succeeded")
        importer.prepare_case.assert_called_once_with(self.request["input"], self.profile, {})
        method.solve_case.assert_called_once_with({"actual_uploaded_case": True}, seconds=1.0, workers=2,
                                                  objective_mode="coverage_then_temporary")
        method.validate_case.assert_called_once()
        self.assertEqual(result["result"]["validation"]["overall"], "UNKNOWN")
        self.assertTrue(result["result"]["provenance"]["requires_review"])
        self.assertNotIn("request_json", result)

    def test_worker_domain_error_is_actionable_and_private(self):
        job, _ = self.submit()
        job_id, lease = self.store.claim()
        importer = types.ModuleType("bb.flora_import")
        importer.prepare_case = Mock(side_effect=ValueError("Behov N1 saknar beslutad duration."))
        method = types.ModuleType("bb.flora")
        method.check_case = Mock()
        method.solve_case = Mock()
        method.validate_case = Mock()
        with patch.dict("sys.modules", {"bb.flora_import": importer, "bb.flora": method}):
            run_worker(self.store.path, job_id, lease)
        status = self.store.get(job["id"], "workspace-a")
        self.assertEqual(status["status"], "failed")
        self.assertIn("N1", status["error"]["message"])
        method.solve_case.assert_not_called()

    def test_dispatcher_process_failure_does_not_hang_job(self):
        job, _ = self.submit()
        process = Mock(pid=12345, returncode=7)
        process.poll.return_value = 7
        manager = JobManager(self.store)
        with patch("bb.flora_jobs.subprocess.Popen", return_value=process) as launch:
            manager.start()
            deadline = time.monotonic() + 3
            while self.store.get(job["id"], "workspace-a")["status"] != "failed" and time.monotonic() < deadline:
                time.sleep(0.01)
            manager.close()
        launch.assert_called_once()
        status = self.store.get(job["id"], "workspace-a")
        self.assertEqual(status["error"]["code"], "WORKER_FAILED")

    def test_worker_result_cannot_overwrite_recovered_job(self):
        job, _ = self.submit()
        job_id, lease = self.store.claim()
        self.store.failure(job_id, lease, "INTERRUPTED", "Avbruten.")
        run_worker(self.store.path, job_id, lease)
        self.assertEqual(self.store.get(job["id"], "workspace-a")["status"], "failed")

    def test_changed_implementation_cannot_silently_reuse_or_execute_old_job(self):
        first, _ = self.submit()
        job_id, lease = self.store.claim()
        with patch("bb.flora_jobs.method_fingerprint", return_value="changed-implementation"):
            second, created = self.submit()
            self.assertTrue(created)
            self.assertNotEqual(first["id"], second["id"])
            run_worker(self.store.path, job_id, lease)
        status = self.store.get(first["id"], "workspace-a")
        self.assertEqual(status["error"]["code"], "METHOD_CHANGED")

    def test_real_subprocess_reports_bad_profile_and_finishes(self):
        job, _ = self.submit()
        manager = JobManager(self.store)
        manager.start()
        try:
            deadline = time.monotonic() + 8
            status = self.store.get(job["id"], "workspace-a")
            while status["status"] in ("queued", "running") and time.monotonic() < deadline:
                time.sleep(0.025)
                status = self.store.get(job["id"], "workspace-a")
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["error"]["code"], "INPUT_OR_MODEL_ERROR")
            self.assertIn("indataprofil", status["error"]["message"])
            with self.store.connect() as con:
                worker_pid = con.execute("SELECT worker_pid FROM jobs WHERE id=?", (job["id"],)).fetchone()["worker_pid"]
            self.assertNotEqual(worker_pid, os.getpid())
        finally:
            manager.close()


class InputTests(unittest.TestCase):
    def test_linux_stat_parser_handles_comm_spaces_and_parentheses(self):
        fields = ["S", *(["0"] * 18), "987654", "0", "0"]
        stat_text = "123 (worker (nested) name) with extra parentheses)) " + " ".join(fields)
        self.assertEqual(_proc_start_ticks(stat_text), "987654")
        self.assertIsNone(_proc_start_ticks("123 invalid stat"))
        fields[0] = "Z"
        self.assertIsNone(_proc_start_ticks("123 (zombie) " + " ".join(fields)))

    def test_process_identity_includes_boot_namespace_and_start_time(self):
        identity = json.loads(process_identity(os.getpid()))
        self.assertEqual(set(identity), {"boot_id", "namespace_device", "namespace_inode", "start_ticks"})
        self.assertEqual(process_identity(os.getpid()), process_identity(os.getpid()))
        self.assertIsNone(process_identity(-1))

    def test_archive_and_unknown_settings_not_silently_discarded(self):
        body = request_fixture()
        body["input"]["source_archive"] = {"bytes": "private"}
        with self.assertRaises(JobInputError):
            normalize_request(body)
        body = request_fixture()
        body["drafts"] = {"person": {"ssg": 80}}
        body["settings"] = {"some_rule": 12}
        parsed = normalize_request(body)
        self.assertEqual(parsed["scenario"]["drafts"], body["drafts"])
        self.assertEqual(parsed["scenario"]["workspace"], body["settings"])

    def test_malformed_metadata_and_objective_are_readable_errors(self):
        body = request_fixture()
        body["input"]["metadata"] = []
        with self.assertRaises(JobInputError):
            normalize_request(body)
        body = request_fixture()
        body["objective_mode"] = []
        with self.assertRaises(JobInputError):
            normalize_request(body)

    def test_database_must_remain_outside_code_checkout(self):
        with patch.dict(os.environ, {"BB_JOB_DB": str(Path(__file__).resolve().parents[1] / "private.sqlite3")}):
            with self.assertRaises(JobInputError):
                database_path()


class APITests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from bb.api import app
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.temp.name) / "jobs.sqlite3")
        self.profile = Path(self.temp.name) / "profile.json"
        self.profile.write_text('{"profile_id":"test"}')
        self.manager = Mock(store=self.store)
        self.env = patch.dict(os.environ, {"BB_API_TOKEN": "server-only-test-token", "BB_FLORA_PROFILE": str(self.profile)})
        self.env.start()
        self.patch = patch("bb.flora_jobs.get_manager", return_value=self.manager)
        self.patch.start()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer server-only-test-token", "X-BB-Job-Owner": "org-a:workspace-a"}

    def tearDown(self):
        self.patch.stop()
        self.env.stop()
        self.client.close()
        self.temp.cleanup()

    def test_submit_status_poll_and_tenant_isolation(self):
        response = self.client.post("/api/flora/jobs", json=request_fixture(), headers=self.headers)
        self.assertEqual(response.status_code, 202)
        job = response.json()
        self.assertEqual(job["status"], "queued")
        duplicate = self.client.post("/api/flora/jobs", json=request_fixture(), headers=self.headers).json()
        self.assertEqual(duplicate["id"], job["id"])
        self.assertTrue(duplicate["deduplicated"])
        self.assertEqual(self.client.get("/api/flora/jobs/" + job["id"], headers=self.headers).json()["id"], job["id"])
        other = {**self.headers, "X-BB-Job-Owner": "org-b:workspace-b"}
        self.assertEqual(self.client.get("/api/flora/jobs/" + job["id"], headers=other).status_code, 404)
        self.assertNotIn("input", job)

    def test_auth_and_verified_server_owner_required(self):
        self.assertEqual(self.client.post("/api/flora/jobs", json=request_fixture()).status_code, 401)
        token_only = {"Authorization": self.headers["Authorization"]}
        self.assertEqual(self.client.post("/api/flora/jobs", json=request_fixture(), headers=token_only).status_code, 403)

    def test_idempotency_mismatch_returns_conflict(self):
        headers = {**self.headers, "Idempotency-Key": "click-1"}
        first = self.client.post("/api/flora/jobs", json=request_fixture(), headers=headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(self.client.post("/api/flora/jobs", json={**request_fixture(), "seconds": 2}, headers=headers).status_code, 409)

    def test_failed_job_error_stays_visible_on_reload(self):
        job = self.client.post("/api/flora/jobs", json=request_fixture(), headers=self.headers).json()
        job_id, lease = self.store.claim()
        self.store.failure(job_id, lease, "INPUT_OR_MODEL_ERROR", "Behov N1 saknar duration.")
        reloaded = self.client.get("/api/flora/jobs/" + job["id"], headers=self.headers).json()
        self.assertEqual(reloaded["status"], "failed")
        self.assertEqual(reloaded["error"]["message"], "Behov N1 saknar duration.")


if __name__ == "__main__":
    unittest.main()
