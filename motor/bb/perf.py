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
