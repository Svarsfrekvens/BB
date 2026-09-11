"""Passkandidater från kundbehov. Separat från personfördelning.

Primär källa är insatser (befintlig kundmodell). Standardmallar är stöd.
Ingen minut-för-minut-generering: bara brytpunkter där något ändras.
"""
from .domain import (
    add_days, days, instant, is_night, jour_intervals, night_intervals,
    occurrences, overlap, parts, span,
)

MAX_GENERATED_TEMPLATES = 48
MAX_MERGES_PER_DAY = 24


def planning_mode(data):
    mode = data.get('planningMode') or 'optimizeExisting'
    if mode not in ('optimizeExisting', 'generateFromNeeds'):
        raise ValueError('Ogiltigt planeringsläge.')
    return mode


def planning_day_bounds(data):
    wp = data['workplace']
    rng = data.get('planningRange') or {}
    start = rng.get('start') or wp['start']
    end = rng.get('end') or wp['end']
    if start < wp['start']:
        start = wp['start']
    if end > wp['end']:
        end = wp['end']
    if start > end:
        raise ValueError('Ogiltigt planeringsintervall.')
    return start, end


def occurrence_window(o):
    duration = o['task']['minutes']
    if o['task']['type'] == 'fixed':
        a = o['earliest']
        return a, a + duration, o['count']
    return o['earliest'], o['latest'] + duration, o['count']


def need_intervals(data):
    """Normaliserade behovsintervall ur insatser. Ingen parallell kundmodell."""
    rows = []
    for o in occurrences(data):
        a, b, count = occurrence_window(o)
        if a >= b:
            continue
        rows.append(dict(
            occurrenceId=o['id'],
            date=o['date'],
            start=a,
            end=b,
            count=count,
            customerId=o['task']['customerId'],
            skills=list(o['task'].get('skills') or []),
            requiredEmployeeId=o['task'].get('requiredEmployeeId'),
            source='customer',
        ))
    return rows


def _clock(t):
    return parts(t)[1]


def _type_for_span(a, b, forced=None):
    if forced:
        return forced
    if is_night(a, b):
        return 'night'
    h = int(_clock(a)[:2])
    if h < 11:
        return 'day'
    if h < 17:
        return 'evening'
    return 'night'


def extra_breakpoints(data, day):
    rules = data['rules']
    marks = []
    start, end = planning_day_bounds(data)
    for a, b in night_intervals(day, day):
        if parts(a)[0] == day or parts(b)[0] == day:
            marks.extend([a, b])
    for a, b in jour_intervals(day, day, rules):
        if parts(a)[0] == day or parts(b)[0] == day:
            marks.extend([a, b])
    wp_lo, wp_hi = instant(start, '00:00'), instant(add_days(end, 1), '00:00')
    for t in data.get('templates') or []:
        sample = dict(t, date=day, breaks=t.get('breaks') or [])
        try:
            a, b = span(sample)
        except (ValueError, KeyError, TypeError):
            continue
        if overlap(a, b, wp_lo, wp_hi):
            marks.extend([a, b])
    return marks


def demand_curve(intervals, lo, hi):
    events = []
    for row in intervals:
        a, b, c = max(row['start'], lo), min(row['end'], hi), row['count']
        if a < b and c:
            events.append((a, c))
            events.append((b, -c))
    events.sort()
    curve = []
    level = 0
    prev = lo
    for t, delta in events:
        if t != prev:
            if prev < hi:
                curve.append((prev, min(t, hi), level))
            prev = t
        level += delta
        if t >= hi:
            break
    if prev < hi:
        curve.append((prev, hi, level))
    return [(a, b, c) for a, b, c in curve if a < b]


def demand_blocks_for_day(data, day, intervals):
    lo, hi = instant(day, '00:00'), instant(add_days(day, 1), '00:00')
    next_hi = instant(add_days(day, 2), '00:00')
    # Behov som korsar midnatt hör till start-dagen och nästa morgon.
    relevant = [r for r in intervals if overlap(r['start'], r['end'], lo, next_hi)]
    marks = {lo, hi}
    for r in relevant:
        marks.add(max(r['start'], lo))
        marks.add(min(r['end'], next_hi))
    for t in extra_breakpoints(data, day):
        if lo <= t <= next_hi:
            marks.add(t)
    points = sorted(t for t in marks if lo <= t <= next_hi)
    curve = demand_curve(relevant, lo, next_hi)
    blocks = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        level = max((c for x, y, c in curve if overlap(a, b, x, y)), default=0)
        if level > 0:
            blocks.append((a, b, level))
    return blocks


