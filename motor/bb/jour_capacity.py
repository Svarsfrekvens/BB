"""Diagnos av obligatorisk jourkapacitet. Ändrar inte jourregler eller golv.

Precheck före full schema-CP-SAT. Extern slack är bara diagnostik och blir
aldrig en employee i den riktiga optimeringen.
"""
from .domain import (
    active_employees, add_days, days, hard_constraints, instant, jour_eligible,
    jour_intervals, overlap, parts, remaining_capacity, span,
)
from .generate import planning_day_bounds, shift_templates_for_solve
from .replan import collect_locked_shifts


JOUR_4W_LIMIT = 48 * 60
JOUR_MONTH_LIMIT = 50 * 60


def _open_shifts(data):
    return list(data.get('vacantShifts') or data.get('openShifts') or [])


def _is_open_jour(row):
    if (row or {}).get('type') == 'jour':
        return True
    kod = str((row or {}).get('kod') or '').strip().lower()
    return kod == 'jo' or kod.startswith('jo')


def _span_row(row):
    try:
        return span(dict(
            date=row['date'], start=row['start'], end=row['end'],
            type=row.get('type') or 'jour',
        ))
    except (ValueError, KeyError, TypeError):
        return None


def locked_jour_rows(data):
    """Boundary- och låsta Jo-pass. Deduplicerade. Inte öppna Före-rader."""
    rows = []
    seen = set()
    for s in list(data.get('boundaryShifts') or []) + list(collect_locked_shifts(data)):
        if s.get('type') != 'jour':
            continue
        key = (s.get('id'), s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'))
        if key in seen:
            continue
        seen.add(key)
        try:
            a, b = span(s)
        except (ValueError, KeyError, TypeError):
            continue
        rows.append(dict(
            shift=s, a=a, b=b, employeeId=s.get('employeeId'), date=s.get('date'),
            minutes=int(b - a), locked=True,
        ))
    return rows


def required_jour_windows(data):
    wp, rules = data['workplace'], data['rules']
    start, end = planning_day_bounds(data)
    lo, hi = instant(start, '00:00'), instant(add_days(end, 1), '00:00')
    floor = int(rules.get('jourFloor') or 0)
    out = []
    for i, (a, b) in enumerate(jour_intervals(start, end, rules)):
        a, b = max(a, lo), min(b, hi)
        if a >= b or not floor:
            continue
        day = parts(a)[0]
        out.append(dict(
            id=f'jw-{i}-{day}-{parts(a)[1]}',
            date=day,
            start=parts(a)[1],
            end=parts(b)[1],
            a=a,
            b=b,
            required=floor,
        ))
    return out


def remaining_4w_on_date(locked_for_emp, day):
    starts = sorted({r['date'] for r in locked_for_emp if r.get('date')} | {day})
    leftover = []
    for start_day in starts:
        limit = add_days(start_day, 27)
        if not (start_day <= day <= limit):
            continue
        fixed = sum(r['minutes'] for r in locked_for_emp if start_day <= r['date'] <= limit)
        leftover.append(remaining_capacity(JOUR_4W_LIMIT, fixed))
    return min(leftover) if leftover else JOUR_4W_LIMIT


def remaining_month_on_date(locked_for_emp, day):
    ym = day[:7]
    fixed = sum(r['minutes'] for r in locked_for_emp if str(r.get('date') or '')[:7] == ym)
    return remaining_capacity(JOUR_MONTH_LIMIT, fixed)


def _eligible_jour_slots(data):
    from .precheck import enumerate_person_shift_slots
    templates = shift_templates_for_solve(data)
    enum = enumerate_person_shift_slots(data, templates)
    slots = []
    seen = set()
    for s in enum['slots']:
        if not s.get('eligible'):
            continue
        if (s.get('template') or {}).get('type') != 'jour':
            continue
        key = (s['employeeId'], s['day'], s['a'], s['b'])
        if key in seen:
            continue
        seen.add(key)
        minutes = int(s['b'] - s['a'])
        slots.append(dict(
            employeeId=s['employeeId'],
            date=s['day'],
            a=s['a'],
            b=s['b'],
            minutes=minutes,
            start=parts(s['a'])[1],
            end=parts(s['b'])[1],
        ))
    return slots


def window_candidate_report(window, employees, locked_by_emp, slots_by_emp, data, open_jour):
    from datetime import date as _date
    from .domain import weekend_allowed
    from .precheck import _absences, _absent
    initially = [e for e in employees if jour_eligible(e)]
    remaining_ids = []
    dropped = dict(jour4w=[], jourMonth=[], weekend=[], absence=[], restOrHard=[])
    for e in initially:
        eid = e['id']
        locked = locked_by_emp.get(eid) or []
        slots = [s for s in (slots_by_emp.get(eid) or []) if overlap(s['a'], s['b'], window['a'], window['b'])]
        if not slots:
            slot_days = list(days(add_days(window['date'], -1), window['date']))
            weekend_days = [d for d in slot_days if _date.fromisoformat(d).isoweekday() >= 6]
            if weekend_days and all(not weekend_allowed(e, d) for d in weekend_days):
                reason = 'weekend'
            elif _absent(_absences(data, eid), window['a'], window['b']):
                reason = 'absence'
            else:
                reason = 'restOrHard'
            dropped[reason].append(eid)
            continue
        cap_ok = False
        blocked_4w = blocked_month = False
        for s in slots:
            if remaining_4w_on_date(locked, s['date']) < s['minutes']:
                blocked_4w = True
                continue
            if remaining_month_on_date(locked, s['date']) < s['minutes']:
                blocked_month = True
                continue
            cap_ok = True
            break
        if cap_ok:
            remaining_ids.append(eid)
        elif blocked_4w:
            dropped['jour4w'].append(eid)
        elif blocked_month:
            dropped['jourMonth'].append(eid)
        else:
            dropped['restOrHard'].append(eid)
    locked_cover = sum(
        1 for rows in locked_by_emp.values() for r in rows
        if overlap(r['a'], r['b'], window['a'], window['b'])
    )
    need_new = max(0, window['required'] - locked_cover)
    isolated_ok = len(remaining_ids)
    if need_new <= 0:
        status = 'TÄCKBAR'
        shortage = False
    elif isolated_ok <= 0:
        status = 'SAKNAR REGISTRERAD RESURS'
        shortage = True
    else:
        status = 'TÄCKBAR'
        shortage = False
    matching_open = False
    open_hits = []
    for row in open_jour:
        sp = _span_row(row)
        if not sp:
            continue
        if overlap(sp[0], sp[1], window['a'], window['b']):
            matching_open = True
            open_hits.append(dict(date=row.get('date'), start=row.get('start'), end=row.get('end'), id=row.get('id')))
    return dict(
        id=window['id'],
        date=window['date'],
        start=window['start'],
        end=window['end'],
        requiredCount=window['required'],
        lockedCover=locked_cover,
        needNew=need_new,
        initiallyEligibleIds=[e['id'] for e in initially],
        droppedBy=dropped,
        remainingCandidateIds=remaining_ids,
        remainingCandidates=isolated_ok,
        status=status,
        safeShortage=shortage,
        matchingOpenJourShift=matching_open,
        openJourShifts=open_hits,
    )


def employee_remaining_capacity_report(employees, locked_by_emp, slots_by_emp, windows):
    period_dates = sorted({w['date'] for w in windows})
    month_keys = sorted({d[:7] for d in period_dates}) if period_dates else []
    out = []
    for e in employees:
        if not jour_eligible(e):
            continue
        eid = e['id']
        locked = locked_by_emp.get(eid) or []
        slots = slots_by_emp.get(eid) or []
        slot_dates = sorted({s['date'] for s in slots})
        rem_4w = [remaining_4w_on_date(locked, d) for d in slot_dates] or [JOUR_4W_LIMIT]
        rem_m = [remaining_month_on_date(locked, d) for d in slot_dates] or [JOUR_MONTH_LIMIT]
        binding = min(min(rem_4w), min(rem_m))
        allowed = []
        for s in slots:
            if remaining_4w_on_date(locked, s['date']) < s['minutes']:
                continue
            if remaining_month_on_date(locked, s['date']) < s['minutes']:
                continue
            allowed.append(s['date'])
        locked_4w = 0
        if slot_dates:
            # relevant 4-veckorsfönster: minuter i fönster som innehåller första slot-dagen
            d0 = slot_dates[0]
            starts = sorted({r['date'] for r in locked if r.get('date')} | {d0})
            best = None
            for start_day in starts:
                limit = add_days(start_day, 27)
                if start_day <= d0 <= limit:
                    mins = sum(r['minutes'] for r in locked if start_day <= r['date'] <= limit)
                    if best is None or mins > best:
                        best = mins
            locked_4w = int(best or 0)
        locked_month = {ym: sum(r['minutes'] for r in locked if str(r.get('date') or '')[:7] == ym) for ym in month_keys}
        out.append(dict(
            employeeId=eid,
            name=e.get('name') or e.get('code') or eid,
            lockedJourMinutes4w=locked_4w,
            lockedJourMinutesMonth=locked_month,
            remainingMinutes4w=min(rem_4w),
            remainingMinutesMonth=min(rem_m),
            bindingRemainingMinutes=binding,
            eligibleJourDates=sorted(set(allowed)),
        ))
    return out


def _diagnostic_external_min(windows, employees, locked_by_emp, slots, floor):
    """Liten CP-SAT: minimera extern jour-slack. Slack blir inte employee."""
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None

    if not windows:
        return dict(minimumExternalJourSlots=0, diagnosticExternalDates=[], status='OPTIMAL')

    model = cp_model.CpModel()
    x = []
    for i, s in enumerate(slots):
        x.append(model.new_bool_var(f'jdiag:{s["employeeId"]}:{s["date"]}:{i}'))

    by_emp_idx = {}
    for i, s in enumerate(slots):
        by_emp_idx.setdefault(s['employeeId'], []).append(i)
    for idxs in by_emp_idx.values():
        for a, i in enumerate(idxs):
            for j in idxs[a + 1:]:
                if overlap(slots[i]['a'], slots[i]['b'], slots[j]['a'], slots[j]['b']):
                    model.add(x[i] + x[j] <= 1)

    for e in employees:
        eid = e['id']
        locked = locked_by_emp.get(eid) or []
        idxs = by_emp_idx.get(eid) or []
        dates = sorted({slots[i]['date'] for i in idxs} | {r['date'] for r in locked if r.get('date')})
        for start_day in dates:
            limit = add_days(start_day, 27)
            win_idx = [i for i in idxs if start_day <= slots[i]['date'] <= limit]
            fixed_j = sum(r['minutes'] for r in locked if start_day <= r['date'] <= limit)
            if win_idx:
                model.add(sum(slots[i]['minutes'] * x[i] for i in win_idx) <= remaining_capacity(JOUR_4W_LIMIT, fixed_j))
        months = {}
        for i in idxs:
            months.setdefault(slots[i]['date'][:7], []).append(i)
        for r in locked:
            months.setdefault(str(r.get('date') or '')[:7], [])
        for ym, group in months.items():
            fixed_m = sum(r['minutes'] for r in locked if str(r.get('date') or '')[:7] == ym)
            if group:
                model.add(sum(slots[i]['minutes'] * x[i] for i in group) <= remaining_capacity(JOUR_MONTH_LIMIT, fixed_m))

        lim = hard_constraints(e).get('maxJourConsecutive')
        if lim and idxs:
            lim = int(lim)
            jour_days = sorted({slots[i]['date'] for i in idxs} | {r['date'] for r in locked if r.get('date')})
            if jour_days:
                start = add_days(min(jour_days), -7)
                end = add_days(max(jour_days), 7)
                day_list = list(days(start, end))
                counts = []
                locked_j = []
                for day in day_list:
                    covering = [x[i] for i in idxs if slots[i]['date'] == day]
                    if covering:
                        jc = model.new_int_var(0, len(covering), f'jdc:{eid}:{day}')
                        model.add(jc == sum(covering))
                    else:
                        jc = 0
                    counts.append(jc)
                    locked_j.append(1 if any(r['date'] == day for r in locked) else 0)
                for w in range(1, lim + 2):
                    for i in range(len(counts) - w + 1):
                        model.add(sum(counts[i:i + w]) <= max(lim, sum(locked_j[i:i + w])))

    ext = []
    for w in windows:
        locked_cover = sum(
            1 for rows in locked_by_emp.values() for r in rows
            if overlap(r['a'], r['b'], w['a'], w['b'])
        )
        covering = [x[i] for i, s in enumerate(slots) if overlap(s['a'], s['b'], w['a'], w['b'])]
        ev = model.new_int_var(0, w['required'], f'ext:{w["id"]}')
        ext.append(ev)
        model.add(sum(covering) + locked_cover + ev >= w['required'])

    model.minimize(sum(ext))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    if not ok:
        return dict(minimumExternalJourSlots=None, diagnosticExternalDates=[], status=str(solver.status_name(status)))
    total = int(round(solver.objective_value))
    dates = [windows[i]['date'] for i, ev in enumerate(ext) if solver.value(ev) >= 1]
    return dict(
        minimumExternalJourSlots=total,
        diagnosticExternalDates=dates,
        status='OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE',
        proven=status == cp_model.OPTIMAL,
    )


def _user_message(payload):
    req = payload.get('requiredJourSlots') or 0
    cov = payload.get('coverableWithRegisteredStaff')
    ext = payload.get('minimumExternalJourSlots')
    if not payload.get('jourCapacityShortfallDetected'):
        return ''
    parts_msg = ['Obligatorisk jour kan inte bemannas med registrerad personal.']
    if req:
        if cov is not None and ext is not None:
            parts_msg.append(
                f'{req} jourpass behöver bemannas under perioden. '
                f'Registrerad personal har, efter redan arbetad jour och gällande jourtak, kapacitet för högst {cov}. '
                f'Minst {ext} jourpass behöver ytterligare resurs.'
            )
        else:
            parts_msg.append(
                f'{req} jourpass behöver bemannas under perioden. '
                'Registrerad personal räcker inte efter redan arbetad jour och gällande jourtak.'
            )
    safe = [w['date'] for w in payload.get('uncoveredJourWindows') or [] if w.get('safeShortage')]
    unique = payload.get('externalDatesAreProvenUnique')
    if unique and safe:
        parts_msg.append('Berörda jourpass: ' + ', '.join(sorted(set(safe))) + '.')
    return ' '.join(parts_msg)


def analyze_jour_capacity(data):
    """Samma jourfakta som motorn: golv, behörighet, boundary, 48 h/4 v, 50 h/månad, helg, frånvaro."""
    rules = data['rules']
    floor = int(rules.get('jourFloor') or 0)
    employees = active_employees(data)
    windows = required_jour_windows(data) if floor else []
    locked = locked_jour_rows(data)
    locked_by_emp = {}
    for r in locked:
        locked_by_emp.setdefault(r['employeeId'], []).append(r)
    slots = _eligible_jour_slots(data) if floor else []
    slots_by_emp = {}
    for s in slots:
        slots_by_emp.setdefault(s['employeeId'], []).append(s)
    open_jour = [r for r in _open_shifts(data) if _is_open_jour(r)]

    window_rows = [
        window_candidate_report(w, employees, locked_by_emp, slots_by_emp, data, open_jour)
        for w in windows
    ]
    emp_rows = employee_remaining_capacity_report(employees, locked_by_emp, slots_by_emp, windows)
    required_new = sum(w['needNew'] for w in window_rows)
    safe_dates = [w['date'] for w in window_rows if w.get('safeShortage')]

    slack = None
    if floor and windows:
        slack = _diagnostic_external_min(windows, employees, locked_by_emp, slots, floor)

    min_ext = None
    proven = False
    diag_dates = []
    if slack and slack.get('minimumExternalJourSlots') is not None:
        min_ext = int(slack['minimumExternalJourSlots'])
        proven = bool(slack.get('proven'))
        diag_dates = list(slack.get('diagnosticExternalDates') or [])

    shortfall = False
    if min_ext is not None:
        shortfall = min_ext > 0
    elif safe_dates:
        shortfall = True

    coverable = None
    if min_ext is not None:
        coverable = max(0, required_new - min_ext)

    # Entydiga datum bara när isolationsbrist (noll kandidater) täcker hela minimumet.
    unique_dates = bool(
        proven and min_ext is not None and min_ext > 0 and len(set(safe_dates)) == min_ext
    )

    blocking = []
    if floor:
        blocking.append('jourFloor')
        blocking.append('JOUR_4W')
        blocking.append('JOUR_MONTH')
    if any((w.get('droppedBy') or {}).get('weekend') for w in window_rows):
        blocking.append('weekendMode')
    if any((w.get('droppedBy') or {}).get('absence') for w in window_rows):
        blocking.append('absence')

    payload = dict(
        requiredJourSlots=required_new,
        requiredJourWindows=len(windows),
        jourFloor=floor,
        coverableWithRegisteredStaff=coverable,
        minimumExternalJourSlots=min_ext,
        jourCapacityShortfallDetected=shortfall,
        diagnosticSlackStatus=(slack or {}).get('status'),
        diagnosticExternalDates=diag_dates,
        externalDatesAreProvenUnique=unique_dates,
        uncoveredJourWindows=window_rows,
        employeeRemainingCapacity=emp_rows,
        openJourShiftsInFore=[
            dict(
                date=r.get('date'), start=r.get('start'), end=r.get('end'),
                id=r.get('id'), matchingOpenJourShift=True,
            )
            for r in open_jour
        ],
        blockingRules=blocking,
        safeShortageDates=sorted(set(safe_dates)),
    )
    payload['userMessage'] = _user_message(payload)
    return payload


def jour_capacity_diagnoses(data, payload=None):
    payload = payload if payload is not None else analyze_jour_capacity(data)
    if not int((data.get('rules') or {}).get('jourFloor') or 0):
        return []
    if not payload.get('jourCapacityShortfallDetected'):
        return []
    return [dict(
        code='JOUR_CAPACITY_SHORTFALL',
        message=payload.get('userMessage') or 'Obligatorisk jour kan inte bemannas med registrerad personal.',
        severity='critical',
        kind='hard_jour',
        jour=payload,
        requiredJourSlots=payload.get('requiredJourSlots'),
        minimumExternalJourSlots=payload.get('minimumExternalJourSlots'),
        coverableWithRegisteredStaff=payload.get('coverableWithRegisteredStaff'),
    )]
