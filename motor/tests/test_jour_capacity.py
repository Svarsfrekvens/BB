"""JOUR-PRE: hård jourbrist som resursdiagnostik, inte regeländring."""
import unittest
from copy import deepcopy
from pathlib import Path

from test_jour import with_jour
from test_rules import cover_f01, fixture
from bb.jour_capacity import analyze_jour_capacity, remaining_4w_on_date, remaining_month_on_date
from bb.precheck import feasibility_precheck


def jo(eid, day, n):
    return dict(
        id=f'jo-{eid}-{day}-{n}',
        employeeId=eid,
        date=day,
        start='23:00',
        end='06:30',
        type='jour',
        skills=[],
        breaks=[],
    )


def four_jour_august():
    d, _ = fixture()
    d['workplace'].update(start='2026-08-03', end='2026-08-16')
    cover_f01(d)
    d = with_jour(d, extra=3)
    d['rules']['nightFloor'] = 0
    d['rules']['jourFloor'] = 1
    d['employees'][0]['name'] = 'Turmalin'
    d['employees'][1]['name'] = 'Jade'
    d['employees'][2]['name'] = 'Bärnsten'
    d['employees'][3]['name'] = 'Ametist'
    d['boundaryShifts'] = (
        [jo('e1', f'2026-08-{17 + i:02d}', i) for i in range(3)]
        + [jo('e2', f'2026-08-{17 + i:02d}', i) for i in range(2)]
        + [jo('e3', '2026-08-02', 0)]
        + [jo('e3', f'2026-08-{17 + i:02d}', i) for i in range(5)]
        + [jo('e4', f'2026-08-{17 + i:02d}', i) for i in range(2)]
    )
    return d


