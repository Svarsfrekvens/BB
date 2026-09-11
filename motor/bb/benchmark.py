"""Syntetiska men realistiska generateFromNeeds-benchmarks. Ingen Medvind-import."""
from datetime import date, timedelta
from .domain import check_input, days
from .generate import generate_shift_templates, generated_template_stats


def _add(day, n):
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def _cover_f01(d):
    d['boundaryKnownFrom'] = _add(d['workplace']['start'], -27)
    d['boundaryKnownTo'] = _add(d['workplace']['end'], 27)
    return d


SCENARIOS = {
    'liten': dict(employees=7, customers=5, period_days=28, night_floor=0, jour_floor=0, seconds=15, absence=False),
    'normal': dict(employees=10, customers=6, period_days=28, night_floor=1, jour_floor=0, seconds=25, absence=False),
    'storre': dict(employees=15, customers=10, period_days=28, night_floor=1, jour_floor=1, seconds=40, absence=False),
    'stress': dict(employees=25, customers=15, period_days=28, night_floor=1, jour_floor=1, seconds=70, absence=True),
}


def build_scenario(name):
    spec = SCENARIOS[name]
    start = '2026-09-07'
    end = _add(start, spec['period_days'] - 1)
    n_emp, n_cust = spec['employees'], spec['customers']
    customers = [dict(id=f'c{i}', code=f'Kund {i}', name=f'Kund {i}', active=True) for i in range(1, n_cust + 1)]
    employees = []
    for i in range(1, n_emp + 1):
        ssg = [100, 75, 50, 100, 80][(i - 1) % 5]
        night = i <= max(2, n_emp // 3)
        jour = spec['jour_floor'] and i <= max(2, n_emp // 5)
        skills = ['Omsorg']
        if i % 4 == 0:
            skills.append('Läkemedel')
        hard = dict(weekendMode='all')
        soft = {}
        if i == 2:
            hard['allowedTypes'] = ['day']
            night = False
        if i == 3:
            hard['earliestStart'] = '07:00'
            hard['latestEnd'] = '21:00'
        if i == 4:
            hard['weekendMode'] = 'every_other'
            hard['weekendOffset'] = 0
        if i == 5:
            soft['preferredTypes'] = ['day']
            soft['preferredCustomerIds'] = ['c1']
        if i == 6 and n_cust >= 2:
            hard['forbiddenCustomerIds'] = [f'c{n_cust}']
        employees.append(dict(
            id=f'e{i}', code=f'M{i:02d}', ssg=ssg, night=night, jour=bool(jour),
            profiles=[], hourlyCost=270 + i, status='active', skills=skills,
            constraints=dict(hard=hard, **({'soft': soft} if soft else {})),
        ))
    interventions = []
    weekday = [1, 2, 3, 4, 5]
    nid = 1

    def add_task(cid, start_clock, minutes, weekdays, skills, name='Stöd', double=False):
        nonlocal nid
        h, m = map(int, start_clock.split(':'))
        end_m = h * 60 + m + minutes
        latest = f'{end_m // 60 % 24:02d}:{end_m % 60:02d}'
        interventions.append(dict(
            id=f't{nid}', customerId=cid, name=name, type='fixed', start=start_clock, latestEnd=latest,
            minutes=minutes, doubleStaff=double, weekdays=weekdays, date=None, skills=skills,
        ))
        nid += 1

    for i, c in enumerate(customers, start=1):
        skills = ['Omsorg']
        if i % 5 == 0:
            skills = ['Omsorg', 'Läkemedel']
        add_task(c['id'], '07:30', 90, weekday, skills, 'Morgon')
        add_task(c['id'], '11:00', 120, weekday, skills, 'Dag')
        if i % 2 == 0:
            add_task(c['id'], '16:00', 150, weekday, skills, 'Kväll')
        if i <= min(3, n_cust):
            add_task(c['id'], '10:00', 120, [6, 7], skills, 'Helg')
    if spec['night_floor']:
        add_task('c1', '22:00', 480, [1, 2, 3, 4, 5, 6, 7], ['Omsorg'], 'Natt')

    absences = []
    if spec['absence']:
        absences.append(dict(id='a1', employeeId='e3', start='2026-09-21', end='2026-09-23'))

    d = dict(
        schemaVersion=1, inputRevision=1, planningMode='generateFromNeeds', existingSchedule=None,
        workplace=dict(name='Benchmark', start=start, end=end, timezone='Europe/Stockholm'),
        customers=customers, employees=employees, interventions=interventions, templates=[],
        absences=absences, boundaryShifts=[], boundaryAcknowledged=True,
        economy=dict(hourlyCost=270),
        rules=dict(
            minRestHours=11, fullTimeWeeklyHours=40, maxWeeklyHours=48, maxShiftHours=12,
            maxConsecutiveDays=5, nightFloor=spec['night_floor'], jourFloor=spec['jour_floor'],
            flexibilityStep=30 if n_emp >= 15 else 15,
            minWeeklyRestHours=36, minRestDaysInFourWeeks=9,
            preferredMinShiftMinutes=240, minGeneratedShiftMinutes=0,
            jour=dict(start='23:00', end='06:30', weekdays=[1, 2, 3, 4, 5, 6, 7]),
        ),
        objectiveWeights=dict(continuitySek=50, spreadSekPerPermille=2.5),
        current=None,
    )
    _cover_f01(d)
    check_input(d)
    d['_scenario'] = name
    d['_seconds'] = spec['seconds']
    return d


def generator_guardrails(data):
    tm = generate_shift_templates(data)
    stats = generated_template_stats(tm)
    clocks = [(t['start'], t['end'], t['type']) for t in tm]
    minute_starts = [t['start'] for t in tm if t['start'].endswith(':01') or t['start'].endswith(':07')]
    short = []
    preferred = int(data['rules'].get('preferredMinShiftMinutes') or 240)
    from .domain import span as sp
    empty_days = []
    start, end = data['workplace']['start'], data['workplace']['end']
    from .generate import need_intervals, demand_blocks_for_day, planning_day_bounds
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
    return dict(
        templates=tm, stats=stats, uniqueClocks=len(set(clocks)),
        suspiciousMinuteStarts=minute_starts, tooShort=short, needlessDays=empty_days,
        preferredMinShiftMinutes=preferred,
    )


def run_benchmark(name, seconds=None):
    from .solver import solve
    data = build_scenario(name)
    guards = generator_guardrails(data)
    sec = seconds if seconds is not None else data['_seconds']
    result = solve(data, sec)
    perf = (result.get('diagnostics') or {}).get('performance') or result.get('modelScope') or {}
    return dict(
        name=name, secondsBudget=sec, data=data, result=result, performance=perf,
        generator=dict(
            templates=len(guards['templates']),
            perDayMax=guards['stats']['perDayMax'],
            total=guards['stats']['total'],
            needlessDays=guards['needlessDays'],
            tooShort=guards['tooShort'],
            suspiciousMinuteStarts=guards['suspiciousMinuteStarts'],
        ),
    )
