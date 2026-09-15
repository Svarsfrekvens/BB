"""Lätt prestandadiagnostik. Ingen instrumentation i CP-SAT-innerloopar."""
from .domain import occurrences, paid


def peak_memory_mb():
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        getter = getattr(ctypes.windll.psapi, 'GetProcessMemoryInfo', None) or getattr(ctypes.windll.kernel32, 'K32GetProcessMemoryInfo', None)
        if getter is None:
            raise OSError('no memory api')
        getter.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
        getter.restype = wintypes.BOOL
        if not getter(handle, ctypes.byref(counters), counters.cb):
            return None
        return round(counters.PeakWorkingSetSize / (1024 * 1024), 1)
    except Exception:
        try:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return round((rss / 1024.0) if rss > 10**6 else rss / 1024.0, 1)
        except Exception:
            return None


def schedule_kpis(data, schedule):
    """Samma definition som appen: täckt behov och kundnära tid. Ej obemannat i täljare."""
    occ = occurrences(data)
    total_need = sum(o['task']['minutes'] * o['count'] for o in occ)
    uncovered = int(schedule.get('uncoveredMinutes') or 0)
    if not uncovered and schedule.get('uncovered'):
        uncovered = sum(int(u.get('count') or 0) * int(u.get('minutes') or 0) for u in schedule['uncovered'])
    covered = max(0, total_need - uncovered)
    paid_m = 0
    for s in schedule.get('shifts') or []:
        paid_m += sum(y - x for x, y in paid(s))
    near_m = sum(max(0, a['end'] - a['start']) for a in schedule.get('assignments') or [])
    if near_m > paid_m:
        near_m = paid_m
    cost = ((schedule.get('objectiveBreakdown') or {}).get('costOre'))
    if cost is None:
        cost = schedule.get('costOre')
    return dict(
        totaltKundbehovMinuter=total_need,
        bemannatKundbehovMinuter=covered,
        coveredNeedPct=round(100.0 * covered / total_need, 2) if total_need else 100.0,
        schematidMinuter=paid_m,
        kundnaraMinuter=near_m,
        customerNearPct=round(100.0 * near_m / paid_m, 2) if paid_m else 0.0,
        scheduleCostOre=int(cost or 0),
    )


def _shift_fingerprint(s):
    return (s.get('id'), s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'), s.get('type'))


def planning_summary(data, schedule, validation=None, performance=None):
    """Stabil sammanfattning för UI. Ingen ny domänlogik."""
    performance = performance or {}
    validation = validation or {}
    kpis = schedule_kpis(data, schedule) if schedule else {}
    coverage = kpis.get('coveredNeedPct')
    if coverage is None:
        coverage = performance.get('coveredNeedPct')
    near = kpis.get('customerNearPct')
    if near is None:
        near = performance.get('customerNearPct')
    cost = kpis.get('scheduleCostOre')
    if cost is None:
        cost = performance.get('scheduleCostOre') or 0
    errors = list(validation.get('errors') or [])
    hard = [e for e in errors if e.get('rule') != 'BOUNDARY_INCOMPLETE']
    warns = list(validation.get('warnings') or [])
    for note in schedule.get('feasibilityNotes') or []:
        warns.append({'rule': 'NOTE', 'message': note})
    for d in schedule.get('preCheck') or []:
        sev = d.get('severity')
        row = {'rule': d.get('code') or 'PRECHECK', 'message': d.get('message') or ''}
        if sev == 'critical':
            hard.append(row)
        elif sev == 'warning' or sev is None:
            warns.append(row)
    if (schedule or {}).get('solverStatus') == 'INFEASIBLE':
        hard = hard or [{'rule': 'INFEASIBLE', 'message': (schedule.get('explanation') or '')[:180]}]
    old = ((data.get('existingSchedule') or data.get('current') or {}).get('shifts') if isinstance(data.get('existingSchedule') or data.get('current'), dict) else None) or []
    old_by = {s.get('id'): _shift_fingerprint(s) for s in old if s.get('id')}
    changed = 0
    for s in schedule.get('shifts') or []:
        fp = _shift_fingerprint(s)
        prev = old_by.get(s.get('id'))
        if prev != fp:
            changed += 1
    expl = (schedule.get('explanation') or '').strip()
    summary_line = expl.split('.')[0].strip()
    if summary_line and not summary_line.endswith('.'):
        summary_line += '.'
    total_ms = performance.get('totalMs') or performance.get('totalTimeMs') or 0
    status = (schedule or {}).get('solverStatus') or performance.get('solverStatus') or 'NOT_RUN'
    perf_line = f"{status}, {coverage if coverage is not None else '–'} % täckt behov, {round((total_ms or 0)/1000, 1)} s"
    return dict(
        status=status,
        coveragePercent=coverage,
        customerNearPercent=near,
        cost=int(cost or 0),
        hardViolations=[{'rule': e.get('rule'), 'message': e.get('message')} for e in hard],
        warnings=[{'rule': w.get('rule'), 'message': w.get('message')} for w in warns],
        changedShiftCount=changed,
        lockedShiftCount=int(performance.get('lockedShifts') or 0),
        explanationSummary=summary_line,
        performanceSummary=perf_line,
    )
