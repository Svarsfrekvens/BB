"""Deterministisk live-omplanering: berördhet och låsta pass.

Godkänt schema → förändring → öppna minsta intervall → lås övrigt → CP-SAT
på berörd del. Boundary, REST, veckovila och F-01 ser fortfarande låsta pass.
Låsta pass hävs aldrig tyst.
"""
from .domain import add_days, days, instant, overlap, span
from .generate import planning_day_bounds


def approved_shifts(data):
    src = data.get('existingSchedule')
    if src is None:
        src = data.get('approvedSchedule') or data.get('current') or {}
    if not isinstance(src, dict):
        return []
    return list(src.get('shifts') or [])


def shift_start_day(shift):
    return shift.get('date')


def collect_locked_shifts(data):
    """Pass som CP-SAT måste återanvända exakt. Hävs inte vid INFEASIBLE."""
    wanted = set(data.get('lockedShiftIds') or [])
    lock_out = bool(data.get('lockedOutsidePlanningRange'))
    pstart, pend = planning_day_bounds(data)
    wp = data['workplace']
    locked = []
    seen = set()
    for s in approved_shifts(data):
        sid = s.get('id')
        day = shift_start_day(s)
        if not sid or not day or sid in seen:
            continue
        if day < wp['start'] or day > wp['end']:
            continue
        outside = day < pstart or day > pend
        if sid in wanted or (lock_out and outside):
            locked.append(s)
            seen.add(sid)
    return locked


def _clip_days(open_days, wp):
    clipped = [d for d in open_days if wp['start'] <= d <= wp['end']]
    if not clipped:
        return wp['start'], wp['end'], []
    return min(clipped), max(clipped), sorted(set(clipped))


def impact_from_change(data, change):
    """Vilka datum/personer som minst måste öppnas. Ingen AI, bara regler.

    Frånvaro öppnar personen, de dagarna, ±1 dag för dygnsvila och de pass
    som personen hade. Kundbehov öppnar berörda datum. Hela perioden öppnas
    inte automatiskt; F-01/REST/WEEK_REST sköts via låsta pass utanför.
    """
    wp = data['workplace']
    kind = (change or {}).get('type') or 'need'
    open_days = set()
    employees = set()
    shifts_hit = []

    if kind == 'absence':
        employees.add(change['employeeId'])
        for day in days(change['start'], change['end']):
            open_days.add(day)
            open_days.add(add_days(day, -1))
            open_days.add(add_days(day, 1))
        for s in approved_shifts(data):
            if s.get('employeeId') != change['employeeId']:
                continue
            a, b = span(s)
            lo, hi = instant(change['start'], '00:00'), instant(add_days(change['end'], 1), '00:00')
            if overlap(a, b, lo, hi) or s.get('date') in open_days:
                shifts_hit.append(s['id'])
                open_days.add(s['date'])
    elif kind in ('need', 'customerNeed', 'customer'):
        start = change.get('start') or change.get('date') or wp['start']
        end = change.get('end') or change.get('date') or start
        cid = change.get('customerId')
        for day in days(start, end):
            open_days.add(day)
        for s in approved_shifts(data):
            if s.get('date') < start or s.get('date') > end:
                continue
            if cid and cid not in (s.get('customerIds') or []):
                continue
            shifts_hit.append(s['id'])
            employees.add(s.get('employeeId'))
    elif kind in ('ssg', 'skill', 'constraint', 'employee'):
        employees.add(change['employeeId'])
        start = change.get('start') or wp['start']
        end = change.get('end') or wp['end']
        for s in approved_shifts(data):
            if s.get('employeeId') == change['employeeId'] and start <= s.get('date') <= end:
                open_days.add(s['date'])
                shifts_hit.append(s['id'])
        if not open_days:
            open_days.update(days(start, end) if start != wp['start'] or end != wp['end'] else [wp['start']])
    else:
        start = change.get('start') or change.get('date') or wp['start']
        end = change.get('end') or start
        open_days.update(days(start, end))

    start, end, ordered = _clip_days(open_days, wp)
    return dict(
        planningRange=dict(start=start, end=end),
        lockedOutsidePlanningRange=True,
        affectedEmployeeIds=sorted(e for e in employees if e),
        affectedDates=ordered,
        affectedShiftIds=shifts_hit,
        reason=kind,
    )


def apply_impact(data, change):
    """Sätter planningRange och låsning utifrån en förändring. Muterar inte hårda regler."""
    impact = impact_from_change(data, change)
    data['planningRange'] = impact['planningRange']
    data['lockedOutsidePlanningRange'] = True
    return impact
