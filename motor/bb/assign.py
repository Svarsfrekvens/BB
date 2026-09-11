"""Deterministisk pruning av insats×person×pass före CP-SAT.

Skapar inte variabler för kombinationer som hårda regler redan utesluter.
Dominans: bara identiska täckningsfönster för samma person och insats.
"""
from .domain import hard_constraints, is_night, skills_on_day
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


def support_options_for_occurrence(o, employees, by_emp, data, reserve):
    """Returnerar täckande (kandidat, fönster) per person efter hård filter + säker dominans."""
    before = after = 0
    per_emp = []
    duration = o['task']['minutes']
    for e in employees:
        raw = []
        for c in overlapping_candidates(by_emp.get(e['id']) or [], o['earliest'], o['latest'], duration):
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
