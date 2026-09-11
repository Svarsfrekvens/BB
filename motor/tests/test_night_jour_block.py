import unittest
from copy import deepcopy
from test_rules import fixture, cover_f01
from bb.domain import (
    calendar_work_days, longest_true_run, paid, span, type_start_date_flags,
    duty_occasions, occasion_span, max_jour_in_night_windows, compensatory_from_occasion,
)
from bb.validate import validate


def _night(eid, sid, day):
    return dict(id=sid, employeeId=eid, date=day, start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])


def _jour(eid, sid, day):
    return dict(id=sid, employeeId=eid, date=day, start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def _days(start, n):
    from datetime import date, timedelta
    d = date.fromisoformat(start)
    return [(d + timedelta(days=i)).isoformat() for i in range(n)]


class NightJourBlock(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        d['employees'][0]['jour'] = False
        self.d, self.s = d, s

    def res(self):
        return validate(self.d, self.s)

    def codes(self):
        r = self.res()
        return {e['rule'] for e in r['errors']}, {w['rule'] for w in r['warnings']}

    def test_one_night_is_one_series_unit(self):
        self.s['shifts'] = [_night('e1', 'n1', '2026-09-07')]
        flags = type_start_date_flags(self.s['shifts'], 'night', '2026-09-07', '2026-09-13')
        self.assertEqual(sum(flags), 1)
        self.assertEqual(longest_true_run(flags), 1)
        flags_cal = calendar_work_days(self.s['shifts'], '2026-09-07', '2026-09-13')
        self.assertEqual(sum(flags_cal), 1)

    def test_two_nights_are_series_two(self):
        self.s['shifts'] = [_night('e1', f'n{i}', day) for i, day in enumerate(_days('2026-09-07', 2))]
        flags = type_start_date_flags(self.s['shifts'], 'night', '2026-09-07', '2026-09-13')
        self.assertEqual(longest_true_run(flags), 2)
        err, warn = self.codes()
        self.assertNotIn('NIGHT_SERIES', err)
        self.assertNotIn('NIGHT_SERIES_SOFT', warn)
        self.assertNotIn('NIGHT_SERIES_STRONG', warn)

    def test_three_nights_soft_yellow(self):
        self.s['shifts'] = [_night('e1', f'n{i}', day) for i, day in enumerate(_days('2026-09-07', 3))]
        err, warn = self.codes()
        self.assertNotIn('NIGHT_SERIES', err)
        self.assertIn('NIGHT_SERIES_SOFT', warn)
        self.assertNotIn('NIGHT_SERIES_STRONG', warn)
        self.assertTrue(self.res()['valid'])

    def test_four_nights_strong_soft_still_valid(self):
        self.s['shifts'] = [_night('e1', f'n{i}', day) for i, day in enumerate(_days('2026-09-07', 4))]
        err, warn = self.codes()
        self.assertNotIn('NIGHT_SERIES', err)
        self.assertIn('NIGHT_SERIES_STRONG', warn)
        self.assertTrue(self.res()['valid'])

    def test_individual_hard_night_cap_invalidates_four(self):
        self.d['employees'][0]['constraints'] = dict(hard=dict(maxNightConsecutive=3))
        self.s['shifts'] = [_night('e1', f'n{i}', day) for i, day in enumerate(_days('2026-09-07', 4))]
        err, _ = self.codes()
        self.assertIn('NIGHT_SERIES', err)
        self.assertFalse(self.res()['valid'])

    def test_jour_one_series_unit(self):
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [_jour('e1', 'j1', '2026-09-07')]
        flags = type_start_date_flags(self.s['shifts'], 'jour', '2026-09-07', '2026-09-13')
        self.assertEqual(sum(flags), 1)
        self.assertEqual(longest_true_run(flags), 1)

    def test_two_jour_are_series_two(self):
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [_jour('e1', f'j{i}', day) for i, day in enumerate(_days('2026-09-07', 2))]
        flags = type_start_date_flags(self.s['shifts'], 'jour', '2026-09-07', '2026-09-13')
        self.assertEqual(longest_true_run(flags), 2)
        err, _ = self.codes()
        self.assertNotIn('JOUR_SERIES', err)
        self.assertTrue(self.res()['valid'])

    def test_individual_hard_jour_cap(self):
        self.d['employees'][0]['jour'] = True
        self.d['employees'][0]['constraints'] = dict(hard=dict(maxJourConsecutive=1))
        self.s['shifts'] = [_jour('e1', f'j{i}', day) for i, day in enumerate(_days('2026-09-07', 2))]
        err, _ = self.codes()
        self.assertIn('JOUR_SERIES', err)
        self.assertFalse(self.res()['valid'])

    def test_night_without_jour_cannot_take_jour(self):
        self.d['employees'][0]['night'] = True
        self.d['employees'][0]['jour'] = False
        self.s['shifts'] = [_jour('e1', 'j1', '2026-09-07')]
        err, _ = self.codes()
        self.assertIn('JOUR', err)
        self.assertNotIn('NIGHT', err)

    def test_jour_eligible_can_take_jour(self):
        self.d['employees'][0]['night'] = False
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [_jour('e1', 'j1', '2026-09-07')]
        err, _ = self.codes()
        self.assertNotIn('JOUR', err)
        self.assertNotIn('NIGHT', err)
        self.assertTrue(self.res()['valid'])

    def test_night_then_morning_is_not_chained(self):
        self.s['shifts'] = [
            _night('e1', 'n1', '2026-09-07'),
            dict(id='d', employeeId='e1', date='2026-09-08', start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        self.assertEqual(len(duty_occasions(self.s['shifts'])), 2)
        err, _ = self.codes()
        self.assertIn('REST', err)

    def test_composite_work_jour_work_no_internal_rest(self):
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [
            dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
            _jour('e1', 'j', '2026-09-07'),
            dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        groups = duty_occasions(self.s['shifts'])
        self.assertEqual(len(groups), 1)
        self.assertEqual(sum(calendar_work_days(self.s['shifts'], '2026-09-07', '2026-09-13')), 1)
        err, _ = self.codes()
        self.assertNotIn('REST', err)
        paid_h = sum(b - a for s in self.s['shifts'] for a, b in paid(s)) / 60
        self.assertAlmostEqual(paid_h, 8 + 3.5, places=5)
        jour_h = (span(_jour('e1', 'j', '2026-09-07'))[1] - span(_jour('e1', 'j', '2026-09-07'))[0]) / 60
        self.assertGreater(jour_h, 7)
        self.assertGreaterEqual(max_jour_in_night_windows(groups[0], self.d['rules']), 5 * 60)
        self.assertNotIn('CONTRACT', err)

    def test_jour_is_not_daily_rest_for_separate_duties(self):
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [
            dict(id='d', employeeId='e1', date='2026-09-07', start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]),
            _jour('e1', 'j', '2026-09-07'),
        ]
        err, _ = self.codes()
        self.assertIn('REST', err)

    def test_standalone_duties_still_need_eleven_hours(self):
        self.s['shifts'] = [
            dict(id='a', employeeId='e1', date='2026-09-07', start='14:00', end='22:00', type='evening', skills=['Omsorg'], breaks=[]),
            dict(id='b', employeeId='e1', date='2026-09-08', start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        err, _ = self.codes()
        self.assertIn('REST', err)

    def test_short_jour_in_composite_fails_window(self):
        self.d['employees'][0]['jour'] = True
        short = dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='00:30', type='jour', skills=[], breaks=[])
        self.s['shifts'] = [
            dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
            short,
            dict(id='m', employeeId='e1', date='2026-09-08', start='01:00', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        err, _ = self.codes()
        self.assertIn('COMPOSITE_JOUR_WINDOW', err)

    def test_composite_requires_compensatory_rest_after(self):
        self.d['employees'][0]['jour'] = True
        self.s['shifts'] = [
            dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
            _jour('e1', 'j', '2026-09-07'),
            dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='next', employeeId='e1', date='2026-09-08', start='16:00', end='20:00', type='evening', skills=['Omsorg'], breaks=[]),
        ]
        owed = compensatory_from_occasion(duty_occasions(self.s['shifts'][:3])[0], 'e1', self.d['rules'])
        self.assertIsNotNone(owed)
        err, _ = self.codes()
        self.assertIn('COMP_REST', err)

    def test_f01_workday_unchanged_on_night(self):
        self.s['shifts'] = [_night('e1', 'n1', '2026-09-07')]
        flags = calendar_work_days(self.s['shifts'], '2026-09-07', '2026-09-13')
        self.assertEqual(sum(flags), 1)
        self.assertTrue(flags[1])
        cover_f01(self.d)
        err, _ = self.codes()
        self.assertNotIn('REST_DAYS', err)

    def test_compensatory_rest_schema_accepted(self):
        self.d['compensatoryRest'] = [dict(
            employeeId='e1', sourceDutyOccasionIds=['x'], earnedFrom='2026-09-06',
            minutesOwed=11 * 60, mustFollowImmediately=True, consumeBy=None, status='owed',
        )]
        from bb.domain import check_input
        check_input(self.d)
