"""In-memory asynkron optimeringskö för piloten. Ändrar inte solve()."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from time import perf_counter
from uuid import uuid4

from .solver import solve

_JOBS = {}
_LOCK = threading.Lock()
_MAX_JOBS = 8


def reset_jobs_for_tests():
    with _LOCK:
        _JOBS.clear()

PHASE_TEXT = {
    'queued': 'Köar beräkningen',
    'preparing': 'Förbereder underlag',
    'checking': 'Kontrollerar styrande villkor',
    'solving': 'Söker bästa möjliga bemanning',
    'validating': 'Kontrollerar resultat',
    'completed': 'Balans klar',
    'failed': 'Kunde inte skapa Balans',
}


def async_jobs_enabled():
    return os.environ.get('BB_ASYNC_JOBS', '').strip().lower() in ('1', 'true', 'yes', 'on')


def input_fingerprint(data):
    blob = json.dumps(data, sort_keys=True, default=str, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:24]


def _trim():
    if len(_JOBS) <= _MAX_JOBS:
        return
    done = [j for j in _JOBS.values() if j.get('status') in ('completed', 'failed')]
    done.sort(key=lambda j: j.get('updatedAt') or 0)
    for j in done[: max(0, len(_JOBS) - _MAX_JOBS)]:
        _JOBS.pop(j['id'], None)


def find_active(fingerprint):
    with _LOCK:
        for j in _JOBS.values():
            if j.get('inputHash') == fingerprint and j.get('status') not in ('completed', 'failed'):
                return j
        return None


def get_job(job_id):
    with _LOCK:
        return _JOBS.get(job_id)


def create_job(data, seconds):
    job = dict(
        id=str(uuid4()),
        status='queued',
        phase='queued',
        inputHash=input_fingerprint(data),
        inputRevision=data.get('inputRevision'),
        seconds=seconds,
        data=data,
        trace=[],
        result=None,
        error=None,
        outcome=None,
        reused=False,
        createdAt=perf_counter(),
        updatedAt=perf_counter(),
        startedAt=None,
        incumbents=0,
    )
    with _LOCK:
        _JOBS[job['id']] = job
        _trim()
    return job


def _set(job, **fields):
    with _LOCK:
        job.update(fields)
        job['updatedAt'] = perf_counter()


def _progress(job):
    rows = list(job.get('trace') or [])
    last = next((r for r in reversed(rows) if r.get('event') == 'incumbent'), None)
    elapsed = None
    if job.get('startedAt'):
        elapsed = round(perf_counter() - job['startedAt'], 1)
    out = dict(
        incumbents=len(rows),
        elapsedS=elapsed,
        uncoveredMinutes=None,
        bound=None,
    )
    if last:
        out['uncoveredMinutes'] = last.get('incumbent')
        out['bound'] = last.get('bound')
    return out


def classify(result):
    if not result:
        return 'tekniskt_fel'
    sched = result.get('schedule') or {}
    val = result.get('validation')
    status = str(sched.get('solverStatus') or '')
    jour = (result.get('resourceDiagnostics') or {}).get('jour') or (sched.get('resourceDiagnostics') or {}).get('jour') or {}
    if jour.get('jourCapacityShortfallDetected'):
        return 'kompletteras'
    valid = bool(val and val.get('valid'))
    if status == 'OPTIMAL' and valid:
        return 'balans_klar'
    if status in ('FEASIBLE', 'OPTIMAL') and (valid or val is None):
        return 'basta_hittade'
    if status in ('INFEASIBLE', 'MODEL_INVALID'):
        return 'kompletteras' if jour else 'tekniskt_fel'
    return 'tekniskt_fel'


def execute(job):
    _set(job, status='preparing', phase='preparing', startedAt=perf_counter())
    _set(job, phase='checking')
    trace = job['trace']
    _set(job, status='solving', phase='solving')
    try:
        result = solve(job['data'], job.get('seconds') or 30, coverage_trace=trace)
    except Exception as exc:
        _set(job, status='failed', phase='failed', error=str(exc), outcome='tekniskt_fel', result=None)
        return job
    _set(job, status='validating', phase='validating')
    outcome = classify(result)
    if outcome == 'tekniskt_fel' and not (result.get('schedule') or {}).get('shifts'):
        status = 'failed'
        phase = 'failed'
    else:
        status = 'completed'
        phase = 'completed'
    _set(job, status=status, phase=phase, result=result, outcome=outcome, incumbents=len(trace))
    job.pop('data', None)
    return job


def public_view(job, include_result=False):
    if not job:
        return None
    progress = _progress(job)
    still = job.get('phase') == 'solving' and (progress.get('incumbents') or 0) >= 0
    view = dict(
        jobId=job['id'],
        status=job.get('status'),
        phase=job.get('phase'),
        phaseText=PHASE_TEXT.get(job.get('phase') or '', ''),
        stillSearching=bool(still and job.get('phase') == 'solving'),
        inputHash=job.get('inputHash'),
        inputRevision=job.get('inputRevision'),
        reused=bool(job.get('reused')),
        outcome=job.get('outcome'),
        error=job.get('error'),
        progress=progress,
        seconds=job.get('seconds'),
    )
    if include_result and job.get('status') in ('completed', 'failed'):
        view['result'] = job.get('result')
    return view