def _customers_in(intervals, a, b):
    ids = []
    for row in intervals:
        if overlap(a, b, row['start'], row['end']) and row['customerId'] not in ids:
            ids.append(row['customerId'])
    return ids


def generate_shift_templates(data):
    """Begränsat antal rimliga passmallar från behovets brytpunkter."""
    rules = data['rules']
    max_span = float(rules.get('maxShiftHours') or 12) * 60
    min_gen = int(rules.get('minGeneratedShiftMinutes') or 0)
    intervals = need_intervals(data)
    start, end = planning_day_bounds(data)
    seen = {}
    order = []

    def add(start_clock, end_clock, typ, customers, source, day):
        key = (start_clock, end_clock, typ)
        if key in seen:
            prev = seen[key]
            for cid in customers:
                if cid not in prev['customerIds']:
                    prev['customerIds'].append(cid)
            if day not in prev['dates']:
                prev['dates'].append(day)
            return
        if len(order) >= MAX_GENERATED_TEMPLATES:
            return
        tid = f'gen{len(order) + 1}'
        row = dict(
            id=tid,
            name=f'{typ} {start_clock}-{end_clock}',
            start=start_clock,
            end=end_clock,
            type=typ,
            skills=[],
            breaks=[],
            generated=True,
            customerIds=list(customers),
            source=source,
            dates=[day],
        )
        seen[key] = row
        order.append(row)

    for day in days(start, end):
        blocks = demand_blocks_for_day(data, day, intervals)
        merges = 0
        for i in range(len(blocks)):
            for j in range(i, len(blocks)):
                a, b = blocks[i][0], blocks[j][1]
                if any(blocks[k][1] < blocks[k + 1][0] for k in range(i, j)):
                    continue
                span_m = b - a
                if span_m <= 0 or span_m > max_span + 1e-9:
                    continue
                atomic = i == j
                if min_gen and span_m + 1e-9 < min_gen and not atomic:
                    continue
                if merges >= MAX_MERGES_PER_DAY:
                    break
                add(_clock(a), _clock(b), _type_for_span(a, b), _customers_in(intervals, a, b), 'need', parts(a)[0])
                merges += 1
            if merges >= MAX_MERGES_PER_DAY:
                break

        night_need = any(is_night(a, b) for a, b, _ in blocks)
        if night_need or int(rules.get('nightFloor') or 0):
            for a, b in night_intervals(day, day):
                if parts(a)[0] != day:
                    continue
                add(_clock(a), _clock(b), 'night', _customers_in(intervals, a, b), 'night', day)
        if int(rules.get('jourFloor') or 0):
            for a, b in jour_intervals(day, day, rules):
                if parts(a)[0] != day:
                    continue
                add(_clock(a), _clock(b), 'jour', [], 'jour', day)

    return order


def merge_templates(support, generated):
    out = []
    seen = set()
    for t in list(generated) + list(support or []):
        key = (t['start'], t['end'], t['type'])
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def shift_templates_for_solve(data):
    support = list(data.get('templates') or [])
    if planning_mode(data) != 'generateFromNeeds':
        return support
    return merge_templates(support, generate_shift_templates(data))


def templates_for_employee(employee, templates, mode):
    by_id = {t['id']: t for t in templates}
    if mode != 'generateFromNeeds':
        return [by_id[p] for p in employee.get('profiles') or [] if p in by_id]
    generated = [t for t in templates if t.get('generated')]
    named = [by_id[p] for p in (employee.get('profiles') or []) if p in by_id]
    return merge_templates(named, generated)


def customer_need_interval_count(data):
    start, end = planning_day_bounds(data)
    intervals = need_intervals(data)
    n = 0
    for day in days(start, end):
        n += len(demand_blocks_for_day(data, day, intervals))
    return n
