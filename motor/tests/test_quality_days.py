import importlib.util
import unittest
from datetime import date, timedelta
from test_rules import fixture
from copy import deepcopy
from bb.domain import (
    consecutive_six_seven_counts,
    has_consecutive_off,
)
from bb.validate import validate


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
def _solve():
    from bb.solver import solve
    return solve


def _days(start, n):
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


def _shift(eid, sid, day):
    return dict(id=sid, employeeId=eid, date=day, start='08:00', end='12:00', type='day', skills=['Omsorg'], breaks=[])


class KvalitetDagarOchFridagar(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 56
        d['rules']['fullTimeWeeklyHours'] = 56
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0, preferredMissSek=0)
        self.d, self.s = d, s

    def codes(self, kind='errors'):
        res = validate(self.d, self.s)
        return {e['rule'] for e in res[kind]}

    def test_counts_5_6_7(self):
        self.assertEqual(consecutive_six_seven_counts([True] * 5 + [False, False]), (0, 0))
        self.assertEqual(consecutive_six_seven_counts([True] * 6 + [False]), (1, 0))
        n6, n7 = consecutive_six_seven_counts([True] * 7)
        self.assertEqual((n6, n7), (2, 1))
        self.assertGreater(n6 + n7, 1)

    def test_five_days_no_hard_or_soft_consecutive(self):
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 5))]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('CONSECUTIVE', self.codes())
        self.assertNotIn('CONSECUTIVE_SOFT', self.codes('warnings'))

    def test_six_days_soft_warning_not_error(self):
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 6))]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('CONSECUTIVE', self.codes())
        self.assertIn('CONSECUTIVE_SOFT', self.codes('warnings'))

    def test_seven_days_stronger_soft_count(self):
        six = [True] * 6 + [False]
        seven = [True] * 7
        self.assertGreater(sum(consecutive_six_seven_counts(seven)), sum(consecutive_six_seven_counts(six)))
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 7))]
        res = validate(self.d, self.s)
        self.assertIn('CONSECUTIVE_SOFT', {w['rule'] for w in res['warnings']})
        self.assertIn('7', [w['message'] for w in res['warnings'] if w['rule'] == 'CONSECUTIVE_SOFT'][0])
        self.assertNotIn('CONSECUTIVE', {e['rule'] for e in res['errors']})

    def test_hard_individual_consecutive_still_errors(self):
        self.d['employees'][0]['constraints'] = dict(hard=dict(maxConsecutiveDays=5))
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 6))]
        self.assertFalse(validate(self.d, self.s)['valid'])
        self.assertIn('CONSECUTIVE', self.codes())

    def test_nine_rest_days_valid(self):
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5][:-1]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('REST_DAYS', self.codes())
        self.assertNotIn('REST_DAYS_SOFT', self.codes('warnings'))

    def test_eight_rest_days_hard_error(self):
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertFalse(res['valid'])
        self.assertIn('REST_DAYS', self.codes())
        self.assertNotIn('REST_DAYS_SOFT', self.codes('warnings'))

    def test_ten_rest_days_valid_no_soft_bonus_code(self):
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5][:-2]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('REST_DAYS', self.codes())
        self.assertNotIn('REST_DAYS_SOFT', self.codes('warnings'))

    def test_nine_rest_days_can_be_disabled(self):
        self.d['workplace']['end'] = '2026-10-04'
        self.d['rules']['minRestDaysInFourWeeks'] = 0
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('REST_DAYS', self.codes())

    def test_rest_days_count_boundary_shifts(self):
        self.d['workplace']['start'] = '2026-09-28'
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5]
        period = set(_days('2026-09-28', 7))
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(d for d in work if d in period)]
        self.d['boundaryShifts'] = [
            dict(id=f'b{i}', employeeId='e1', date=day, start='08:00', end='12:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(d for d in work if d < '2026-09-28')
        ]
        res = validate(self.d, self.s)
        self.assertFalse(res['valid'])
        self.assertIn('REST_DAYS', self.codes())

    def test_pair_off_days_favoured(self):
        self.assertTrue(has_consecutive_off([True] * 5 + [False, False], 2))
        self.assertFalse(has_consecutive_off([True, False, True, False, True, False, True], 2))
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(['2026-09-07', '2026-09-09', '2026-09-11', '2026-09-13'])]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertIn('PAIR_OFF_SOFT', self.codes('warnings'))
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 5))]
        self.assertNotIn('PAIR_OFF_SOFT', self.codes('warnings'))

    def test_soft_min_off_warns_hard_min_off_fails(self):
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(_days('2026-09-07', 6))]
        self.d['employees'][0]['constraints'] = dict(soft=dict(minConsecutiveOffDays=2))
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertIn('MIN_OFF_SOFT', self.codes('warnings'))
        self.d['employees'][0]['constraints'] = dict(hard=dict(minConsecutiveOffDays=2))
        res = validate(self.d, self.s)
        self.assertFalse(res['valid'])
        self.assertIn('MIN_OFF', self.codes())

    def test_old_payload_still_validates(self):
        d, s = fixture()
        self.assertTrue(validate(d, s)['valid'])


