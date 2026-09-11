import importlib.util
import unittest
from copy import deepcopy
from test_rules import fixture, cover_f01
from bb.domain import check_input, ssg_cap_minutes, days, instant, add_days, span, longest_rest_minutes
from bb.validate import validate


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
def _solve():
    from bb.solver import solve
    return solve


class DatumstyrdSsgValidator(unittest.TestCase):
    def two_weeks(self):
        d, s = fixture()
        d['workplace']['end'] = '2026-09-20'
        cover_f01(d)
        d['employees'][0]['ssgWindows'] = [
            dict(start='2026-09-07', end='2026-09-13', ssg=100),
            dict(start='2026-09-14', end='2026-09-20', ssg=75),
        ]
        d['rules']['fullTimeWeeklyHours'] = 40
        d['rules']['maxWeeklyHours'] = 48
        d['rules']['maxConsecutiveDays'] = 7
        d['interventions'] = []
        s['assignments'] = []
        return d, s

    def test_split_ssg_cap_is_70_hours(self):
        d, _ = self.two_weeks()
        cap = ssg_cap_minutes(d['employees'][0], list(days('2026-09-07', '2026-09-20')), d['rules'])
        self.assertAlmostEqual(cap / 60, 70, places=5)

    def test_hours_over_75_percent_week_fail_contract(self):
        d, s = self.two_weeks()
        s['shifts'] = []
        for i, day in enumerate(days('2026-09-07', '2026-09-20')):
            s['shifts'].append(dict(id=f's{i}', employeeId='e1', date=day, start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]))
        self.assertIn('CONTRACT', {e['rule'] for e in validate(d, s)['errors']})

    def test_hours_within_split_cap_pass(self):
        d, s = self.two_weeks()
        s['shifts'] = []
        for i, day in enumerate(['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10',
                                 '2026-09-14', '2026-09-15', '2026-09-16']):
            s['shifts'].append(dict(id=f's{i}', employeeId='e1', date=day, start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]))
        self.assertNotIn('CONTRACT', {e['rule'] for e in validate(d, s)['errors']})
        self.assertTrue(validate(d, s)['valid'] or 'CONTRACT' not in {e['rule'] for e in validate(d, s)['errors']})


