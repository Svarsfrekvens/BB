"""Syntetiska generateFromNeeds-benchmarks: skalbarhet (A) och constraint-stress (B)."""
from datetime import date, timedelta
from .domain import check_input, days
from .generate import generate_shift_templates, generated_template_stats, need_intervals, demand_blocks_for_day, planning_day_bounds
from .domain import span as sp


def _add(day, n):
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def _cover_f01(d):
    d['boundaryKnownFrom'] = _add(d['workplace']['start'], -27)
    d['boundaryKnownTo'] = _add(d['workplace']['end'], 27)
    return d


SCALE = {
    'liten': dict(employees=7, customers=5, period_days=28, seconds=20),
    'normal': dict(employees=10, customers=6, period_days=28, seconds=30),
    'storre': dict(employees=15, customers=10, period_days=28, seconds=60),
    'stress': dict(employees=25, customers=15, period_days=28, seconds=120),
}

CONSTRAINT = {
    'night': dict(kind='night', seconds=15),
    'skill': dict(kind='skill', seconds=15),
    'ssg': dict(kind='ssg', seconds=20),
    'absence': dict(kind='absence', seconds=15),
}


def _base(start, end, customers, employees, interventions, rules, absences=None, templates=None):
    d = dict(
        schemaVersion=1, inputRevision=1, planningMode='generateFromNeeds', existingSchedule=None,
        workplace=dict(name='Benchmark', start=start, end=end, timezone='Europe/Stockholm'),
        customers=customers, employees=employees, interventions=interventions,
        templates=templates or [],
        absences=absences or [], boundaryShifts=[], boundaryAcknowledged=True,
        economy=dict(hourlyCost=270),
        rules=rules,
        objectiveWeights=dict(continuitySek=50, spreadSekPerPermille=2.5),
        current=None,
    )
    return _cover_f01(d)


def build_scale(name):
    """A: 100 % kundtäckning är avsiktligt möjlig. Inom-pass-tid sänker kundnära KPI."""
    spec = SCALE[name]
    start, n_emp, n_cust = '2026-09-07', spec['employees'], spec['customers']
    end = _add(start, spec['period_days'] - 1)
    customers = [dict(id=f'c{i}', code=f'Kund {i}', name=f'Kund {i}', active=True) for i in range(1, n_cust + 1)]
    employees = []
    for i in range(1, n_emp + 1):
        employees.append(dict(
            id=f'e{i}', code=f'M{i:02d}', ssg=100, night=True, jour=True,
            hourlyCost=270 + i, status='active', skills=['Omsorg'],
            profiles=['D'],
            constraints=dict(hard=dict(weekendMode='all')),
        ))
    interventions, nid = [], 1

    def add_task(cid, clock, minutes, weekdays, name='Stöd'):
        nonlocal nid
        h, m = map(int, clock.split(':'))
        end_m = h * 60 + m + minutes
        latest = f'{end_m // 60 % 24:02d}:{end_m % 60:02d}'
        interventions.append(dict(
            id=f't{nid}', customerId=cid, name=name, type='fixed', start=clock, latestEnd=latest,
            minutes=minutes, doubleStaff=False, weekdays=weekdays, date=None, skills=['Omsorg'],
        ))
        nid += 1

    for c in customers:
        add_task(c['id'], '08:00', 180, [1, 2, 3, 4, 5], 'Morgonbesök')
    for c in customers[: min(2, n_cust)]:
        add_task(c['id'], '10:00', 120, [6, 7], 'Helg')
    templates = [dict(id='D', name='Dag', start='07:00', end='16:00', type='day', skills=['Omsorg'], breaks=[], dates=list(days(start, end)))]
    rules = dict(
        minRestHours=11, fullTimeWeeklyHours=40, maxWeeklyHours=48, maxShiftHours=12,
        maxConsecutiveDays=6, nightFloor=0, jourFloor=0, flexibilityStep=15,
        minWeeklyRestHours=36, minRestDaysInFourWeeks=9,
        preferredMinShiftMinutes=240, minGeneratedShiftMinutes=0,
        withinPassMinutesPerShift=30,
        jour=dict(start='23:00', end='06:30', weekdays=[1, 2, 3, 4, 5, 6, 7]),
    )
    d = _base(start, end, customers, employees, interventions, rules, templates=templates)
    check_input(d)
    d['_scenario'] = 'scale_' + name
    d['_category'] = 'scale'
    d['_seconds'] = spec['seconds']
    d['_activities'] = ['verksamhetsmöte/inom_pass-reserv', 'kontaktpersonstid', 'journal/GP', 'samordnartid', 'handledning']
    return d


