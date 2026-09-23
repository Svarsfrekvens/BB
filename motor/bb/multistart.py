"""28d async multi-start. Samma support_z-solve, annan körordning."""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import tempfile
import traceback
from copy import deepcopy
from pathlib import Path

from .domain import days

MULTI_START_WORKERS = 4
MULTI_START_SECONDS = 240
MULTI_START_SEEDS = (41, 42, 43, 44)
SKILL_RULES = frozenset(('TASK_SKILL', 'SKILL'))


def is_28d_period(data):
    wp = (data or {}).get('workplace') or {}
    start, end = wp.get('start'), wp.get('end')
    if not start or not end:
        return False
    return len(list(days(start, end))) == 28


def uncovered_minutes(result):
    if not result:
        return None
    sched = result.get('schedule') or {}
    raw = sched.get('uncoveredMinutes')
    if raw is None:
        raw = (sched.get('lexicographic') or {}).get('uncoveredMinutes')
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def has_incumbent(result):
    sched = (result or {}).get('schedule') or {}
    if str(sched.get('solverStatus') or '') not in ('FEASIBLE', 'OPTIMAL'):
        return False
    return bool(sched.get('shifts') or sched.get('assignments'))


def _errors(result):
    val = (result or {}).get('validation') or {}
    return list(val.get('errors') or [])


def godkannbar_resultat(result):
    if not has_incumbent(result):
        return False
    if uncovered_minutes(result) != 0:
        return False
    errs = _errors(result)
    if errs:
        return False
    if any(e.get('rule') in SKILL_RULES for e in errs):
        return False
    val = (result or {}).get('validation') or {}
    if val.get('valid') is False:
        return False
    return True


def _rank(result):
    if not result or not has_incumbent(result):
        return (-1, -1, -10**12)
    godk = 1 if godkannbar_resultat(result) else 0
    hard = 0 if not _errors(result) else 1
    unc = uncovered_minutes(result)
    cov = 0 if unc is None else -int(unc)
    return (godk, 0 if hard == 0 else -1, cov)


def _better(candidate, best):
    if best is None:
        return True
    return _rank(candidate) > _rank(best)


def solve_attempt_worker(data, seconds, workers, seed, out_path):
    payload = dict(__ok=False)
    try:
        from bb.solver import solve

        result = solve(
            data,
            seconds,
            sat_params=dict(num_search_workers=int(workers), random_seed=int(seed)),
            occurrence_encoding='support_z',
        )
        payload = dict(__ok=True, result=result)
    except Exception as exc:
        payload = dict(__ok=False, error=f'{type(exc).__name__}: {exc}', trace=traceback.format_exc())
    Path(out_path).write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding='utf-8')


def run_solve_attempt(data, seconds, workers, seed):
    """Ett försök i egen process. Ingen warm start."""
    ctx = mp.get_context('spawn')
    fd, raw_path = tempfile.mkstemp(prefix='bb_ms_', suffix='.json')
    os.close(fd)
    out_path = raw_path
    proc = ctx.Process(
        target=solve_attempt_worker,
        args=(deepcopy(data), float(seconds), int(workers), int(seed), out_path),
        daemon=True,
    )
    proc.start()
    proc.join(timeout=float(seconds) + 180.0)
    if proc.is_alive():
        proc.terminate()
        proc.join(20)
        try:
            Path(out_path).unlink(missing_ok=True)
        except OSError:
            pass
        return None, 'försöket överskred tidsgränsen'
    try:
        blob = Path(out_path).read_text(encoding='utf-8')
        payload = json.loads(blob) if blob else {}
    except (OSError, json.JSONDecodeError) as exc:
        payload = dict(__ok=False, error=str(exc))
    try:
        Path(out_path).unlink(missing_ok=True)
    except OSError:
        pass
    if proc.exitcode not in (0, None) and not payload.get('__ok'):
        return None, payload.get('error') or f'processfel {proc.exitcode}'
    if not payload.get('__ok'):
        return None, payload.get('error') or 'försöket misslyckades'
    return payload.get('result'), None


def run_28d_job(job, set_fields):
    """Sekventiell 4×240 s. set_fields uppdaterar jobbstatus till UI."""
    data = job['data']
    best = None
    tried = []
    stopped = None
    for i, seed in enumerate(MULTI_START_SEEDS):
        text = 'Skapar balans' if i == 0 else 'Förbättrar balans'
        set_fields(job, status='solving', phase='solving', phaseText=text)
        result, err = run_solve_attempt(data, MULTI_START_SECONDS, MULTI_START_WORKERS, seed)
        set_fields(job, status='validating', phase='validating', phaseText='Kontrollerar resultat')
        row = dict(seed=seed, error=err, godkannbar=False, uncoveredMinutes=None)
        if err or not result:
            tried.append(row)
            continue
        row['godkannbar'] = godkannbar_resultat(result)
        row['uncoveredMinutes'] = uncovered_minutes(result)
        tried.append(row)
        if _better(result, best):
            best = result
        if row['godkannbar']:
            stopped = seed
            break
    if best is not None:
        diag = dict(best.get('diagnostics') or {})
        diag['multiStart'] = dict(
            workers=MULTI_START_WORKERS,
            attemptSeconds=MULTI_START_SECONDS,
            seeds=list(MULTI_START_SEEDS),
            seedsTried=[t['seed'] for t in tried],
            stoppedAtSeed=stopped,
            encoding='support_z',
        )
        best['diagnostics'] = diag
    return best, tried, stopped
