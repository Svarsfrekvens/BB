import unittest
from copy import deepcopy
from test_rules import fixture, cover_f01
from bb.domain import check_input, days, paid, ssg_cap_minutes, weekly_minutes_for_day
from bb.validate import validate


CATALOG = [
    dict(id='helgfri-40', name='Helgfri vecka 40 h', weeklyMinutes=40 * 60, reductionRuleId='t04-pending'),
    dict(id='vardag-helg-37', name='Vardag och sön/helg 37 h', weeklyMinutes=37 * 60),
    dict(id='standig-natt-36-20', name='Ständig natt 36 h 20 min', weeklyMinutes=36 * 60 + 20),
    dict(id='fri-32', name='Fritt mått 32 h', weeklyMinutes=32 * 60),
]


def workplace_with_models(d, default='vardag-helg-37'):
    d['workplace']['workTimeModels'] = deepcopy(CATALOG)
    d['workplace']['defaultWorkTimeModelId'] = default
    return d


def week_days():
    return list(days('2026-09-07', '2026-09-13'))


def day_shift(eid, sid, day, start='08:00', end='16:00', typ='day', breaks=None):
    return dict(id=sid, employeeId=eid, date=day, start=start, end=end, type=typ, skills=['Omsorg'], breaks=breaks or [])


