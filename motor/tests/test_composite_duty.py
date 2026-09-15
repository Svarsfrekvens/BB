import importlib.util
import unittest
from test_rules import fixture, cover_f01
from bb.domain import (
    build_duty_occasion, calendar_work_days, consecutive_pass_run, duty_occasions,
    occasion_exceeds_max_span, occasion_profile_id, span, required_rest_after_minutes,
)
from bb.validate import validate


def evening():
    return dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[])


def jour():
    return dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def morning():
    return dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[])


def long_morning():
    return dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='15:00', type='day', skills=['Omsorg'], breaks=[])


def chain_payload(morning_end='10:00', max_span=None):
    d, _ = fixture()
    d['workplace']['end'] = '2026-09-08'
    cover_f01(d)
    d['templates'] = [
        dict(id='E', name='Kväll', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
        dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]),
        dict(id='M', name='Morgon', start='06:30', end=morning_end, type='day', skills=['Omsorg'], breaks=[]),
    ]
    d['employees'][0]['profiles'] = ['E', 'J', 'M']
    d['employees'][0]['jour'] = True
    d['employees'][0]['night'] = False
    d['rules']['nightFloor'] = 0
    d['rules']['jourFloor'] = 1
    d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[1])
    if max_span is not None:
        d['rules']['shiftProfiles'] = dict(combinedWorkJour=dict(maxSpanHours=max_span))
    d['interventions'] = [
        dict(id='t1', customerId='c1', name='Kväll', type='fixed', start='16:00', latestEnd='17:00',
             minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-07', skills=['Omsorg']),
        dict(id='t2', customerId='c1', name='Morgon', type='fixed', start='07:00', latestEnd='08:00',
             minutes=60, doubleStaff=False, weekdays=[2], date='2026-09-08', skills=['Omsorg']),
    ]
    return d


def selected_occasions(schedule, rules):
    from collections import defaultdict
    by_emp = defaultdict(list)
    for s in schedule.get('shifts') or []:
        by_emp[s['employeeId']].append(s)
    out = []
    for rows in by_emp.values():
        for group in duty_occasions(rows):
            out.append(build_duty_occasion(group, rules))
    return out


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

    def test_configured_max_span_18_rejects_19h_chain(self):
        self.d['rules']['shiftProfiles'] = dict(combinedWorkJour=dict(maxSpanHours=18))
        self.s['shifts'] = [evening(), jour(), morning()]
        self.assertTrue(occasion_exceeds_max_span(self.s['shifts'], self.d['rules']))
        err, _, valid = self.codes()
        self.assertIn('COMPOSITE_LENGTH', err)
        self.assertFalse(valid)

    def test_jour_alone_is_not_combined_work_jour(self):
        self.s['shifts'] = [jour()]
        self.assertEqual(occasion_profile_id(self.s['shifts'], self.d['rules']), 'normal')
        self.assertFalse(occasion_exceeds_max_span(self.s['shifts'], self.d['rules']))
        err, _, valid = self.codes()
        self.assertNotIn('COMPOSITE_LENGTH', err)
        self.assertTrue(valid)

    def test_two_ordinary_work_shifts_are_separate_occasions(self):
        self.s['shifts'] = [
            dict(id='a', employeeId='e1', date='2026-09-07', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='b', employeeId='e1', date='2026-09-08', start='06:30', end='15:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        groups = duty_occasions(self.s['shifts'])
        self.assertEqual(len(groups), 2)
        self.assertFalse(any(occasion_exceeds_max_span(g, self.d['rules']) for g in groups))
        err, _, valid = self.codes()
        self.assertNotIn('COMPOSITE_LENGTH', err)
        self.assertTrue(valid)


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class CompositeDutySolver(unittest.TestCase):
    def forced_status(self, shifts, rules):
        from ortools.sat.python import cp_model
        from bb.domain import paid as paid_work
        from bb.solver import _as_bool, forbid_overlong_occasions
        model = cp_model.CpModel()
        items = []
        for s in shifts:
            a, b = span(s)
            x = model.new_bool_var(s['id'])
            model.add(x == 1)
            items.append(dict(shift=s, a=a, b=b, work=paid_work(s), x=x))
        forbid_overlong_occasions(model, items, rules, lambda var, name: _as_bool(model, var, name), prefix='t')
        sv = cp_model.CpSolver()
        return sv.status_name(sv.solve(model))

    def assert_no_overlong_occasion(self, result, rules):
        self.assertNotEqual(result['schedule']['solverStatus'], 'MODEL_INVALID')
        from collections import defaultdict
        by_emp = defaultdict(list)
        for s in result['schedule'].get('shifts') or []:
            by_emp[s['employeeId']].append(s)
        for rows in by_emp.values():
            for group in duty_occasions(rows):
                self.assertFalse(occasion_exceeds_max_span(group, rules))
        if result.get('validation'):
            self.assertNotIn('COMPOSITE_LENGTH', {e['rule'] for e in result['validation']['errors']})

    def test_solver_allows_exact_19h_work_jour_work(self):
        d, s = fixture()
        d['employees'][0]['jour'] = True
        d['rules']['nightFloor'] = 0
        d['interventions'] = []
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        segs = [evening(), jour(), morning()]
        self.assertIn(self.forced_status(segs, d['rules']), ['OPTIMAL', 'FEASIBLE'])
        s['shifts'] = segs
        s['assignments'] = []
        result = validate(d, s)
        self.assertNotIn('COMPOSITE_LENGTH', {e['rule'] for e in result['errors']})
        self.assertTrue(result['valid'])
        occ = build_duty_occasion(duty_occasions(segs)[0], d['rules'])
        self.assertEqual(occ['spanMinutes'] / 60, 19)
        self.assertAlmostEqual(occ['paidMinutes'] / 60, 11.5, places=5)
        self.assertGreater(occ['jourMinutes'] / 60, 7)

    def test_solver_cannot_select_24h_work_jour_work(self):
        d, s = fixture()
        d['employees'][0]['jour'] = True
        d['rules']['nightFloor'] = 0
        d['interventions'] = []
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        segs = [evening(), jour(), long_morning()]
        self.assertEqual(self.forced_status(segs, d['rules']), 'INFEASIBLE')
        s['shifts'] = segs
        s['assignments'] = []
        self.assertIn('COMPOSITE_LENGTH', {e['rule'] for e in validate(d, s)['errors']})
        from bb.solver import solve
        r = solve(chain_payload('15:00'), 12)
        self.assert_no_overlong_occasion(r, d['rules'])
        for occ in selected_occasions(r['schedule'], d['rules']):
            self.assertLessEqual(occ['spanMinutes'] / 60, 19 + 1e-9)

    def test_solver_reads_configured_max_span_not_hardcoded_19(self):
        d, s = fixture()
        d['employees'][0]['jour'] = True
        d['rules']['nightFloor'] = 0
        d['interventions'] = []
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        d['rules']['shiftProfiles'] = dict(combinedWorkJour=dict(maxSpanHours=18))
        segs = [evening(), jour(), morning()]
        self.assertEqual(self.forced_status(segs, d['rules']), 'INFEASIBLE')
        s['shifts'] = segs
        s['assignments'] = []
        self.assertIn('COMPOSITE_LENGTH', {e['rule'] for e in validate(d, s)['errors']})
        from bb.solver import solve
        r = solve(chain_payload('10:00', max_span=18), 12)
        self.assert_no_overlong_occasion(r, d['rules'])

    def test_solver_jour_alone_is_not_composite_length(self):
        d, _ = fixture()
        d['templates'].append(dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]))
        d['employees'][0]['profiles'] = ['D', 'J']
        d['employees'][0]['jour'] = True
        d['employees'][0]['night'] = False
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 1
        d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[1])
        self.assertIn(self.forced_status([jour()], d['rules']), ['OPTIMAL', 'FEASIBLE'])
        from bb.solver import solve
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        jour_shifts = [s for s in r['schedule']['shifts'] if s.get('type') == 'jour']
        self.assertGreaterEqual(len(jour_shifts), 1)
        for occ in selected_occasions(r['schedule'], d['rules']):
            if occ['jourMinutes'] and not occ['paidMinutes']:
                self.assertEqual(occ['profile'], 'normal')
        if r.get('validation'):
            self.assertNotIn('COMPOSITE_LENGTH', {e['rule'] for e in r['validation']['errors']})

    def test_solver_two_ordinary_work_shifts_unaffected(self):
        d, _ = fixture()
        segs = [
            dict(id='a', employeeId='e1', date='2026-09-07', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='b', employeeId='e1', date='2026-09-08', start='06:30', end='15:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        self.assertIn(self.forced_status(segs, d['rules']), ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(len(duty_occasions(segs)), 2)
