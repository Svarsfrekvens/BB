import unittest
from test_rules import fixture, cover_f01
from bb.domain import (
    build_duty_occasion, calendar_work_days, consecutive_pass_run, duty_occasions,
    occasion_profile_id, paid, span, required_rest_after_minutes,
)
from bb.validate import validate


def evening():
    return dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[])


def jour():
    return dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def morning():
    return dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[])


class CompositeDuty(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        d['employees'][0]['jour'] = True
        self.d, self.s = d, s

    def codes(self):
        r = validate(self.d, self.s)
        return {e['rule'] for e in r['errors']}, {w['rule'] for w in r['warnings']}, r['valid']

    def test_work_jour_work_is_one_occasion_19h(self):
        self.s['shifts'] = [evening(), jour(), morning()]
        groups = duty_occasions(self.s['shifts'])
        self.assertEqual(len(groups), 1)
        occ = build_duty_occasion(groups[0], self.d['rules'])
        self.assertEqual(occ['profile'], 'combinedWorkJour')
        self.assertEqual(occ['spanMinutes'] / 60, 19)
        self.assertAlmostEqual(occ['paidMinutes'] / 60, 11.5, places=5)
        self.assertGreater(occ['jourMinutes'] / 60, 7)
        self.assertLess(occ['ssgMinutes'], occ['spanMinutes'])
        self.assertEqual(sum(calendar_work_days(self.s['shifts'], '2026-09-07', '2026-09-13')), 1)
        err, _, valid = self.codes()
        self.assertNotIn('REST', err)
        self.assertNotIn('CONTRACT', err)
        self.assertTrue(valid)

    def test_jour_blocks_rest_between_separate_occasions(self):
        self.s['shifts'] = [
            dict(id='d', employeeId='e1', date='2026-09-07', start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]),
            jour(),
        ]
        self.assertEqual(len(duty_occasions(self.s['shifts'])), 2)
        err, _, _ = self.codes()
        self.assertIn('REST', err)

    def test_following_duty_needs_rest_after_composite(self):
        self.s['shifts'] = [
            evening(), jour(), morning(),
            dict(id='n', employeeId='e1', date='2026-09-08', start='16:00', end='20:00', type='evening', skills=['Omsorg'], breaks=[]),
        ]
        self.assertGreater(required_rest_after_minutes(duty_occasions(self.s['shifts'][:3])[0], self.d['rules']), 11 * 60)
        err, _, _ = self.codes()
        self.assertIn('COMP_REST', err)

    def test_night_plus_morning_not_composite(self):
        self.s['shifts'] = [
            dict(id='n', employeeId='e1', date='2026-09-07', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[]),
            dict(id='d', employeeId='e1', date='2026-09-08', start='08:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        self.assertEqual(len(duty_occasions(self.s['shifts'])), 2)
        err, _, _ = self.codes()
        self.assertIn('REST', err)

    def test_two_work_segments_without_jour_do_not_skip_rest(self):
        self.s['shifts'] = [
            dict(id='a', employeeId='e1', date='2026-09-07', start='15:00', end='18:00', type='evening', skills=['Omsorg'], breaks=[]),
            dict(id='b', employeeId='e1', date='2026-09-07', start='19:00', end='22:00', type='evening', skills=['Omsorg'], breaks=[]),
        ]
        self.assertEqual(len(duty_occasions(self.s['shifts'])), 2)
        err, _, _ = self.codes()
        self.assertIn('REST', err)

    def test_short_jour_invalid_for_combined_profile(self):
        short = dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='00:30', type='jour', skills=[], breaks=[])
        self.s['shifts'] = [
            evening(),
            short,
            dict(id='m', employeeId='e1', date='2026-09-08', start='01:00', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        err, _, valid = self.codes()
        self.assertIn('COMPOSITE_JOUR_WINDOW', err)
        self.assertFalse(valid)

    def test_global_max_shift_rejects_20h_single(self):
        self.s['shifts'] = [dict(id='long', employeeId='e1', date='2026-09-07', start='10:00', end='06:00', type='night', skills=['Omsorg'], breaks=[])]
        err, _, _ = self.codes()
        self.assertIn('SHIFT_LENGTH', err)

    def test_24h_requires_extended_profile(self):
        segs = [
            dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
            dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='08:00', type='jour', skills=[], breaks=[]),
            dict(id='m', employeeId='e1', date='2026-09-08', start='08:00', end='15:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        self.s['shifts'] = segs
        self.assertEqual(occasion_profile_id(segs, self.d['rules']), 'combinedWorkJour')
        err, _, _ = self.codes()
        self.assertIn('COMPOSITE_LENGTH', err)
        tagged = [{**s, 'dutyProfile': 'extendedCombinedWorkJour'} if s['id'] == 'j' else s for s in segs]
        self.s['shifts'] = tagged
        self.assertEqual(occasion_profile_id(tagged, self.d['rules']), 'extendedCombinedWorkJour')
        err, _, valid = self.codes()
        self.assertNotIn('COMPOSITE_LENGTH', err)
        self.assertNotIn('SHIFT_LENGTH', err)
        self.assertTrue(valid)

    def test_two_nights_same_start_date_count_as_two(self):
        a = dict(id='n1', employeeId='e1', date='2026-09-07', start='00:30', end='07:30', type='night', skills=['Omsorg'], breaks=[])
        b = dict(id='n2', employeeId='e1', date='2026-09-07', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])
        self.assertEqual(consecutive_pass_run([a, b], 'night'), 2)

    def test_f01_and_jour_caps_still_hold(self):
        cover_f01(self.d)
        self.s['shifts'] = [evening(), jour(), morning()]
        err, _, valid = self.codes()
        self.assertNotIn('REST_DAYS', err)
        self.assertNotIn('JOUR_4W', err)
        self.assertNotIn('JOUR_MONTH', err)
        self.assertTrue(valid)

    def test_week_rest_still_sees_jour_span(self):
        self.d['workplace']['end'] = '2026-09-13'
        cover_f01(self.d)
        self.s['shifts'] = [
            dict(id=f'd{i}', employeeId='e1', date=f'2026-09-{7 + i:02d}', start='08:00', end='20:00', type='day', skills=['Omsorg'], breaks=[])
            for i in range(6)
        ]
        self.s['shifts'].append(jour())
        err, _, _ = self.codes()
        self.assertIn('WEEK_REST', err)