class WorkTimeModel(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['maxConsecutiveDays'] = 7
        d['rules']['maxWeeklyHours'] = 48
        self.d, self.s = d, s

    def codes(self):
        return {e['rule'] for e in validate(self.d, self.s)['errors']}

    def test_old_payload_uses_full_time_weekly_hours(self):
        e = self.d['employees'][0]
        self.d['rules']['fullTimeWeeklyHours'] = 40
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'])
        self.assertAlmostEqual(cap / 60, 40, places=5)
        check_input(self.d)

    def test_business_default(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        self.d['rules']['fullTimeWeeklyHours'] = 40
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 37, places=5)

    def test_individual_override(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeModelId'] = 'helgfri-40'
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 40, places=5)

    def test_window_overrides_person_and_default(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeModelId'] = 'helgfri-40'
        e['workTimeWindows'] = [dict(start='2026-09-07', end='2026-09-13', modelId='fri-32')]
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 32, places=5)

    def test_37_hours_as_input(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeModelId'] = 'vardag-helg-37'
        self.assertAlmostEqual(weekly_minutes_for_day(e, '2026-09-07', self.d['rules'], self.d['workplace']), 37 * 60)

    def test_36_hours_20_as_input(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeModelId'] = 'standig-natt-36-20'
        self.assertAlmostEqual(weekly_minutes_for_day(e, '2026-09-07', self.d['rules'], self.d['workplace']), 36 * 60 + 20)

    def test_arbitrary_weekly_measure(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeWindows'] = [dict(start='2026-09-07', end='2026-09-13', weeklyMinutes=29 * 60 + 15)]
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 29.25, places=5)

    def test_75_percent_ssg_times_37(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['ssg'] = 75
        e['workTimeModelId'] = 'vardag-helg-37'
        cap = ssg_cap_minutes(e, week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 0.75 * 37, places=5)

    def test_dated_ssg_and_dated_measure(self):
        workplace_with_models(self.d)
        self.d['workplace']['end'] = '2026-09-20'
        e = self.d['employees'][0]
        e['ssg'] = 100
        e['ssgWindows'] = [
            dict(start='2026-09-07', end='2026-09-13', ssg=75),
            dict(start='2026-09-14', end='2026-09-20', ssg=100),
        ]
        e['workTimeWindows'] = [
            dict(start='2026-09-07', end='2026-09-13', modelId='vardag-helg-37'),
            dict(start='2026-09-14', end='2026-09-20', modelId='helgfri-40'),
        ]
        cap = ssg_cap_minutes(e, list(days('2026-09-07', '2026-09-20')), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 0.75 * 37 + 40, places=5)

    def test_model_change_mid_period(self):
        workplace_with_models(self.d)
        self.d['workplace']['end'] = '2026-09-20'
        e = self.d['employees'][0]
        e['workTimeWindows'] = [
            dict(start='2026-09-07', end='2026-09-13', modelId='vardag-helg-37'),
            dict(start='2026-09-14', end='2026-09-20', modelId='standig-natt-36-20'),
        ]
        cap = ssg_cap_minutes(e, list(days('2026-09-07', '2026-09-20')), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap / 60, 37 + (36 + 20 / 60), places=5)

    def test_two_people_different_caps(self):
        workplace_with_models(self.d)
        self.d['employees'].append(dict(**{**self.d['employees'][0], 'id': 'e2', 'code': 'M02'}))
        self.d['employees'][0]['workTimeModelId'] = 'vardag-helg-37'
        self.d['employees'][1]['workTimeModelId'] = 'standig-natt-36-20'
        days7 = week_days()
        cap_a = ssg_cap_minutes(self.d['employees'][0], days7, self.d['rules'], self.d['workplace'])
        cap_b = ssg_cap_minutes(self.d['employees'][1], days7, self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap_a / 60, 37, places=5)
        self.assertAlmostEqual(cap_b / 60, 36 + 20 / 60, places=5)
        self.s['shifts'] = [
            day_shift('e1', 'a1', '2026-09-07'),
            day_shift('e1', 'a2', '2026-09-08'),
            day_shift('e1', 'a3', '2026-09-09'),
            day_shift('e1', 'a4', '2026-09-10'),
            day_shift('e1', 'a5', '2026-09-11', '08:00', '12:40'),
            day_shift('e2', 'b1', '2026-09-07'),
            day_shift('e2', 'b2', '2026-09-08'),
            day_shift('e2', 'b3', '2026-09-09'),
            day_shift('e2', 'b4', '2026-09-10'),
            day_shift('e2', 'b5', '2026-09-11', '08:00', '12:40'),
        ]
        errors = [e for e in validate(self.d, self.s)['errors'] if e['rule'] == 'CONTRACT']
        who = {e['employeeId'] for e in errors}
        self.assertNotIn('e1', who)
        self.assertIn('e2', who)

    def test_first_employee_model_does_not_affect_other(self):
        workplace_with_models(self.d)
        self.d['employees'].append(dict(**{**self.d['employees'][0], 'id': 'e2', 'code': 'M02'}))
        self.d['employees'][0]['workTimeModelId'] = 'helgfri-40'
        cap_b = ssg_cap_minutes(self.d['employees'][1], week_days(), self.d['rules'], self.d['workplace'])
        self.assertAlmostEqual(cap_b / 60, 37, places=5)

    def test_jour_is_not_paid_capacity(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['workTimeModelId'] = 'vardag-helg-37'
        self.s['shifts'] = [
            day_shift('e1', 'd1', '2026-09-07'),
            day_shift('e1', 'j1', '2026-09-08', '23:00', '06:30', 'jour'),
        ]
        self.assertEqual(paid(self.s['shifts'][1]), [])
        self.assertNotIn('CONTRACT', self.codes())

    def test_break_is_unpaid(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['ssg'] = 100
        e['workTimeWindows'] = [dict(start='2026-09-07', end='2026-09-13', weeklyMinutes=int(7.5 * 60))]
        self.s['shifts'] = [day_shift('e1', 'd1', '2026-09-07', breaks=[dict(offset=180, minutes=30)])]
        self.assertNotIn('CONTRACT', self.codes())
        self.s['shifts'] = [day_shift('e1', 'd1', '2026-09-07')]
        self.assertIn('CONTRACT', self.codes())

    def test_max_weekly_hours_48_unchanged(self):
        workplace_with_models(self.d)
        self.d['employees'][0]['workTimeWindows'] = [dict(start='2026-09-07', end='2026-09-13', weeklyMinutes=56 * 60)]
        self.d['rules']['maxWeeklyHours'] = 48
        self.s['shifts'] = [
            day_shift('e1', f's{i}', day, '06:00', '16:00')
            for i, day in enumerate(['2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11'])
        ]
        self.assertIn('WEEK_HOURS', self.codes())
        self.assertEqual(self.d['rules']['maxWeeklyHours'], 48)

    def test_no_night_special_case_in_engine(self):
        workplace_with_models(self.d)
        e = self.d['employees'][0]
        e['night'] = True
        self.assertAlmostEqual(
            weekly_minutes_for_day(e, '2026-09-07', self.d['rules'], self.d['workplace']) / 60,
            37,
            places=5,
        )
        e['night'] = False
        self.assertAlmostEqual(
            weekly_minutes_for_day(e, '2026-09-07', self.d['rules'], self.d['workplace']) / 60,
            37,
            places=5,
        )