class JourCapacityPrecheck(unittest.TestCase):
    def test_jour_pre_a_seven_nights_enough_capacity_is_not_critical(self):
        d, _ = fixture()
        d = with_jour(d, extra=2)
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 1
        codes = {x['code'] for x in feasibility_precheck(d) if x.get('severity') == 'critical'}
        self.assertNotIn('JOUR_CAPACITY_SHORTFALL', codes)
        payload = analyze_jour_capacity(d)
        self.assertFalse(payload['jourCapacityShortfallDetected'])
        self.assertEqual(payload.get('minimumExternalJourSlots'), 0)

    def test_jour_pre_b_fourteen_nights_month_cap_eleven(self):
        d = four_jour_august()
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('JOUR_CAPACITY_SHORTFALL', codes)
        payload = analyze_jour_capacity(d)
        self.assertTrue(payload['jourCapacityShortfallDetected'])
        self.assertEqual(payload['requiredJourSlots'], 14)
        self.assertEqual(payload['minimumExternalJourSlots'], 3)
        self.assertEqual(payload['coverableWithRegisteredStaff'], 11)
        barn = next(r for r in payload['employeeRemainingCapacity'] if r['name'] == 'Bärnsten')
        self.assertLess(barn['bindingRemainingMinutes'], 7 * 60 + 30)
        self.assertEqual(barn['eligibleJourDates'], [])
        self.assertIn('JOUR_MONTH', payload['blockingRules'])
        self.assertIn('Minst 3', payload['userMessage'])
        self.assertNotIn('Berörda jourpass:', payload['userMessage'])

    def test_jour_pre_c_boundary_reduces_four_week_capacity(self):
        d, _ = fixture()
        d = with_jour(d)
        d['rules']['jourFloor'] = 1
        before = analyze_jour_capacity(d)
        row0 = next(r for r in before['employeeRemainingCapacity'] if r['employeeId'] == 'e1')
        d2 = deepcopy(d)
        d2['boundaryShifts'] = [jo('e1', '2026-09-01', 0)]
        after = analyze_jour_capacity(d2)
        row1 = next(r for r in after['employeeRemainingCapacity'] if r['employeeId'] == 'e1')
        self.assertGreater(row0['remainingMinutes4w'], row1['remainingMinutes4w'])
        self.assertEqual(row1['remainingMinutes4w'], row0['remainingMinutes4w'] - (7 * 60 + 30))

    def test_jour_pre_d_boundary_reduces_month_capacity(self):
        d, _ = fixture()
        d = with_jour(d)
        d['rules']['jourFloor'] = 1
        before = analyze_jour_capacity(d)
        row0 = next(r for r in before['employeeRemainingCapacity'] if r['employeeId'] == 'e1')
        d2 = deepcopy(d)
        d2['boundaryShifts'] = [jo('e1', '2026-09-01', 0)]
        after = analyze_jour_capacity(d2)
        row1 = next(r for r in after['employeeRemainingCapacity'] if r['employeeId'] == 'e1')
        self.assertGreater(row0['remainingMinutesMonth'], row1['remainingMinutesMonth'])
        self.assertEqual(row1['remainingMinutesMonth'], row0['remainingMinutesMonth'] - (7 * 60 + 30))

    def test_jour_pre_e_open_jour_is_fore_info_not_capacity(self):
        d = four_jour_august()
        base = analyze_jour_capacity(d)
        d['vacantShifts'] = [dict(
            id='open-jo',
            date='2026-08-08',
            start='23:00',
            end='06:30',
            type='jour',
            kod='Jo',
            rowLabel='Ingen placerad',
            source='medvind',
            origin='fore',
        )]
        d['openShifts'] = d['vacantShifts']
        with_open = analyze_jour_capacity(d)
        self.assertEqual(base['minimumExternalJourSlots'], with_open['minimumExternalJourSlots'])
        self.assertEqual(base['coverableWithRegisteredStaff'], with_open['coverableWithRegisteredStaff'])
        self.assertEqual(len(with_open['openJourShiftsInFore']), 1)
        match = [w for w in with_open['uncoveredJourWindows'] if w.get('matchingOpenJourShift')]
        self.assertTrue(match)
        self.assertGreaterEqual(with_open['minimumExternalJourSlots'], 3)

    def test_jour_pre_f_weekend_filters_candidates(self):
        d, _ = fixture()
        d = with_jour(d, extra=1)
        d['rules']['jourFloor'] = 1
        d['employees'][0]['constraints'] = dict(hard=dict(weekendMode='none'))
        d['employees'][1]['constraints'] = dict(hard=dict(weekendMode='all'))
        payload = analyze_jour_capacity(d)
        sat = [w for w in payload['uncoveredJourWindows'] if w['date'] == '2026-09-12']
        self.assertTrue(sat)
        for w in sat:
            self.assertNotIn('e1', w['remainingCandidateIds'])
            self.assertIn('e2', w['remainingCandidateIds'])
            self.assertIn('e1', w['droppedBy']['weekend'])
        mon = [w for w in payload['uncoveredJourWindows'] if w['date'] == '2026-09-07' and w['start'] >= '23:00']
        if not mon:
            mon = [w for w in payload['uncoveredJourWindows'] if w['date'] == '2026-09-07']
        self.assertTrue(any('e1' in w['remainingCandidateIds'] for w in mon))

    def test_jour_pre_g_customer_peak_is_not_jour_shortfall(self):
        d, _ = fixture()
        d['rules']['jourFloor'] = 0
        d['employees'] = [
            {**d['employees'][0], 'id': f'e{i}', 'code': f'M{i:02d}'}
            for i in range(1, 6)
        ]
        d['customers'] = [dict(id=f'c{i}', code=f'K{i}', active=True) for i in range(1, 8)]
        d['interventions'] = [
            dict(
                id=f't{i}', customerId=f'c{i}', name='Stöd', type='fixed',
                start='09:00', latestEnd='10:00', minutes=60, doubleStaff=False,
                weekdays=[1], date='2026-09-07', skills=['Omsorg'],
            )
            for i in range(1, 8)
        ]
        rows = feasibility_precheck(d)
        codes = {x['code'] for x in rows}
        self.assertIn('INSUFFICIENT_TOTAL_CAPACITY', codes)
        self.assertNotIn('JOUR_CAPACITY_SHORTFALL', codes)
        self.assertFalse(any(x.get('code') == 'JOUR_CAPACITY_SHORTFALL' for x in rows))

    def test_jour_pre_h_diagnostic_slack_minimum(self):
        d, _ = fixture()
        d['workplace'].update(start='2026-09-07', end='2026-09-09')
        cover_f01(d)
        d = with_jour(d)
        d['rules']['jourFloor'] = 1
        d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[1, 2, 3])
        d['boundaryShifts'] = [jo('e1', f'2026-09-{i:02d}', i) for i in range(1, 6)]
        payload = analyze_jour_capacity(d)
        self.assertEqual(payload['requiredJourSlots'], 3)
        self.assertEqual(payload['minimumExternalJourSlots'], 2)
        self.assertEqual(payload['coverableWithRegisteredStaff'], 1)
        locked = [dict(date=f'2026-09-{i:02d}', minutes=7 * 60 + 30) for i in range(1, 6)]
        self.assertEqual(remaining_month_on_date(locked, '2026-09-07'), 12 * 60 + 30)
        self.assertEqual(remaining_4w_on_date(locked, '2026-09-07'), 10 * 60 + 30)


