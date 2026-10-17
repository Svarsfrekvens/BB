"""Durable, local-first background jobs for computed Flora proposals.

The database belongs outside the source checkout. Input is private, is never
logged, and is read by a separate bounded worker process after HTTP submission.
The shared service token authenticates the app server, not individual tenants:
the app server must verify tenant access before supplying X-BB-Job-Owner.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager


METHOD_VERSION = "flora-reassignment/1.0"
OBJECTIVES = {"coverage_then_temporary", "coverage_then_workload_then_temporary"}
MAX_SECONDS = 300
_MANAGERS: dict[str, "JobManager"] = {}
_MANAGERS_LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def method_fingerprint() -> str:
    """Cache identity follows actual implementation, not only its display name."""
    root = Path(__file__).resolve().parent
    files = [root / "flora_import.py", root / "business_profiles.py",
             root / "engine_api.py", root / "flora_jobs.py", *sorted((root / "flora").glob("*.py"))]
    content = hashlib.sha256(METHOD_VERSION.encode())
    for path in files:
        if path.is_file():
            content.update(str(path.relative_to(root)).encode())
            content.update(path.read_bytes())
    return content.hexdigest()


def _proc_start_ticks(stat_text: str) -> str | None:
    """Read Linux stat field 22 without splitting the parenthesized comm.

    comm may itself contain spaces and parentheses. The final closing
    parenthesis precedes field 3 (state), so starttime is tail item 19.
    """
    end = stat_text.rfind(")")
    if end < 0:
        return None
    fields = stat_text[end + 1:].split()
    if len(fields) <= 19 or fields[0] in {"Z", "X", "x"} or not fields[19].isdigit():
        return None
    return fields[19]


def process_identity(pid: int | None) -> str | None:
    """Identity survives checks but cannot mistake reused/container PIDs.

    The persistent database may outlive a container and its PID namespace.
    A numeric PID, even a currently live PID 1, is therefore not a lease.
    """
    if type(pid) is not int or pid <= 0:
        return None
    try:
        proc = Path("/proc") / str(pid)
        start_ticks = _proc_start_ticks((proc / "stat").read_text())
        namespace = (proc / "ns/pid").stat()
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        # Re-read start time after the other observations, failing closed if
        # the process exited/reused its PID during the identity read itself.
        if not start_ticks or not boot_id or start_ticks != _proc_start_ticks((proc / "stat").read_text()):
            return None
        return canonical(dict(boot_id=boot_id, namespace_device=namespace.st_dev,
                              namespace_inode=namespace.st_ino, start_ticks=start_ticks))
    except (OSError, ValueError):
        return None


class JobInputError(ValueError):
    pass


class IdempotencyConflict(JobInputError):
    pass


def normalize_request(body: dict) -> dict:
    if not isinstance(body, dict) or not isinstance(body.get("input"), dict):
        raise JobInputError("Underlaget saknas. Skicka ett inläst BB-underlag i input.")
    source = body["input"]
    if source.get("source_archive") is not None:
        raise JobInputError("Originalarkivet ska stanna i webbläsaren. Skicka endast de inlästa uppgifterna.")
    if not isinstance(source.get("metadata"), dict) or source["metadata"].get("schema_version") not in ("flora-bb-input/1.0", "bb-input/1.0"):
        raise JobInputError("Okänt underlagsformat. Skicka ett normaliserat BB-underlag från appens import.")
    for field in ("staff", "customers", "schedule_segments", "customer_needs", "business_rules"):
        if not isinstance(source.get(field), list):
            raise JobInputError(f"Underlaget saknar listan {field}.")
    if len(source["customer_needs"]) > 20000 or len(source["schedule_segments"]) > 20000:
        raise JobInputError("Underlaget är för stort för den här testmiljön.")
    seconds = body.get("seconds", 30)
    if type(seconds) not in (int, float) or not 1 <= seconds <= MAX_SECONDS:
        raise JobInputError("Körtiden ska vara mellan 1 och 300 sekunder per söksteg.")
    objective = body.get("objective_mode", "coverage_then_temporary")
    if not isinstance(objective, str) or objective not in OBJECTIVES:
        raise JobInputError("Okänd beräkningsinriktning.")
    scenario = body.get("scenario", {})
    if scenario is None:
        scenario = {}
    if not isinstance(scenario, dict):
        raise JobInputError("Scenarioinställningarna har fel format.")
    if body.get("drafts") is not None or body.get("settings") is not None:
        if not isinstance(scenario.get("workspace", {}), dict):
            raise JobInputError("Arbetskopians scenarioinställningar har fel format.")
        if not isinstance(body.get("drafts", {}), dict) or not isinstance(body.get("settings", {}), dict):
            raise JobInputError("Personutkast och arbetsinställningar måste vara objekt.")
        scenario = {**scenario, "drafts": body.get("drafts", {}),
                    "workspace": {**scenario.get("workspace", {}), **body.get("settings", {})}}
    retry_of = body.get("retry_of")
    if retry_of is not None and not re.fullmatch(r"[a-f0-9]{32}", str(retry_of)):
        raise JobInputError("Ogiltig tidigare körning för nytt försök.")
    out = dict(input=source, scenario=scenario, seconds=float(seconds), objective_mode=objective)
    if retry_of:
        out["retry_of"] = retry_of
    # Reject NaN and objects outside the JSON contract before saving anything.
    canonical(out)
    return out


def load_profile() -> tuple[dict, str]:
    configured = os.environ.get("BB_FLORA_PROFILE", "").strip()
    if not configured:
        raise JobInputError("Floras beslutade testprofil är inte ansluten till beräkningstjänsten (BB_FLORA_PROFILE).")
    try:
        content = Path(configured).read_bytes()
        profile = json.loads(content)
    except (OSError, ValueError) as exc:
        raise JobInputError("Floras testprofil kunde inte läsas. Kontrollera serverns inställning.") from exc
    if not isinstance(profile, dict):
        raise JobInputError("Floras testprofil har fel format.")
    return profile, hashlib.sha256(content).hexdigest()


def database_path() -> Path:
    configured = os.environ.get("BB_JOB_DB", "").strip()
    path = Path(configured) if configured else Path(tempfile.gettempdir()) / f"bb-flora-jobs-{os.getuid()}" / "jobs.sqlite3"
    if not path.is_absolute():
        raise JobInputError("BB_JOB_DB måste vara en absolut sökväg utanför kodarkivet.")
    checkout = Path(__file__).resolve().parents[1]
    if path.resolve().is_relative_to(checkout):
        raise JobInputError("Körningsdatabasen måste sparas utanför kodarkivet.")
    return path


class JobStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        parent = Path(path).parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, dedup TEXT NOT NULL,
                input_hash TEXT NOT NULL, profile_hash TEXT NOT NULL,
                request_json TEXT NOT NULL, profile_json TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, error_json TEXT, result_json TEXT,
                runner_pid INTEGER, worker_pid INTEGER, lease TEXT,
                UNIQUE(owner,dedup))""")
            columns = {r["name"] for r in con.execute("PRAGMA table_info(jobs)")}
            if "client_key" not in columns:
                con.execute("ALTER TABLE jobs ADD COLUMN client_key TEXT")
            if "method_hash" not in columns:
                con.execute("ALTER TABLE jobs ADD COLUMN method_hash TEXT")
            if "runner_identity" not in columns:
                con.execute("ALTER TABLE jobs ADD COLUMN runner_identity TEXT")
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS jobs_client_key ON jobs(owner,client_key) WHERE client_key IS NOT NULL")
            con.execute("""CREATE TABLE IF NOT EXISTS job_keys (
                owner TEXT NOT NULL, client_key TEXT NOT NULL, job_id TEXT NOT NULL,
                PRIMARY KEY(owner,client_key))""")
            con.execute("INSERT OR IGNORE INTO job_keys SELECT owner,client_key,id FROM jobs WHERE client_key IS NOT NULL")
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=10000")
        try:
            with con:
                yield con
        finally:
            con.close()

    @staticmethod
    def public(row) -> dict:
        return dict(id=row["id"], status=row["status"], input_hash=row["input_hash"],
                    method_version=METHOD_VERSION, created_at=row["created_at"],
                    method_fingerprint=row["method_hash"],
                    started_at=row["started_at"], finished_at=row["finished_at"],
                    error=json.loads(row["error_json"]) if row["error_json"] else None,
                    result=json.loads(row["result_json"]) if row["result_json"] else None)

    def get(self, job_id: str, owner: str) -> dict | None:
        with self.connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=? AND owner=?", (job_id, owner)).fetchone()
        return self.public(row) if row else None

    def submit(self, owner: str, request: dict, profile: dict, profile_hash: str, client_key: str | None = None) -> tuple[dict, bool]:
        input_hash = digest(request["input"])
        method_hash = method_fingerprint()
        dedup = digest(dict(request=request, profile_hash=profile_hash, method=METHOD_VERSION, method_hash=method_hash))
        if request.get("retry_of"):
            previous = self.get(request["retry_of"], owner)
            if not previous or previous["status"] != "failed":
                raise JobInputError("Ett nytt försök kräver en misslyckad körning i samma arbetsyta.")
        job_id = uuid.uuid4().hex
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            if client_key:
                old = con.execute("""SELECT j.* FROM jobs j JOIN job_keys k ON j.id=k.job_id
                                     WHERE k.owner=? AND k.client_key=?""", (owner, client_key)).fetchone()
                if old:
                    if old["dedup"] != dedup:
                        raise IdempotencyConflict("Samma körningsnyckel har använts för ändrade uppgifter. Skapa en ny körning.")
                    return self.public(old), False
            cur = con.execute("""INSERT OR IGNORE INTO jobs
                (id,owner,dedup,input_hash,profile_hash,request_json,profile_json,status,created_at,client_key,method_hash)
                VALUES (?,?,?,?,?,?,?,'queued',?,?,?)""",
                (job_id, owner, dedup, input_hash, profile_hash, canonical(request), canonical(profile), now(), client_key, method_hash))
            created = cur.rowcount == 1
            row = con.execute("SELECT * FROM jobs WHERE owner=? AND dedup=?", (owner, dedup)).fetchone()
            if client_key:
                con.execute("INSERT INTO job_keys(owner,client_key,job_id) VALUES (?,?,?)", (owner, client_key, row["id"]))
        return self.public(row), created

    def claim(self) -> tuple[str, str] | None:
        lease = uuid.uuid4().hex
        identity = process_identity(os.getpid())
        if not identity:
            raise JobInputError("Körmiljön saknar verifierbar Linux-processidentitet. Jobbkön kan inte startas säkert.")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            # This limit is global to the database, including two accidental
            # API processes. A Python-thread lock alone would not protect it.
            if con.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
                return None
            row = con.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            con.execute("UPDATE jobs SET status='running',started_at=?,runner_pid=?,runner_identity=?,lease=? WHERE id=? AND status='queued'",
                        (now(), os.getpid(), identity, lease, row["id"]))
        return row["id"], lease

    def failure(self, job_id: str, lease: str, code: str, message: str):
        with self.connect() as con:
            con.execute("""UPDATE jobs SET status='failed',finished_at=?,error_json=?
                           WHERE id=? AND lease=? AND status='running'""",
                        (now(), canonical(dict(code=code, message=message)), job_id, lease))

    def recover_interrupted(self) -> int:
        """A killed API server cannot leave a job apparently running forever."""
        recovered = 0
        with self.connect() as con:
            for row in con.execute("SELECT id,lease,runner_pid,runner_identity FROM jobs WHERE status='running'").fetchall():
                actual = process_identity(row["runner_pid"])
                if not row["runner_identity"] or actual != row["runner_identity"]:
                    con.execute("UPDATE jobs SET status='failed',finished_at=?,error_json=? WHERE id=? AND status='running'",
                                (now(), canonical(dict(code="INTERRUPTED", message="Beräkningstjänsten startades om. Inget färdigt förslag finns; gör ett nytt försök.")), row["id"]))
                    recovered += 1
        return recovered


