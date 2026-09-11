"""Strukturell feasibility före CP-SAT. Ändrar inte krav eller golv."""
from datetime import date
from .domain import (
    add_days, candidate_as_shift, days, hard_constraints, instant, is_night,
    jour_eligible, jour_intervals, night_eligible, night_intervals, occurrences,
    overlap, parts, shift_allowed, shifts_mergeable, skills_on_day, span,
    ssg_cap_minutes, weekend_allowed,
)
from .generate import (
    customer_need_interval_count, demand_blocks_for_day, need_intervals,
    occurrence_window, planning_day_bounds, planning_mode,
    shift_templates_for_solve, templates_for_employee,
)


def _absences(data, employee_id):
    return [
        (instant(a['start'], '00:00'), instant(add_days(a['end'], 1), '00:00'))
        for a in data['absences'] if a['employeeId'] == employee_id
    ]


def _absent(windows, a, b):
    return any(overlap(a, b, x, y) for x, y in windows)


def employee_available(e, day, a, b, data, for_night=False, for_jour=False):
    if e.get('status') != 'active':
        return False
    if not weekend_allowed(e, day):
        return False
    if _absent(_absences(data, e['id']), a, b):
        return False
    hard = hard_constraints(e)
    types = hard.get('allowedTypes')
    if for_night and types and 'night' not in types and 'jour' not in types:
        return False
    if for_jour and types and 'jour' not in types:
        return False
    if for_night and not night_eligible(e):
        return False
    if for_jour and not jour_eligible(e):
        return False
    weekdays = hard.get('weekdays')
    if weekdays and date.fromisoformat(day).isoweekday() not in weekdays:
        return False
    return True


def slot_eligible(e, template, day, a, b, data, rules, absences, boundary):
    """Pre-filter: uppenbart omöjliga person/pass-kombinationer."""
    if template.get('type') == 'jour' and not jour_eligible(e):
        return False
    if template.get('type') != 'jour' and is_night(a, b) and not night_eligible(e):
        return False
    if not shift_allowed(e, template, day, a, b, rules):
        return False
    if _absent(absences, a, b):
        return False
    if any(overlap(a, b, v['a'], v['b']) for v in boundary):
        return False
    rest_need = rules['minRestHours'] * 60
    cand = dict(shift=dict(type=template.get('type'), date=day, start=template['start'], end=template['end']), a=a, b=b)
    for v in boundary:
        if shifts_mergeable(candidate_as_shift(cand), candidate_as_shift(v)):
            continue
        if a - v['b'] >= rest_need or v['a'] - b >= rest_need:
            continue
        return False
    forbidden = set(hard_constraints(e).get('forbiddenCustomerIds') or [])
    covered = set(template.get('customerIds') or [])
    if covered and forbidden and covered <= forbidden:
        return False
    profile = template.get('dutyProfile')
    if profile in ('extendedCombinedWorkJour', 'EXTENDED_COMBINED_WORK_JOUR', 'longException'):
        if not (data.get('rules') or {}).get('shiftProfiles'):
            return False
    return True


def enumerate_person_shift_slots(data, templates=None):
    """Alla person×mall×dag i perioden, med eligible-flagga. Ingen solvervariabel."""
    wp, rules = data['workplace'], data['rules']
    lo, hi = instant(wp['start'], '00:00'), instant(add_days(wp['end'], 1), '00:00')
    mode = planning_mode(data)
    templates = templates if templates is not None else shift_templates_for_solve(data)
    start, end = planning_day_bounds(data)
    employees = [e for e in data['employees'] if e['status'] == 'active']
    boundary = []
    for s in data['boundaryShifts']:
        a, b = span(s)
        boundary.append(dict(shift=s, a=a, b=b, employeeId=s['employeeId']))
    before = after = 0
    slots = []
    for e in employees:
        absences = _absences(data, e['id'])
        own_b = [v for v in boundary if v['employeeId'] == e['id']]
        for day in days(add_days(start, -1), end):
            for t in templates_for_employee(e, templates, mode):
                dates = t.get('dates')
                if dates is not None and day not in dates:
                    continue
                if mode == 'generateFromNeeds' and dates is None:
                    if t.get('type') == 'night' and int(rules.get('nightFloor') or 0):
                        pass
                    elif t.get('type') == 'jour' and int(rules.get('jourFloor') or 0):
                        pass
                    else:
                        continue
                s = dict(id='slot', employeeId=e['id'], date=day, start=t['start'], end=t['end'], type=t['type'],
                         skills=t.get('skills') or [], breaks=t.get('breaks') or [])
                if t.get('dutyProfile'):
                    s['dutyProfile'] = t['dutyProfile']
                try:
                    a, b = span(s)
                except (ValueError, KeyError, TypeError):
                    continue
                if b <= lo or a >= hi or b - a > rules['maxShiftHours'] * 60:
                    continue
                before += 1
                ok = slot_eligible(e, t, day, a, b, data, rules, absences, own_b)
                if ok:
                    after += 1
                slots.append(dict(employeeId=e['id'], day=day, template=t, a=a, b=b, eligible=ok))
    return dict(before=before, after=after, slots=slots, templates=templates)