class SolverKvalitetDagar(unittest.TestCase):
    def demand_days(self, n):
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 56
        d['rules']['fullTimeWeeklyHours'] = 56
        d['rules']['maxShiftHours'] = 12
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0, preferredMissSek=0)
        d['templates'] = [dict(id='D', name='Kort', start='08:00', end='12:00', type='day', skills=['Omsorg'], breaks=[])]
        days = _days('2026-09-07', n)
        d['workplace']['end'] = days[-1]
        d['interventions'] = [
            dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='09:00',
                 latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date=day, skills=['Omsorg'])
            for i, day in enumerate(days)
        ]
        return d

    def test_six_days_chosen_when_needed_for_coverage(self):
        d = self.demand_days(6)
        r = _solve()(d, 12)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        self.assertIn('CONSECUTIVE_SOFT', {w['rule'] for w in r['validation']['warnings']})

    def test_lexico_coverage_unchanged_on_classic_fixture(self):
        d, _ = fixture()
        d['rules']['nightFloor'] = 0
        d['objectiveWeights'] = dict(continuitySek=0, spreadSekPerPermille=0)
        r = _solve()(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])

    def weekday_demand(self, drop=0, extra_employee=None):
        d = self.demand_days(7)
        days = _days('2026-09-07', 28)
        d['workplace']['end'] = days[-1]
        work = [day for day in days if date.fromisoformat(day).weekday() < 5]
        if drop:
            work = work[:-drop]
        d['interventions'] = [
            dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='09:00',
                 latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date=day, skills=['Omsorg'])
            for i, day in enumerate(work)
        ]
        d['objectiveWeights'] = dict(
            continuitySek=0, spreadSekPerPermille=0, preferredMissSek=0,
            consecutive6Sek=0, consecutive7Sek=0, missingPairOffSek=0, missingRestDaySek=0,
        )
        if extra_employee:
            d['employees'].append(extra_employee)
        return d, work

    def test_solver_eight_rest_cannot_cover_all_weekdays(self):
        d, work = self.weekday_demand(0)
        self.assertEqual(len(work), 20)
        r = _solve()(d, 20)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertGreater(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        self.assertNotIn('REST_DAYS', {e['rule'] for e in r['validation']['errors']})

    def test_solver_nine_rest_days_feasible(self):
        d, work = self.weekday_demand(1)
        self.assertEqual(len(work), 19)
        r = _solve()(d, 20)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        worked = {s['date'] for s in r['schedule']['shifts'] if s['employeeId'] == 'e1'}
        self.assertEqual(len(worked), 19)

    def test_solver_ten_rest_days_feasible(self):
        d, work = self.weekday_demand(2)
        self.assertEqual(len(work), 18)
        r = _solve()(d, 20)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        worked = {s['date'] for s in r['schedule']['shifts'] if s['employeeId'] == 'e1'}
        self.assertEqual(len(worked), 18)

    def test_ten_rest_has_no_quality_bonus_over_nine(self):
        nine = _solve()(self.weekday_demand(1)[0], 20)
        ten = _solve()(self.weekday_demand(2)[0], 20)
        self.assertEqual(nine['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertEqual(ten['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertGreaterEqual(
            ten['schedule']['lexicographic']['qualityOre'],
            nine['schedule']['lexicographic']['qualityOre'],
        )

    def test_cheaper_nine_rest_beats_expensive_ten(self):
        d, _ = self.weekday_demand(1)
        d['employees'][0]['hourlyCost'] = 100
        other = deepcopy(d['employees'][0])
        other['id'] = 'e2'
        other['code'] = 'M02'
        other['hourlyCost'] = 800
        d['employees'].append(other)
        r = _solve()(d, 25)
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        by = {}
        for s in r['schedule']['shifts']:
            by.setdefault(s['employeeId'], set()).add(s['date'])
        self.assertEqual(len(by.get('e1', ())), 19)
        self.assertEqual(len(by.get('e2', ())), 0)

    def test_solver_rest_days_across_period_boundary(self):
        d, _ = self.weekday_demand(0)
        d['workplace']['start'] = '2026-09-28'
        days = _days('2026-09-07', 28)
        work = [day for day in days if date.fromisoformat(day).weekday() < 5]
        period = set(_days('2026-09-28', 7))
        d['interventions'] = [
            dict(id=f't{i}', customerId='c1', name='Stöd', type='fixed', start='09:00',
                 latestEnd='10:00', minutes=60, doubleStaff=False, weekdays=[1],
                 date=day, skills=['Omsorg'])
            for i, day in enumerate(d for d in work if d in period)
        ]
        d['boundaryShifts'] = [
            dict(id=f'b{i}', employeeId='e1', date=day, start='08:00', end='12:00', type='day', skills=['Omsorg'], breaks=[])
            for i, day in enumerate(d for d in work if d < '2026-09-28')
        ]
        r = _solve()(d, 20)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertGreater(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
        self.assertNotIn('REST_DAYS', {e['rule'] for e in r['validation']['errors']})

    def test_old_payload_without_min_rest_key_still_solves(self):
        d, _ = fixture()
        self.assertNotIn('minRestDaysInFourWeeks', d['rules'])
        d['rules']['nightFloor'] = 0
        r = _solve()(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(r['schedule']['lexicographic']['uncoveredMinutes'], 0)
        self.assertTrue(r['validation']['valid'])