class JobManager:
    def __init__(self, store: JobStore):
        self.store = store
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.current: tuple[str, str, subprocess.Popen] | None = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not process_identity(os.getpid()):
            raise JobInputError("Körmiljön saknar verifierbar Linux-processidentitet. Jobbkön kan inte startas säkert.")
        self.store.recover_interrupted()
        self.thread = threading.Thread(target=self.run, name="flora-job-dispatcher", daemon=True)
        self.thread.start()

    def wake(self):
        self.wake_event.set()

    def run(self):
        while not self.stop_event.is_set():
            claimed = self.store.claim()
            if not claimed:
                self.store.recover_interrupted()
                self.wake_event.wait(0.5)
                self.wake_event.clear()
                continue
            job_id, lease = claimed
            try:
                with self.store.connect() as con:
                    row = con.execute("SELECT request_json FROM jobs WHERE id=?", (job_id,)).fetchone()
                request = json.loads(row["request_json"])
                # Up to four separately budgeted optimization stages, plus build,
                # independent validation and bounded startup margin.
                timeout = 4 * request["seconds"] + 120
                process = subprocess.Popen(
                    [sys.executable, "-m", "bb.flora_jobs", "worker", self.store.path, job_id, lease],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env={**os.environ, "PYTHONUNBUFFERED": "1"},
                )
                self.current = (job_id, lease, process)
                with self.store.connect() as con:
                    con.execute("UPDATE jobs SET worker_pid=? WHERE id=? AND lease=?", (process.pid, job_id, lease))
                deadline = time.monotonic() + timeout
                while process.poll() is None and not self.stop_event.wait(0.1):
                    if time.monotonic() >= deadline:
                        process.kill()
                        process.wait(timeout=5)
                        self.store.failure(job_id, lease, "WORKER_TIMEOUT", "Beräkningen nådde tjänstens tidsgräns utan ett färdigt resultat. Det bevisar inte att ett schema är omöjligt.")
                        break
                if self.stop_event.is_set() and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    self.store.failure(job_id, lease, "INTERRUPTED", "Beräkningstjänsten stoppades. Gör ett nytt försök.")
                elif process.returncode:
                    self.store.failure(job_id, lease, "WORKER_FAILED", "Beräkningen kunde inte slutföras. Underlaget och tidigare förslag har bevarats.")
                else:
                    self.store.failure(job_id, lease, "WORKER_NO_RESULT", "Beräkningen avslutades utan ett färdigt resultat. Gör ett nytt försök; inget schema har godkänts.")
            except Exception:
                self.store.failure(job_id, lease, "WORKER_START_FAILED", "Beräkningstjänsten kunde inte starta körningen. Försök igen eller kontrollera testmiljön.")
            finally:
                self.current = None

    def close(self):
        self.stop_event.set()
        self.wake_event.set()
        if self.thread:
            self.thread.join(timeout=8)