def _diag(code, message, severity='warning', **extra):
    row = dict(code=code, message=message, severity=severity)
    row.update(extra)
    return row


def feasibility_precheck(data):
    """Snabb strukturell kontroll. Sänker inte golv, behov, SSG eller villkor."""
    diagnoses = []
    employees = [e for e in data['employees'] if e['status'] == 'active']
    wp, rules = data['workplace'], data['rules']
    start, end = planning_day_bounds(data)
    occ = occurrences(data)
    night_floor = int(rules.get('nightFloor') or 0)
    jour_floor = int(rules.get('jourFloor') or 0)

    if not employees:
        diagnoses.append(_diag('NO_EMPLOYEES', 'Inga aktiva medarbetare finns för beräkningen.', 'critical'))
        return diagnoses

    period_days = list(days(wp['start'], wp['end']))
    need_min = sum(o['task']['minutes'] * o['count'] for o in occ)
    cap_min = sum(ssg_cap_minutes(e, period_days, rules, wp) for e in employees)
    if need_min > cap_min + 0.01:
        diagnoses.append(_diag(
            'SSG_CAPACITY_SHORT',
            f'SSG-kapaciteten är {cap_min / 60:g} timmar mot {need_min / 60:g} timmar kundbehov. SSG sänks inte.',
            needMinutes=need_min, capacityMinutes=cap_min,
        ))
    intervals = need_intervals(data)
    for day in days(start, end):
        for a, b, level in demand_blocks_for_day(data, day, intervals):
            available = [e for e in employees if employee_available(e, day, a, b, data)]
            if level > len(available):
                diagnoses.append(_diag(
                    'INSUFFICIENT_TOTAL_CAPACITY',
                    f'{day} kl. {parts(a)[1]}–{parts(b)[1]}: behov = {level}, maximalt tillgängliga = {len(available)}.',
                    date=day, need=level, available=len(available),
                ))
                break

    lo, hi = instant(start, '00:00'), instant(add_days(end, 1), '00:00')
    for a, b in night_intervals(start, end):
        a, b = max(a, lo), min(b, hi)
        if a >= b or not night_floor:
            continue
        day = parts(a)[0]
        available = [e for e in employees if employee_available(e, day, a, b, data, for_night=True)]
        if len(available) < night_floor:
            diagnoses.append(_diag(
                'NIGHT_STAFF_SHORT',
                f'{day}: nattbehov = {night_floor}, nattbehöriga tillgängliga = {len(available)}.',
                'critical', date=day, need=night_floor, available=len(available),
            ))

    for a, b in jour_intervals(start, end, rules):
        a, b = max(a, lo), min(b, hi)
        if a >= b or not jour_floor:
            continue
        day = parts(a)[0]
        available = [e for e in employees if employee_available(e, day, a, b, data, for_jour=True)]
        if len(available) < jour_floor:
            diagnoses.append(_diag(
                'JOUR_STAFF_SHORT',
                f'{day}: jourbehov = {jour_floor}, jourbehöriga tillgängliga = {len(available)}.',
                'critical', date=day, need=jour_floor, available=len(available),
            ))

    for o in occ:
        skills = set(o['task'].get('skills') or [])
        krav = o['task'].get('requiredEmployeeId')
        matching = []
        blocked_link = 0
        blocked_profile = 0
        for e in employees:
            if skills and not skills <= set(skills_on_day(e, o['date'])):
                continue
            if krav and e['id'] != krav:
                continue
            if o['task']['customerId'] in set(hard_constraints(e).get('forbiddenCustomerIds') or []):
                blocked_link += 1
                continue
            wa, wb = occurrence_window(o)[:2]
            if not employee_available(e, o['date'], wa, wb, data):
                blocked_profile += 1
                continue
            matching.append(e)
        if skills and not any(skills <= set(skills_on_day(e, o['date'])) for e in employees):
            diagnoses.append(_diag(
                'SKILL_SHORTAGE',
                f"{o['date']}: {o['task']['name']} kräver kompetens som ingen tillgänglig medarbetare har.",
                date=o['date'], occurrenceId=o['id'],
            ))
        elif krav and not any(e['id'] == krav for e in employees):
            diagnoses.append(_diag(
                'CUSTOMER_LINK_BLOCK',
                f"{o['date']}: insatsen kräver en medarbetare som inte finns bland aktiv personal.",
                date=o['date'], occurrenceId=o['id'],
            ))
        elif not matching and (blocked_link or krav):
            diagnoses.append(_diag(
                'CUSTOMER_LINK_BLOCK',
                f"{o['date']}: alla möjliga medarbetare är blockerade av kundkoppling för {o['task']['name']}.",
                date=o['date'], occurrenceId=o['id'],
            ))
        elif not matching and blocked_profile:
            diagnoses.append(_diag(
                'HARD_PROFILE_BLOCKS',
                f"{o['date']}: hårda individvillkor blockerar alla som annars kunde ta {o['task']['name']}.",
                date=o['date'], occurrenceId=o['id'],
            ))

    if night_floor:
        natt = [e for e in employees if night_eligible(e)]
        if natt and all(
            hard_constraints(e).get('allowedTypes')
            and 'night' not in (hard_constraints(e).get('allowedTypes') or [])
            for e in natt
        ):
            diagnoses.append(_diag(
                'HARD_PROFILE_BLOCKS',
                'Nattbehöriga medarbetare är blockerade av hårda passtypvillkor. nightFloor sänks inte.',
                'critical',
            ))

    seen = set()
    unique = []
    for d in diagnoses:
        key = (d['code'], d.get('date'), d.get('occurrenceId'), d['message'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique


def has_critical_precheck(diagnoses):
    return any(d.get('severity') == 'critical' for d in diagnoses)


def explain_with_precheck(solver_status, diagnoses, fallback):
    if solver_status != 'INFEASIBLE':
        return fallback
    critical = [d for d in diagnoses if d.get('severity') == 'critical']
    useful = critical or diagnoses
    if not useful:
        return fallback
    lines = ['Full bemanning kan inte skapas med nuvarande förutsättningar.']
    for d in useful[:8]:
        lines.append(d['message'])
    return ' '.join(lines)


def planning_diagnostics(data, extra=None):
    extra = extra or {}
    employees = [e for e in data['employees'] if e['status'] == 'active']
    start, end = planning_day_bounds(data)
    return dict(
        planningMode=planning_mode(data),
        employees=len(employees),
        planningDays=(date.fromisoformat(end) - date.fromisoformat(start)).days + 1,
        customerNeedIntervals=customer_need_interval_count(data),
        generatedShiftTemplates=extra.get('generatedShiftTemplates', 0),
        personShiftCombinationsBeforeFilter=extra.get('before', 0),
        personShiftCombinationsAfterFilter=extra.get('after', 0),
        solverVariables=extra.get('solverVariables', 0),
        solverConstraints=extra.get('solverConstraints', 0),
        preCheckTimeMs=extra.get('preCheckTimeMs', 0),
        solveTimeMs=extra.get('solveTimeMs', 0),
        solverStatus=extra.get('solverStatus', 'NOT_RUN'),
    )