def _period_days(d):
    from bb.domain import days
    return list(days(d['workplace']['start'], d['workplace']['end']))


def _temporary(d, dates, jour=True, eid='t1', code='T1'):
    e = dict(d['employees'][0])
    e.update(
        id=eid,
        code=code,
        name='Extern jourresurs',
        resourceType='temporary',
        ssg=0,
        night=False,
        jour=jour,
        hourlyCost=350,
        skills=[],
        profiles=['J'] if jour else ['D'],
        constraints=dict(hard=dict(
            dates=list(dates),
            allowedTypes=['jour'] if jour else ['day'],
            weekendMode='all',
        )),
    )
    e.pop('workTimeModelId', None)
    e.pop('ssgWindows', None)
    e.pop('workTimeWindows', None)
    return e


class ExplicitTemporaryJourResource(unittest.TestCase):
    def test_open_shifts_still_not_a_resource(self):
        d = four_jour_august()
        before = len([e for e in d['employees'] if e.get('resourceType') != 'temporary'])
        d['vacantShifts'] = [
            dict(id='open-ar', date='2026-08-08', start='07:00', end='16:00', type='day', kod='Ar', source='medvind', origin='fore'),
            dict(id='open-jo', date='2026-08-08', start='23:00', end='06:30', type='jour', kod='Jo', source='medvind', origin='fore'),
        ]
        d['openShifts'] = d['vacantShifts']
        from bb.domain import active_employees, check_input
        check_input(d)
        self.assertEqual(len(active_employees(d)), before)
        self.assertFalse(any(e.get('resourceType') == 'temporary' for e in d['employees']))

    def test_jour_without_eligibility_does_not_count(self):
        d = four_jour_august()
        base = analyze_jour_capacity(d)['minimumExternalJourSlots']
        d['employees'].append(_temporary(d, _period_days(d), jour=False))
        after = analyze_jour_capacity(d)
        self.assertEqual(after['minimumExternalJourSlots'], base)

    def test_jour_outside_registered_dates_does_not_count(self):
        d = four_jour_august()
        base = analyze_jour_capacity(d)['minimumExternalJourSlots']
        d['employees'].append(_temporary(d, ['2026-07-01', '2026-07-02', '2026-07-03'], jour=True))
        after = analyze_jour_capacity(d)
        self.assertEqual(after['minimumExternalJourSlots'], base)

    def test_three_correct_extra_nights_can_clear_shortfall(self):
        d = four_jour_august()
        self.assertEqual(analyze_jour_capacity(d)['minimumExternalJourSlots'], 3)
        d['employees'].append(_temporary(d, _period_days(d), jour=True))
        from bb.domain import check_input
        check_input(d)
        after = analyze_jour_capacity(d)
        self.assertEqual(after['minimumExternalJourSlots'], 0)
        self.assertGreaterEqual(after['coverableWithRegisteredStaff'], 14)
        self.assertFalse(after['jourCapacityShortfallDetected'])

    def test_removing_temporary_restores_shortfall(self):
        d = four_jour_august()
        d['employees'].append(_temporary(d, _period_days(d), jour=True))
        self.assertEqual(analyze_jour_capacity(d)['minimumExternalJourSlots'], 0)
        d['employees'] = [e for e in d['employees'] if e.get('resourceType') != 'temporary']
        restored = analyze_jour_capacity(d)
        self.assertEqual(restored['minimumExternalJourSlots'], 3)

    def test_temporary_is_solver_staff_temp_pool_is_not(self):
        from bb.domain import active_employees
        d = four_jour_august()
        d['employees'].append(_temporary(d, _period_days(d)))
        pool = dict(d['employees'][0], id='pool1', code='P1', resourceType='temp_pool')
        d['employees'].append(pool)
        ids = {e['id'] for e in active_employees(d)}
        self.assertIn('t1', ids)
        self.assertNotIn('pool1', ids)

    def test_jour_only_temporary_is_not_daytime_capacity(self):
        from test_rules import fixture
        from bb.domain import instant
        from bb.precheck import employee_available, feasibility_precheck
        d, _ = fixture()
        d['customers'] = [dict(id=f'c{i}', code=f'K{i}', active=True) for i in range(1, 3)]
        d['interventions'] = [
            dict(
                id=f't{i}', customerId=f'c{i}', name='Stöd', type='fixed',
                start='09:00', latestEnd='10:00', minutes=60, doubleStaff=False,
                weekdays=[1], date='2026-09-07', skills=['Omsorg'],
            )
            for i in range(1, 3)
        ]
        d['employees'].append(_temporary(d, _period_days(d), jour=True))
        rows = feasibility_precheck(d)
        codes = {x['code'] for x in rows}
        self.assertIn('INSUFFICIENT_TOTAL_CAPACITY', codes)
        row = next(x for x in rows if x['code'] == 'INSUFFICIENT_TOTAL_CAPACITY')
        self.assertEqual(row.get('available'), 1)
        o_day = '2026-09-07'
        a, b = instant(o_day, '09:00'), instant(o_day, '10:00')
        temp = next(e for e in d['employees'] if e.get('resourceType') == 'temporary')
        self.assertFalse(employee_available(temp, o_day, a, b, d))
        self.assertTrue(employee_available(temp, o_day, a, b, d, for_jour=True))


