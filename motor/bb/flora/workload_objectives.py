"""Search priority only: exact highest active net Monday week, all staff.

No weekly legal limit or business weighting is imposed. All time definitions and
hard rules are inherited from the case. Jo is separate from active Ar net.
"""
from collections import defaultdict
from ortools.sat.python import cp_model


def clip_duration(start, end, lo, hi):
    return max(0, min(end, hi) - max(start, lo))


def add_weekly_peak(case, model, variables, fixed_breaks):
    H = case['horizon']
    assert H == 4 * 10080
    step = case['config']['shift_step']
    break_length = case['config']['break_length']
    choices = model._reassignment_choices
    movable = {row_id for ch in choices for row_id in ch['unit']['segment_ids']}
    immutable = [r for r in case['fixed_segments'] if r['id'] not in movable]
    recipients = {ch['unit']['id']: dict(ch['options']) for ch in choices}
    terms = defaultdict(list)

    # Gross Ar follows the final recipient. Clip each immutable source segment,
    # rather than treating a cross-week Ar/Jo envelope as active work throughout.
    for p in case['staff']:
        person = p['id']
        for week in range(4):
            lo, hi = week * 10080, (week + 1) * 10080
            fixed_gross = sum(clip_duration(r['start'], r['end'], lo, hi)
                              for r in immutable
                              if r['person'] == person and r['code'] == 'Ar')
            terms[person, week].append(fixed_gross)
    for ch in choices:
        for week in range(4):
            lo, hi = week * 10080, (week + 1) * 10080
            gross = sum(clip_duration(r['start'], r['end'], lo, hi)
                        for r in ch['unit']['rows'] if r['code'] == 'Ar')
            if gross:
                for person, present in ch['options']:
                    terms[person, week].append(gross * present)

    # Exact break overlap at week edges: min(max(end,lo),hi) minus the
    # correspondingly clipped start. Thus 15+15 minute cross-week breaks do not
    # count as30 in either week. Fixed-unit break identities follow recipients.
    for bi, br in enumerate(fixed_breaks):
        start = br['start'] * step
        end = start + break_length
        dom = list(model.Proto().variables[br['start'].Index()].domain)
        earliest, latest = dom[0] * step, dom[-1] * step
        for week in range(4):
            lo, hi = week * 10080, (week + 1) * 10080
            if latest + break_length <= lo or earliest >= hi:
                continue
            if earliest >= lo and latest + break_length <= hi:
                overlap = break_length
            else:
                clamped = []
                for label, expr in [('start', start), ('end', end)]:
                    after_lo = model.NewIntVar(lo, max(hi, latest + break_length),
                                                f'break_{bi}_{week}_{label}_max')
                    model.AddMaxEquality(after_lo, [expr, lo])
                    inside = model.NewIntVar(lo, hi, f'break_{bi}_{week}_{label}_clip')
                    model.AddMinEquality(inside, [after_lo, hi])
                    clamped.append(inside)
                overlap = model.NewIntVar(0, break_length, f'break_{bi}_{week}_overlap')
                model.Add(overlap == clamped[1] - clamped[0])
            if br['unit_id'] is None:
                terms[br['person'], week].append(-overlap)
            else:
                for person, present in recipients[br['unit_id']].items():
                    if isinstance(overlap, int):
                        deduction = overlap * present
                    else:
                        deduction = model.NewIntVar(0, break_length,
                                                  f'break_{bi}_{week}_{person}_assigned')
                        model.AddMultiplicationEquality(deduction, [overlap, present])
                    terms[person, week].append(-deduction)

    # Candidate shifts are entirely within their known calendar day, hence one
    # Monday week; their exported net already deducts their optional break.
    for v in variables:
        day = v['c']['day']
        assert 0 <= day < 28 and day * 1440 <= v['c']['lo'] <= v['c']['hi'] <= (day + 1) * 1440
        terms[v['c']['person'], day // 7].append(v['net'])
    weekly = {}
    for key, exprs in terms.items():
        value = model.NewIntVar(0, 10080, f'weekly_Ar_net_{key[0]}_{key[1]}')
        model.Add(value == sum(exprs))
        weekly[key] = value
    peak = model.NewIntVar(0, 10080, 'highest_active_net_week_all_staff')
    model.AddMaxEquality(peak, list(weekly.values()))
    model._weekly_net = weekly
    model._weekly_peak = peak

    # The inherited validated candidate supplies an honest feasible workload
    # hint; no objective bound is invented from a business preference.
    prior = case.get('search_hint')
    if prior:
        hinted = []
        for (person, week), value in weekly.items():
            lo, hi = week * 10080, (week + 1) * 10080
            gross = sum(clip_duration(r['start'], r['end'], lo, hi)
                        for r in prior['segments']
                        if r['person'] == person and r['code'] == 'Ar')
            breaks = sum(clip_duration(b['start'], b['end'], lo, hi)
                         for b in prior['breaks'] if b['person'] == person)
            model.AddHint(value, gross - breaks)
            hinted.append(gross - breaks)
        model.AddHint(peak, max(hinted))
    return peak


def export_weekly_workload(model, solver):
    people = defaultdict(list)
    for (person, week), value in sorted(model._weekly_net.items()):
        people[person].append(solver.Value(value))
    return {
        'priority': 'COVERAGE_THEN_MIN_MAX_ACTIVE_NET_WEEK_THEN_TEMPORARY_NET',
        'legal_weekly_bound_or_business_weight_added': False,
        'definition': 'P2 Monday-Sunday Ar net after explicit breaks; all9staff; Jo separate',
        'highest_active_net_week_minutes': solver.Value(model._weekly_peak),
        'active_net_week_minutes_by_person': dict(people),
        'known_P3_overhang_is_not_zero_or_approved': True,
    }