class Veckovila(unittest.TestCase):
    def codes(self, d, s):
        return {e['rule'] for e in validate(d, s)['errors']}

    def test_weekend_off_has_weekly_rest(self):
        d, s = fixture()
        d['rules']['minWeeklyRestHours'] = 36
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = [
            dict(id=f's{i}', employeeId='e1', date=day, start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11'])
        ]
        self.assertNotIn('WEEK_REST', self.codes(d, s))

    def test_seven_workdays_fail_weekly_rest(self):
        d, s = fixture()
        d['rules']['minWeeklyRestHours'] = 36
        d['rules']['maxConsecutiveDays'] = 7
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = [
            dict(id=f's{i}', employeeId='e1', date=day, start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11', '2026-09-12', '2026-09-13'])
        ]
        self.assertIn('WEEK_REST', self.codes(d, s))

    def test_boundary_shift_blocks_weekly_rest(self):
        d, s = fixture()
        d['rules']['minWeeklyRestHours'] = 36
        d['rules']['maxConsecutiveDays'] = 7
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = [
            dict(id=f's{i}', employeeId='e1', date=day, start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11', '2026-09-12'])
        ]
        d['boundaryShifts'] = [dict(id='after', employeeId='e1', date='2026-09-13', start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[])]
        self.assertIn('WEEK_REST', self.codes(d, s))

    def test_solver_respects_weekly_rest(self):
        solve = _solve()
        d, _ = fixture()
        d['workplace']['end'] = '2026-09-13'
        d['rules']['minWeeklyRestHours'] = 36
        d['rules']['maxConsecutiveDays'] = 7
        d['rules']['fullTimeWeeklyHours'] = 56
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['nightFloor'] = 0
        d['interventions'] = [
            dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='09:00', latestEnd='10:00',
                 minutes=60, doubleStaff=False, weekdays=[date], date=day, skills=['Omsorg'])
            for i, (date, day) in enumerate([(1, '2026-09-07'), (2, '2026-09-08'), (3, '2026-09-09'),
                                             (4, '2026-09-10'), (5, '2026-09-11'), (6, '2026-09-12'), (7, '2026-09-13')])
        ]
        r = solve(d, 12)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(r['validation']['valid'])
        self.assertNotIn('WEEK_REST', {e['rule'] for e in r['validation']['errors']})
        self.assertLess(len(r['schedule']['shifts']), 7)

    def sunday_monday_split(self):
        """Lör–sön plus må–fre: varje ISO-vecka har 36 h, rullande sju dagar har det inte."""
        d, s = fixture()
        d['workplace']['end'] = '2026-09-20'
        cover_f01(d)
        d['rules']['minWeeklyRestHours'] = 36
        d['rules']['maxConsecutiveDays'] = 7
        d['rules']['maxWeeklyHours'] = 48
        d['rules']['fullTimeWeeklyHours'] = 40
        d['interventions'] = []
        s['assignments'] = []
        days_on = ['2026-09-12', '2026-09-13', '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18']
        s['shifts'] = [
            dict(id=f's{i}', employeeId='e1', date=day, start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(days_on)
        ]
        return d, s

    def test_iso_week_would_accept_sunday_monday_split(self):
        d, s = self.sunday_monday_split()
        duties = [span(sh) for sh in s['shifts']]
        for week in ['2026-09-07', '2026-09-14']:
            wa, wb = instant(week, '00:00'), instant(add_days(week, 7), '00:00')
            self.assertGreaterEqual(longest_rest_minutes(duties, wa, wb), 36 * 60)

    def test_rolling_seven_days_rejects_sunday_monday_split(self):
        d, s = self.sunday_monday_split()
        self.assertIn('WEEK_REST', self.codes(d, s))

    def test_solver_does_not_emit_sunday_monday_split(self):
        solve = _solve()
        d, _ = self.sunday_monday_split()
        d['rules']['nightFloor'] = 0
        d['rules']['fullTimeWeeklyHours'] = 56
        d['rules']['maxWeeklyHours'] = 60
        d['interventions'] = [
            dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='09:00', latestEnd='10:00',
                 minutes=60, doubleStaff=False, weekdays=[(i % 7) + 1], date=day, skills=['Omsorg'])
            for i, day in enumerate(['2026-09-12', '2026-09-13', '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18'])
        ]
        r = solve(d, 12)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(r['validation']['valid'])
        self.assertNotIn('WEEK_REST', {e['rule'] for e in r['validation']['errors']})
        worked = {sh['date'] for sh in r['schedule']['shifts']}
        self.assertNotEqual(worked, {'2026-09-12', '2026-09-13', '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17', '2026-09-18'})


class IndividuellaVillkor(unittest.TestCase):
    def codes(self, d, s):
        return {e['rule'] for e in validate(d, s)['errors']}

    def test_hard_day_only_rejects_evening(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(allowedTypes=['day']))
        s['shifts'][0]['type'] = 'evening'
        s['shifts'][0]['start'] = '13:30'
        s['shifts'][0]['end'] = '21:30'
        self.assertIn('PROFILE', self.codes(d, s))

    def test_soft_evening_preference_does_not_forbid_day(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(soft=dict(preferredTypes=['evening']))
        self.assertNotIn('PROFILE', self.codes(d, s))
        self.assertTrue(validate(d, s)['valid'])

    def test_forbidden_customer(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(forbiddenCustomerIds=['c1']))
        self.assertIn('CUSTOMER', self.codes(d, s))

    def test_dated_skill_outside_window(self):
        d, s = fixture()
        d['employees'][0]['skills'] = ['Omsorg', 'delegering']
        d['employees'][0]['skillWindows'] = [dict(skill='delegering', start='2026-09-01', end='2026-09-06')]
        d['interventions'][0]['skills'] = ['delegering']
        self.assertIn('TASK_SKILL', self.codes(d, s))

    def test_min_max_shift_length(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(maxShiftHours=6, minShiftHours=7))
        self.assertIn('SHIFT_LENGTH', self.codes(d, s))

    def test_weekend_every_other_rejects_off_week(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(weekendMode='every_other', weekendOffset=0))
        s['shifts'][0]['date'] = '2026-09-12'
        s['assignments'] = []
        d['interventions'] = []
        self.assertIn('WEEKEND', self.codes(d, s))

    def test_earliest_start(self):
        d, s = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(earliestStart='07:00'))
        self.assertIn('WINDOW_EMP', self.codes(d, s))

    def test_solver_does_not_use_forbidden_customer(self):
        solve = _solve()
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['employees'][0]['constraints'] = dict(hard=dict(forbiddenCustomerIds=['c1']))
        r = solve(d, 8)
        self.assertEqual(r['schedule']['assignments'], [])
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']), 1)
        self.assertTrue(r['validation']['valid'])


class Helgmönster(unittest.TestCase):
    def test_precheck_when_nobody_may_work_saturday(self):
        solve = _solve()
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['interventions'][0].update(date='2026-09-12', weekdays=[6])
        d['employees'][0]['constraints'] = dict(hard=dict(weekendMode='none'))
        d['employees'].append({**deepcopy(d['employees'][0]), 'id': 'e2', 'code': 'M02',
                               'constraints': dict(hard=dict(weekendMode='every_third', weekendOffset=1))})
        r = solve(d, 8)
        notes = r['schedule'].get('feasibilityNotes') or []
        self.assertTrue(any('helgbehov' in n or 'helgbehörig' in n for n in notes))
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']), 1)

    def test_mixed_weekend_patterns_can_cover(self):
        solve = _solve()
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['interventions'][0].update(date='2026-09-12', weekdays=[6])
        d['employees'][0]['constraints'] = dict(hard=dict(weekendMode='every_other', weekendOffset=0))
        d['employees'].append({**deepcopy(d['employees'][0]), 'id': 'e2', 'code': 'M02',
                               'constraints': dict(hard=dict(weekendMode='every_other', weekendOffset=1))})
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(r['validation']['valid'])
        self.assertEqual(r['schedule']['uncovered'], [])
        self.assertEqual({a['employeeId'] for a in r['schedule']['assignments']}, {'e2'})


class InomPass(unittest.TestCase):
    def test_reserve_prevents_invisible_overtime(self):
        solve = _solve()
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['rules']['withinPassMinutesPerShift'] = 30
        d['templates'][0].update(start='09:00', end='17:00')
        d['employees'][0]['profiles'] = ['D']
        d['interventions'][0].update(start='09:00', latestEnd='17:00', minutes=480)
        r = solve(d, 8)
        self.assertEqual(r['schedule']['assignments'], [])
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']), 1)

    def test_validator_flags_assignment_plus_reserve_over_paid(self):
        d, s = fixture()
        from bb.domain import instant
        d['rules']['withinPassMinutesPerShift'] = 30
        s['shifts'][0].update(start='09:00', end='17:00')
        d['interventions'][0].update(start='09:00', latestEnd='17:00', minutes=480)
        s['assignments'][0]['start'] = instant('2026-09-07', '09:00')
        s['assignments'][0]['end'] = instant('2026-09-07', '17:00')
        self.assertIn('WITHIN_PASS', {e['rule'] for e in validate(d, s)['errors']})

    def test_old_payload_without_new_fields_still_checks(self):
        d, _ = fixture()
        check_input(d)