class Galaxen14dJourDiagnostics(unittest.TestCase):
    def test_galaxen_14d_still_infeasible_with_explanation(self):
        path = Path(__file__).resolve().parents[2] / 'qa' / 'scripts' / '_galaxen_14d.json'
        if not path.exists():
            self.skipTest('Galaxen 14d-dump saknas')
        import json
        from bb.domain import active_employees
        from bb.solver import solve
        blob = json.loads(path.read_text(encoding='utf-8'))
        data = blob['data']
        emps = active_employees(data)
        self.assertEqual(len(emps), 5)
        self.assertFalse(any(str(e.get('id') or '').startswith('x') for e in emps))
        r = solve(data, 8)
        self.assertEqual(r['schedule']['solverStatus'], 'INFEASIBLE')
        jour = (r.get('resourceDiagnostics') or r['schedule'].get('resourceDiagnostics') or {}).get('jour') or {}
        self.assertTrue(jour.get('jourCapacityShortfallDetected'))
        self.assertEqual(jour.get('requiredJourSlots'), 14)
        self.assertEqual(jour.get('minimumExternalJourSlots'), 3)
        self.assertIn('JOUR_CAPACITY_SHORTFALL', {x['code'] for x in r['schedule'].get('preCheck') or []})
        self.assertIn('Obligatorisk jour', r['schedule'].get('explanation') or '')
        self.assertGreaterEqual(len(jour.get('openJourShiftsInFore') or []), 1)
        codes = {x.get('rule') for x in (r.get('summary') or {}).get('hardViolations') or []}
        self.assertIn('JOUR_CAPACITY_SHORTFALL', codes)
        self.assertNotIn('INSUFFICIENT_TOTAL_CAPACITY', codes)
