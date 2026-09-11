import importlib.util
import unittest
from datetime import date, timedelta
from test_rules import fixture
from bb.domain import (
    calendar_work_days,
    consecutive_six_seven_counts,
    has_consecutive_off,
    rest_days_missing_in_windows,
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

    def test_nine_rest_days_no_penalty(self):
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5][:-1]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        worked = calendar_work_days(self.s['shifts'], '2026-09-07', '2026-10-04')
        self.assertEqual(rest_days_missing_in_windows(worked, 28, 9), 0)
        self.assertNotIn('REST_DAYS_SOFT', self.codes('warnings'))

    def test_eight_rest_days_soft_warning(self):
        self.d['workplace']['end'] = '2026-10-04'
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertIn('REST_DAYS_SOFT', self.codes('warnings'))

    def test_nine_rest_days_can_be_disabled(self):
        self.d['workplace']['end'] = '2026-10-04'
        self.d['rules']['minRestDaysInFourWeeks'] = 0
        days = _days('2026-09-07', 28)
        work = [d for d in days if date.fromisoformat(d).weekday() < 5]
        self.s['shifts'] = [_shift('e1', f's{i}', day) for i, day in enumerate(work)]
        res = validate(self.d, self.s)
        self.assertTrue(res['valid'])
        self.assertNotIn('REST_DAYS_SOFT', self.codes('warnings'))

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
