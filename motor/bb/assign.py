"""Deterministisk pruning av insats×person×pass före CP-SAT.

Skapar inte variabler för kombinationer som hårda regler redan utesluter.
Dominans: bara identiska täckningsfönster för samma person och insats.
"""
from .domain import add_days, hard_constraints, is_night, skills_on_day
from .generate import occurrence_window
from .precheck import employee_available


def shrink_work(intervals, take):
    if take <= 0:
        return list(intervals)
    left, out = take, []
    for a, b in intervals:
        if left <= 0:
            out.append((a, b))
            continue
        cut = min(left, b - a)
        if a + cut < b:
            out.append((a + cut, b))
        left -= cut
    return out


def occurrence_employee_ok(e, o, data):
    """Kompetens, kundlänk, frånvaro, helg, natt, status. Samma hårda logik som pre-check."""
    if e.get('status') != 'active':
        return False
    skills = set(o['task'].get('skills') or [])
    if skills and not skills <= set(skills_on_day(e, o['date'])):
        return False
    krav = o['task'].get('requiredEmployeeId')
    if krav and e['id'] != krav:
        return False
    hard = hard_constraints(e)
    if o['task']['customerId'] in set(hard.get('forbiddenCustomerIds') or []):
        return False
    wa, wb = occurrence_window(o)[:2]
    nightish = is_night(wa, wb)
    types = hard.get('allowedTypes')
    if types:
        if nightish and not ({'night', 'jour'} & set(types)):
            return False
        if not nightish and set(types) <= {'night', 'jour'}:
            return False
    return employee_available(e, o['date'], wa, wb, data, for_night=nightish)


def covering_windows(candidate, o, reserve):
    duration = o['task']['minutes']
    windows = []
    for a, b in shrink_work(candidate.get('work') or [], reserve):
        if b - a < duration or b < o['earliest'] + duration or a > o['latest']:
            continue
        windows.append((a, b))
    return windows


def prune_duplicate_cover_windows(pairs):
    """Dubbletter av samma pass och samma fönster. Olika pass prunas inte.

    Samma täckningsfönster från två olika passmallar kan skilja i kostnad, vila,
    SSG och kvalitet. Sådan dominans är inte bevisbart säker.
    """
    seen = {}
    out = []
    for cand, a, b in pairs:
        key = (cand['shift']['id'], a, b)
        if key in seen:
            continue
        seen[key] = True
        out.append((cand, a, b))
    return out


def index_candidates_by_employee(candidates):
    by = {}
    for c in candidates:
        by.setdefault(c['shift']['employeeId'], []).append(c)
    for rows in by.values():
        rows.sort(key=lambda c: c['a'])
    return by


def overlapping_candidates(rows, earliest, latest, duration):
    lo, hi = earliest, latest + duration
    out = []
    for c in rows:
        if c['b'] <= lo:
            continue
        if c['a'] >= hi:
            break
        out.append(c)
    return out


def support_options_for_occurrence(o, employees, by_emp, data, reserve, by_emp_day=None):
    """Returnerar täckande (kandidat, fönster) per person efter hård filter + säker dominans."""
    before = after = 0
    per_emp = []
    duration = o['task']['minutes']
    day = o['date']
    prev, nxt = add_days(day, -1), add_days(day, 1)
    for e in employees:
        if by_emp_day is not None:
            rows = []
            for d in (prev, day, nxt):
                if d:
                    rows.extend(by_emp_day.get((e['id'], d)) or [])
            rows.sort(key=lambda c: c['a'])
        else:
            rows = by_emp.get(e['id']) or []
        raw = []
        for c in overlapping_candidates(rows, o['earliest'], o['latest'], duration):
            for a, b in covering_windows(c, o, reserve):
                raw.append((c, a, b))
        before += len(raw)
        if not occurrence_employee_ok(e, o, data):
            continue
        pruned = prune_duplicate_cover_windows(raw)
        after += len(pruned)
        if pruned:
            per_emp.append((e, pruned))
    return dict(before=before, after=after, per_emp=per_emp)


def index_candidates_by_employee_day(candidates):
    by = {}
    for c in candidates:
        by.setdefault((c['shift']['employeeId'], c['shift']['date']), []).append(c)
    for rows in by.values():
        rows.sort(key=lambda c: c['a'])
    return by


def _keep_generated_template(template):
    if template.get('type') in ('night', 'jour'):
        return True
    if template.get('dutyProfile'):
        return True
    if template.get('source') in ('night', 'jour'):
        return True
    return False


def template_covers_occurrence(template, day, o, reserve):
    from .domain import paid, span
    sample = dict(
        id='probe', employeeId='probe', date=day, start=template['start'], end=template['end'],
        type=template.get('type') or 'day', skills=template.get('skills') or [],
        breaks=template.get('breaks') or [],
    )
    if template.get('dutyProfile'):
        sample['dutyProfile'] = template['dutyProfile']
    try:
        span(sample)
    except (ValueError, KeyError, TypeError):
        return False
    duration = o['task']['minutes']
    for a, b in shrink_work(paid(sample), reserve):
        if b - a < duration or b < o['earliest'] + duration or a > o['latest']:
            continue
        return True
    return False


def prune_unusable_generated_templates(data, templates):
    """Ta bort genererade dag-/kvällsmallar som inte kan täcka något behov den dagen.

    Natt, jour och composite lämnas. Stödmallar (ej generated) lämnas.
    Korta mallar som faktiskt kan bära en insats lämnas — de kan vara billigare.
    """
    from .domain import occurrences
    reserve = int((data.get('rules') or {}).get('withinPassMinutesPerShift') or 0)
    occ_by_day = {}
    for o in occurrences(data):
        occ_by_day.setdefault(o['date'], []).append(o)
    generated_before = sum(1 for t in templates if t.get('generated'))
    out = []
    for t in templates:
        if not t.get('generated') or _keep_generated_template(t):
            out.append(t)
            continue
        dates = list(t.get('dates') or [])
        if not dates:
            out.append(t)
            continue
        keep = [d for d in dates if any(template_covers_occurrence(t, d, o, reserve) for o in occ_by_day.get(d) or [])]
        if not keep:
            continue
        if keep == dates:
            out.append(t)
        else:
            row = dict(t)
            row['dates'] = keep
            out.append(row)
    generated_after = sum(1 for t in out if t.get('generated'))
    pct = round(100.0 * (generated_before - generated_after) / generated_before, 2) if generated_before else 0.0
    return out, dict(
        generatedShiftTemplatesBeforePruning=generated_before,
        generatedShiftTemplatesAfterPruning=generated_after,
        generatedShiftPrunedPercent=pct,
    )