def get_manager() -> JobManager:
    path = str(database_path())
    with _MANAGERS_LOCK:
        manager = _MANAGERS.get(path)
        if not manager or manager.stop_event.is_set():
            manager = JobManager(JobStore(path))
            manager.start()
            _MANAGERS[path] = manager
        return manager


def close_managers():
    with _MANAGERS_LOCK:
        for manager in _MANAGERS.values():
            manager.close()
        _MANAGERS.clear()


def run_worker(path: str, job_id: str, lease: str):
    store = JobStore(path)
    with store.connect() as con:
        row = con.execute("SELECT * FROM jobs WHERE id=? AND lease=? AND status='running'", (job_id, lease)).fetchone()
    if not row:
        return
    try:
        if row["method_hash"] and row["method_hash"] != method_fingerprint():
            store.failure(job_id, lease, "METHOD_CHANGED", "Beräkningskoden ändrades efter att körningen skapades. Starta en ny körning med aktuellt underlag.")
            return
        request = json.loads(row["request_json"])
        profile = json.loads(row["profile_json"])
        from .flora_import import prepare_case
        from .flora import solve_case, validate_case
        case = prepare_case(request["input"], profile, request["scenario"])
        started = time.monotonic()
        result = solve_case(case, seconds=request["seconds"], workers=2,
                            objective_mode=request["objective_mode"])
        result["validation"] = validate_case(case, result)
        result["input_hash"] = row["input_hash"]
        result["provenance"] = {**result.get("provenance", {}), "input_hash": row["input_hash"],
                                "profile_hash": row["profile_hash"], "method_version": METHOD_VERSION,
                                "method_fingerprint": row["method_hash"],
                                "job_id": job_id, "calculation_seconds": time.monotonic() - started,
                                "requires_review": True,
                                "engine_context": request.get("engine_context"),
                                "automatic_learning": False}
        with store.connect() as con:
            con.execute("UPDATE jobs SET status='succeeded',finished_at=?,result_json=? WHERE id=? AND lease=? AND status='running'",
                        (now(), canonical(result), job_id, lease))
    except ValueError as exc:
        # Import and domain errors are deliberately user-facing, source-linked
        # messages. Unexpected tracebacks and private inputs never enter logs.
        store.failure(job_id, lease, "INPUT_OR_MODEL_ERROR", str(exc)[:2000])
    except Exception:
        store.failure(job_id, lease, "CALCULATION_FAILED", "Beräkningen kunde inte slutföras i testmiljön. Underlaget är bevarat; inget schema har godkänts.")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "worker":
        run_worker(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("Use python -m bb.flora_jobs worker DATABASE JOB_ID LEASE")
