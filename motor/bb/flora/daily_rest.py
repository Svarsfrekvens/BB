"""Fixed-day 11-hour rest: shared arithmetic, no business defaults or approvals.

Minutes use the importer's verified local wall-clock horizon (DST is rejected
by check_case). Jour and whole-duty gaps never become qualifying daily rest.
Bransch E 6 b/c diagnostics are conditional, not proof of applicability.
"""
from collections import defaultdict
from datetime import datetime, timedelta

VERSION = 'fixed-daily-rest/1.0'
WORK_CODES = {'Ar', 'Jo', 'Kl', 'Öv'}


def boundary(case, person):
    params = case.get('daily_rest_parameters') or {}
    rows = [r for r in params.get('boundaries', [])
            if r.get('period_id') == params.get('period_id') and r.get('person_id') == person]
    if len(rows) != 1:
        return None
    value = rows[0].get('minute_of_day')
    return value if type(value) is int and 0 <= value < 1440 else None


def windows(case, person):
    offset = boundary(case, person)
    if offset is None:
        return []
    horizon = case['horizon']
    # Do not extend a P2 boundary decision backwards into P1 or beyond P2.
    return [(a, a + 1440, a >= 0 and a + 1440 <= horizon)
            for a in range(offset - 1440 if offset else 0, horizon, 1440)]


def merge(rows):
    out = []
    for a, b in sorted(rows):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def longest_free(lo, hi, occupied):
    cursor, best = lo, (lo, lo)
    for a, b in merge((max(lo, a), min(hi, b)) for a, b in occupied):
        if a - cursor > best[1] - best[0]:
            best = (cursor, a)
        cursor = max(cursor, b)
    if hi - cursor > best[1] - best[0]:
        best = (cursor, hi)
    return best


from .grouping import occasions, VERIFIED


