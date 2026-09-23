"""Filbaserad job store. Ingen solverlogik."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

PERSIST_KEYS = (
    'id',
    'inputHash',
    'status',
    'phase',
    'phaseText',
    'outcome',
    'createdAtIso',
    'updatedAtIso',
    'startedAtIso',
    'error',
    'inputRevision',
    'seconds',
)
TERMINAL = frozenset(('completed', 'failed'))
KEEP_TERMINAL = 16
PROTECT_SECONDS = 6 * 3600
RESTART_TEXT = 'Beräkningen avbröts när tjänsten startades om. Skapa balans igen.'


def store_dir():
    raw = (os.environ.get('BB_JOB_STORE_DIR') or '').strip()
    return Path(raw) if raw else None


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_iso(raw):
    if not raw or not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        return None


def snapshot(job):
    rec = {k: job.get(k) for k in PERSIST_KEYS}
    rec['id'] = job.get('id')
    if job.get('status') in TERMINAL:
        rec['result'] = job.get('result')
    else:
        rec['result'] = None
    return rec


def atomic_write(path: Path, rec: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    blob = json.dumps(rec, ensure_ascii=False, default=str)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fd = None
            fh.write(blob)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        if fd is not None:
            os.close(fd)
    os.replace(str(tmp), str(path))


def job_path(directory: Path, job_id: str):
    safe = ''.join(ch for ch in str(job_id) if ch.isalnum() or ch in '-_')
    if not safe or safe != str(job_id):
        raise ValueError('Ogiltigt jobb-id.')
    return directory / f'{safe}.json'


def write_job(job):
    d = store_dir()
    if not d or not job.get('id'):
        return []
    rec = snapshot(job)
    atomic_write(job_path(d, job['id']), rec)
    return apply_retention(d)


def read_all(directory: Path):
    rows = []
    for path in directory.glob('*.json'):
        try:
            rec = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(rec, dict) or not rec.get('id'):
            continue
        rows.append((path, rec))
    return rows


def fail_closed(rec):
    rec = dict(rec)
    rec['status'] = 'failed'
    rec['phase'] = 'failed'
    rec['outcome'] = 'tekniskt_fel'
    rec['result'] = None
    rec['error'] = RESTART_TEXT
    rec['phaseText'] = RESTART_TEXT
    rec['updatedAtIso'] = now_iso()
    rec.pop('data', None)
    rec['trace'] = []
    return rec


def hydrate(rec):
    rec = dict(rec)
    rec.pop('data', None)
    rec['trace'] = []
    rec['reused'] = False
    rec.setdefault('incumbents', 0)
    rec.setdefault('createdAt', 0)
    rec.setdefault('updatedAt', 0)
    rec.setdefault('startedAt', None)
    if rec.get('status') not in TERMINAL:
        rec = fail_closed(rec)
    return rec


def apply_retention(directory: Path):
    now = datetime.now(timezone.utc)
    protected = []
    older = []
    for path, rec in read_all(directory):
        if rec.get('status') not in TERMINAL:
            continue
        ts = parse_iso(rec.get('updatedAtIso'))
        age = (now - ts).total_seconds() if ts else 10 ** 12
        item = (path, rec, ts or datetime.min.replace(tzinfo=timezone.utc), age)
        if age < PROTECT_SECONDS:
            protected.append(item)
        else:
            older.append(item)
    older.sort(key=lambda x: x[2], reverse=True)
    slots = max(0, KEEP_TERMINAL - len(protected))
    drop = older[slots:]
    dropped = []
    for path, rec, _ts, _age in drop:
        try:
            path.unlink()
        except OSError:
            pass
        dropped.append(rec.get('id'))
    return dropped