def build_constraint(kind):
    """B: medvetet pressat. Full täckning är inte målet."""
    start, end = '2026-09-07', '2026-09-13'
    customers = [dict(id='c1', code='Kund 1', name='Kund 1', active=True),
                 dict(id='c2', code='Kund 2', name='Kund 2', active=True)]
    def emp(i, **kw):
        row = dict(id=f'e{i}', code=f'M{i:02d}', ssg=100, night=True, jour=True, profiles=['D'],
                   hourlyCost=270, status='active', skills=['Omsorg'],
                   constraints=dict(hard=dict(weekendMode='all')))
        row.update(kw)
        return row
    templates = [dict(id='D', name='Dag', start='07:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
                 dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])]
    task = dict(id='t1', customerId='c1', name='Stöd', type='fixed', start='09:00', latestEnd='10:00',
                minutes=60, doubleStaff=False, weekdays=[1, 2, 3, 4, 5], date=None, skills=['Omsorg'])
    absences, employees, interventions, rules_extra = [], [], [task], {}
    if kind == 'night':
        employees = [emp(1, night=False, profiles=['D']), emp(2, night=False, profiles=['D'])]
        rules_extra = dict(nightFloor=1)
        interventions.append(dict(id='tn', customerId='c1', name='Natt', type='fixed', start='22:00', latestEnd='06:00',
                                  minutes=480, doubleStaff=False, weekdays=[1, 2, 3, 4, 5], date=None, skills=['Omsorg']))
    elif kind == 'skill':
        employees = [emp(1, skills=['Omsorg']), emp(2, skills=['Omsorg'])]
        interventions[0]['skills'] = ['Läkemedel']
    elif kind == 'ssg':
        employees = [emp(1, ssg=10), emp(2, ssg=10)]
        interventions = [dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='08:00', latestEnd='16:00',
                              minutes=480, doubleStaff=False, weekdays=[1, 2, 3, 4, 5], date=None, skills=['Omsorg'])
                         for i in range(1, 6)]
    elif kind == 'absence':
        employees = [emp(1), emp(2)]
        absences = [dict(id='a1', employeeId='e1', start=start, end=end),
                    dict(id='a2', employeeId='e2', start=start, end=end)]
    else:
        raise ValueError(kind)
    for e in employees:
        if 'D' in (e.get('profiles') or []) and kind != 'night':
            e['profiles'] = ['D']
    rules = dict(
        minRestHours=11, fullTimeWeeklyHours=40, maxWeeklyHours=48, maxShiftHours=12,
        maxConsecutiveDays=5, jourFloor=0, flexibilityStep=15,
        minWeeklyRestHours=36, minRestDaysInFourWeeks=9,
        nightFloor=rules_extra.pop('nightFloor', 0),
        **rules_extra,
    )
    d = _base(start, end, customers, employees, interventions, rules, absences, templates)
    d['planningMode'] = 'generateFromNeeds'
    check_input(d)
    d['_scenario'] = 'constraint_' + kind
    d['_category'] = 'constraint'
    d['_seconds'] = CONSTRAINT[kind]['seconds']
    return d


def build_scenario(name):
    if name in SCALE or name in ('liten', 'normal', 'storre', 'stress'):
        key = name if name in SCALE else name
        return build_scale(key)
    if name.startswith('constraint_'):
        return build_constraint(name.split('_', 1)[1])
    if name in CONSTRAINT:
        return build_constraint(name)
    raise ValueError(name)


SCENARIOS = {**{k: dict(v, category='scale') for k, v in SCALE.items()},
             **{k: dict(v, category='constraint') for k, v in CONSTRAINT.items()}}


def generator_guardrails(data):
    tm = generate_shift_templates(data) if data.get('planningMode') == 'generateFromNeeds' else list(data.get('templates') or [])
    stats = generated_template_stats(tm) if data.get('planningMode') == 'generateFromNeeds' else dict(total=len(tm), perDayMax=len(tm), perDay={})
    minute_starts = [t['start'] for t in tm if str(t.get('start', '')).endswith(':01') or str(t.get('start', '')).endswith(':07')]
    short, empty_days = [], []
    if data.get('planningMode') == 'generateFromNeeds':
        p0, p1 = planning_day_bounds(data)
        intervals = need_intervals(data)
        night_floor = int(data['rules'].get('nightFloor') or 0)
        jour_floor = int(data['rules'].get('jourFloor') or 0)
        for day in days(p0, p1):
            blocks = demand_blocks_for_day(data, day, intervals)
            dated = [t for t in tm if day in (t.get('dates') or [])]
            if not blocks and not night_floor and not jour_floor and dated:
                empty_days.append(day)
            for t in dated:
                a, b = sp(dict(date=day, start=t['start'], end=t['end'], type=t['type'], breaks=[]))
                if t['type'] != 'jour' and (b - a) < 60:
                    short.append(t['id'])
    return dict(templates=tm, stats=stats, suspiciousMinuteStarts=minute_starts, tooShort=short, needlessDays=empty_days)


def run_benchmark(name, seconds=None):
    from .solver import solve
    data = build_scenario(name)
    guards = generator_guardrails(data)
    sec = seconds if seconds is not None else data['_seconds']
    result = solve(data, sec)
    perf = (result.get('diagnostics') or {}).get('performance') or result.get('modelScope') or {}
    return dict(
        name=data.get('_scenario', name), category=data.get('_category'), secondsBudget=sec,
        data=data, result=result, performance=perf,
        generator=dict(
            templates=len(guards['templates']), perDayMax=guards['stats'].get('perDayMax', 0),
            total=guards['stats'].get('total', 0), needlessDays=guards['needlessDays'],
            tooShort=guards['tooShort'], suspiciousMinuteStarts=guards['suspiciousMinuteStarts'],
        ),
    )