def assess(case, raw):
    origin = datetime.fromisoformat(case['origin'])
    stamp = lambda minute: (origin + timedelta(minutes=minute)).isoformat(timespec='minutes')
    required = case['config'].get('min_daily_rest')
    duties = occasions(case, raw)
    records, missing, violations, exceptions = [], [], [], []
    supported = required == 660
    for p in case['staff']:
        person = p['id']
        if boundary(case, person) is None:
            missing.append(person)
            continue
        own = [d for d in duties if d['person'] == person]
        spans = [(d['start'], d['end']) for d in own]
        known_work = [(r['start'], r['end']) for d in own for r in d['rows']]
        for lo, hi, inside in windows(case, person):
            free = longest_free(lo, hi, spans)
            minutes = free[1] - free[0]
            possible = [d['id'] for d in own if d['combined_jour'] and d['end']-d['start'] > 720
                        and d['start'] < hi and d['end'] > lo]
            if not supported:
                status, reason = 'UNKNOWN', 'UNSUPPORTED_REST_POLICY'
            elif not inside or lo < case['config'].get('known_from', 0) or hi > case['config'].get('known_to', case['horizon']):
                status, reason = 'UNKNOWN', 'PERIOD_EDGE_OR_BOUNDARY_SCOPE'
            elif any(d['grouping_status'] != VERIFIED and d['start'] < hi and d['end'] > lo for d in own):
                status, reason = 'UNKNOWN', 'UNVERIFIED_GROUPING'
            elif minutes >= required:
                status, reason = 'PASS', 'CONTIGUOUS_REST_VERIFIED'
            elif possible:
                status, reason = 'UNKNOWN', 'COMBINED_JOUR_EXCEPTION_APPLICABILITY'
            else:
                known = longest_free(lo, hi, known_work)
                if known[1] - known[0] >= required:
                    status, reason = 'UNKNOWN', 'UNVERIFIED_WHOLE_DUTY_GAPS'
                else:
                    status, reason = 'FAIL', 'CONTIGUOUS_REST_TOO_SHORT'
                    violations.append(dict(rule='fixed_daily_rest_11h', person=person,
                                           start=stamp(lo), end=stamp(hi),
                                           longest_rest_minutes=minutes, required_minutes=required))
            records.append(dict(person_id=person, start=stamp(lo), end=stamp(hi),
                                status=status, reason=reason, required_minutes=required,
                                longest_rest_minutes=minutes,
                                longest_rest_start=stamp(free[0]), longest_rest_end=stamp(free[1]),
                                conditional_duty_ids=possible))
    # Mathematical conditions for combined work/jour are separate from the
    # employer's verified contract, MBL and individual exception applicability.
    for d in duties:
        span = d['end']-d['start']
        if not d['combined_jour'] or span <= 720 or d['start'] >= case['horizon'] or d['end']+span <= 0:
            continue
        night = []
        for r in d['rows']:
            if r['code'] != 'Jo':
                continue
            for day in range(r['start']//1440-1, r['end']//1440+1):
                night.append((max(r['start'], day*1440+1320), min(r['end'], (day+1)*1440+480)))
        night_minutes = max((b-a for a,b in merge(night)), default=0)
        until = d['end']+span
        others = [o for o in duties if o['person']==d['person'] and o is not d]
        interrupted = any(o['start'] < until and o['end'] > d['end'] for o in others)
        rest_status = 'FAIL' if interrupted else 'UNKNOWN' if until > min(case['config'].get('known_to',case['horizon']),case['horizon']) else 'PASS'
        exceptions.append(dict(person_id=d['person'], duty_id=d['id'], start=stamp(d['start']), end=stamp(d['end']),
                               span_minutes=span, contract_reference='Bransch E § 5 mom. 6 b/c (conditional)',
                               longest_night_jour_minutes=night_minutes,
                               grouping_status=d['grouping_status'],
                               night_jour_status='UNKNOWN' if d['grouping_status'] != VERIFIED else 'PASS' if night_minutes>=300 else 'FAIL',
                               max_24h_status='UNKNOWN' if d['grouping_status'] != VERIFIED else 'PASS' if span<=1440 else 'FAIL',
                               compensation_required_until=stamp(until), compensation_status='UNKNOWN' if d['grouping_status'] != VERIFIED else rest_status,
                               applicability='UNKNOWN',
                               reason='Numeriska villkor kontrollerade; ingen lokal undantagstillämplighet har antagits.'))
    status = 'FAIL' if violations else 'UNKNOWN' if missing or not supported or any(r['status']=='UNKNOWN' for r in records) else 'PASS'
    return dict(version=VERSION, status=status, required_minutes=required,
                missing_person_ids=missing, windows=records, conditional_jour_duties=exceptions,
                violations=violations, jour_counts_as_rest=False,
                other_business_decisions_inherited=False)


def constrain(case, model, person, events):
    """Enforce a contiguous 11h block in each fully known applicable day.

    A potentially selected combined-jour exception makes only its overlapping
    days conditional; its applicability remains UNKNOWN in the independent
    certificate. A different worker's jour never relaxes this person's day.
    """
    if case['config'].get('min_daily_rest') != 660:
        return
    for lo, hi, inside in windows(case, person):
        if not inside or lo < case['config'].get('known_from',0) or hi > case['config'].get('known_to',case['horizon']):
            continue
        applicable = []
        fixed_exception = False
        for e in events:
            if e.get('combined_jour') and isinstance(e['start'],int) and e['end']-e['start']>720 and e['start']<hi and e['end']>lo:
                if isinstance(e['present'],int):
                    fixed_exception = True
                else:
                    applicable.append(e['present'].Not())
        if fixed_exception:
            continue
        rest = model.NewIntVar(lo, hi-660, f'daily_rest_{person}_{lo}')
        for e in events:
            if isinstance(e['start'],int) and isinstance(e['end'],int) and (e['end']<=lo or e['start']>=hi):
                continue
            lit = applicable + ([] if isinstance(e['present'],int) else [e['present']])
            before = model.NewBoolVar('daily_rest_order')
            model.Add(e['end']<=rest).OnlyEnforceIf(lit+[before])
            model.Add(rest+660<=e['start']).OnlyEnforceIf(lit+[before.Not()])
