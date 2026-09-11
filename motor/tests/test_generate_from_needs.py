import importlib.util
import unittest
from copy import deepcopy
from test_rules import fixture
from bb.domain import check_input, duty_occasions, paid, span
from bb.generate import generate_shift_templates, need_intervals, planning_mode
from bb.precheck import enumerate_person_shift_slots, feasibility_precheck
from bb.validate import validate


def gen_base():
    d, s = fixture()
    d['planningMode'] = 'generateFromNeeds'
    d['existingSchedule'] = None
    d['current'] = None
    d['templates'] = []
    d['employees'][0]['profiles'] = []
    d['employees'][0]['night'] = True
    d['employees'][0]['jour'] = True
    d['rules']['nightFloor'] = 0
    d['rules']['preferredMinShiftMinutes'] = 240
    d['rules']['minGeneratedShiftMinutes'] = 0
    return d, s


def task(tid, start, minutes, date='2026-09-07', **extra):
    h, m = start.split(':')
    end_m = int(h) * 60 + int(m) + minutes
    latest = f'{end_m // 60:02d}:{end_m % 60:02d}' if end_m < 24 * 60 else start
    row = dict(
        id=tid, customerId='c1', name='Stöd', type='fixed', start=start, latestEnd=latest,
        minutes=minutes, doubleStaff=False, weekdays=[1], date=date, skills=['Omsorg'],
    )
    row.update(extra)
    return row


class GenerateFromNeeds(unittest.TestCase):
    def test_mode_and_null_schedule_accepted(self):
        d, _ = gen_base()
        check_input(d)
        self.assertEqual(planning_mode(d), 'generateFromNeeds')
        self.assertIsNone(d['existingSchedule'])

    def test_simple_need_creates_candidates(self):
        d, _ = gen_base()
        d['interventions'] = [task('t1', '09:00', 60)]
        tm = generate_shift_templates(d)
        self.assertGreaterEqual(len(tm), 1)
        self.assertTrue(any(t['start'] == '09:00' and t['end'] == '10:00' for t in tm))
        self.assertLess(len(tm), 30)

    def test_breakpoints_make_limited_reasonable_candidates(self):
        d, _ = gen_base()
        d['interventions'] = (
            [task(f'a{i}', '07:00', 420) for i in range(2)]
            + [task(f'b{i}', '14:00', 180) for i in range(3)]
            + [task(f'c{i}', '17:00', 300) for i in range(2)]
        )
        tm = generate_shift_templates(d)
        clocks = {(t['start'], t['end']) for t in tm if t['type'] != 'jour'}
        self.assertIn(('07:00', '14:00'), clocks)
        self.assertTrue(any(s == '07:00' and e in ('17:00', '22:00') for s, e in clocks))
        self.assertTrue(any(s == '14:00' and e in ('17:00', '21:00', '22:00') for s, e in clocks))
        self.assertLessEqual(len(tm), 24)
        minutes = (22 - 7) * 60
        self.assertLess(len(tm), minutes)

    def test_not_minute_for_minute(self):
        d, _ = gen_base()
        d['interventions'] = [task('t1', '07:00', 180), task('t2', '10:00', 240)]
        tm = generate_shift_templates(d)
        starts = {t['start'] for t in tm}
        self.assertTrue(starts <= {'07:00', '10:00', '13:00', '14:00', '22:00', '23:00'})
        self.assertNotIn('07:01', starts)

    def test_night_need_creates_night_candidates(self):
        d, _ = gen_base()
        d['interventions'] = [task('n1', '22:00', 480)]
        tm = generate_shift_templates(d)
        self.assertTrue(any(t['type'] == 'night' for t in tm))

    def test_jour_floor_creates_jour_candidates(self):
        d, _ = gen_base()
        d['rules']['jourFloor'] = 1
        d['interventions'] = [task('t1', '15:00', 480)]
        tm = generate_shift_templates(d)
        self.assertTrue(any(t['type'] == 'jour' for t in tm))

    def test_composite_segments_group_with_existing_logic(self):
        d, _ = gen_base()
        d['rules']['jourFloor'] = 1
        d['interventions'] = [task('e', '15:00', 480), task('m', '06:30', 210, date='2026-09-08')]
        tm = generate_shift_templates(d)
        types = {t['type'] for t in tm}
        self.assertIn('jour', types)
        segs = [
            dict(id='e', employeeId='e1', date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[]),
            dict(id='j', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[]),
            dict(id='m', employeeId='e1', date='2026-09-08', start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        self.assertEqual(len(duty_occasions(segs)), 1)

    def test_prefilter_night_jour_skill_customer_time(self):
        d, _ = gen_base()
        d['templates'] = [
            dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[]),
            dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]),
            dict(id='D', name='Dag', start='07:00', end='16:00', type='day', skills=['Läkemedel'], breaks=[]),
        ]
        d['planningMode'] = 'optimizeExisting'
        d['employees'][0]['profiles'] = ['N', 'J', 'D']
        d['employees'][0]['night'] = False
        d['employees'][0]['jour'] = False
        d['employees'][0]['skills'] = ['Omsorg']
        d['employees'][0]['constraints'] = dict(hard=dict(
            forbiddenCustomerIds=['c1'],
            earliestStart='12:00',
        ))
        enum = enumerate_person_shift_slots(d)
        night = [s for s in enum['slots'] if s['template']['type'] == 'night']
        jour = [s for s in enum['slots'] if s['template']['type'] == 'jour']
        drug = [s for s in enum['slots'] if s['template']['id'] == 'D']
        self.assertTrue(night and all(not s['eligible'] for s in night))
        self.assertTrue(jour and all(not s['eligible'] for s in jour))
        self.assertTrue(drug and all(not s['eligible'] for s in drug))
        self.assertGreater(enum['before'], enum['after'])

    def test_ssg_50_does_not_target_19_days(self):
        d, _ = gen_base()
        d['employees'][0]['ssg'] = 50
        d['interventions'] = [task('t1', '07:00', 420)]
        tm = generate_shift_templates(d)
        enum = enumerate_person_shift_slots(d)
        work_days = {s['day'] for s in enum['slots'] if s['eligible'] and s['template']['type'] != 'jour'}
        self.assertLessEqual(len(work_days), 2)
        self.assertLess(len(tm), 19)
        self.assertFalse(any((span(dict(date=s['day'], start=s['template']['start'], end=s['template']['end']))[1]
                              - span(dict(date=s['day'], start=s['template']['start'], end=s['template']['end']))[0]) < 60
                             for s in enum['slots'] if s['eligible']))

    def test_precheck_codes(self):
        d, _ = gen_base()
        d['employees'] = []
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('NO_EMPLOYEES', codes)

        d, _ = gen_base()
        d['employees'][0]['ssg'] = 10
        d['interventions'] = [task(f't{i}', '07:00', 480) for i in range(8)]
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('SSG_CAPACITY_SHORT', codes)

        d, _ = gen_base()
        d['employees'].append({**d['employees'][0], 'id': 'e2', 'code': 'M02'})
        d['interventions'] = [task(f't{i}', '17:00', 300) for i in range(3)]
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('INSUFFICIENT_TOTAL_CAPACITY', codes)

        d, _ = gen_base()
        d['rules']['nightFloor'] = 1
        d['employees'][0]['night'] = False
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('NIGHT_STAFF_SHORT', codes)
        self.assertEqual(d['rules']['nightFloor'], 1)

        d, _ = gen_base()
        d['rules']['jourFloor'] = 1
        d['employees'][0]['jour'] = False
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('JOUR_STAFF_SHORT', codes)
        self.assertEqual(d['rules']['jourFloor'], 1)

        d, _ = gen_base()
        d['interventions'][0]['skills'] = ['Läkemedel']
        d['employees'][0]['skills'] = ['Omsorg']
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('SKILL_SHORTAGE', codes)

        d, _ = gen_base()
        d['employees'][0]['constraints'] = dict(hard=dict(forbiddenCustomerIds=['c1']))
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('CUSTOMER_LINK_BLOCK', codes)

        d, _ = gen_base()
        d['rules']['nightFloor'] = 1
        d['employees'][0]['constraints'] = dict(hard=dict(allowedTypes=['day']))
        codes = {x['code'] for x in feasibility_precheck(d)}
        self.assertIn('HARD_PROFILE_BLOCKS', codes)

        d, _ = gen_base()
        codes = {x['code'] for x in feasibility_precheck(d) if x['severity'] == 'critical'}
        self.assertEqual(codes, set())

    def test_need_intervals_use_existing_customer_model(self):
        d, _ = gen_base()
        rows = need_intervals(d)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['customerId'], 'c1')
        self.assertEqual(rows[0]['count'], 1)


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class GenerateFromNeedsSolver(unittest.TestCase):
    def test_generate_without_existing_schedule(self):
        from bb.solver import solve
        d, _ = gen_base()
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(r['validation']['valid'])
        self.assertEqual(r['modelScope']['planningMode'], 'generateFromNeeds')
        self.assertGreater(r['modelScope']['generatedShiftTemplates'], 0)
        self.assertGreaterEqual(r['modelScope']['personShiftCombinationsBeforeFilter'],
                                r['modelScope']['personShiftCombinationsAfterFilter'])
        self.assertIn('solverVariables', r['modelScope'])
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']), 0)

    def test_optimize_existing_still_works(self):
        from bb.solver import solve
        d, _ = fixture()
        self.assertEqual(planning_mode(d), 'optimizeExisting')
        r = solve(d, 5)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(validate(d, r['schedule'])['valid'])
        self.assertEqual(len(r['schedule']['assignments']), 1)

    def test_infeasible_night_explains_precheck(self):
        from bb.solver import solve
        d, _ = gen_base()
        d['planningMode'] = 'optimizeExisting'
        d['templates'] = [dict(id='D', name='Dag', start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[])]
        d['employees'][0]['profiles'] = ['D']
        d['employees'][0]['night'] = False
        d['rules']['nightFloor'] = 1
        r = solve(d, 3)
        self.assertEqual(r['schedule']['solverStatus'], 'INFEASIBLE')
        self.assertIn('NIGHT_STAFF_SHORT', {x['code'] for x in r['schedule']['preCheck']})
        self.assertIn('nattbehöriga tillgängliga', r['schedule']['explanation'])
        self.assertNotEqual(r['schedule']['explanation'], 'Ingen lösning hittades')
        self.assertEqual(d['rules']['nightFloor'], 1)

    def test_regression_f01_rest_week_jour_series(self):
        from bb.solver import solve
        d, s = fixture()
        d['rules']['nightFloor'] = 0
        r = solve(d, 5)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        s2 = deepcopy(r['schedule'])
        err = {e['rule'] for e in validate(d, s2)['errors']}
        self.assertNotIn('REST_DAYS', err)
        self.assertNotIn('WEEK_REST', err)
        nights = [
            dict(id=f'n{i}', employeeId='e1', date=f'2026-09-{7+i:02d}', start='21:00', end='07:30',
                 type='night', skills=['Omsorg'], breaks=[])
            for i in range(2)
        ]
        s['shifts'] = nights
        s['assignments'] = []
        d['employees'][0]['night'] = True
        d['interventions'] = []
        codes, warns = {e['rule'] for e in validate(d, s)['errors']}, {w['rule'] for w in validate(d, s)['warnings']}
        self.assertNotIn('NIGHT_SERIES', codes)
        self.assertNotIn('NIGHT_SERIES_SOFT', warns)
        d2, s2 = fixture()
        d2['employees'][0]['jour'] = False
        s2['shifts'] = [dict(id='j1', employeeId='e1', date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])]
        s2['assignments'] = []
        self.assertIn('JOUR', {e['rule'] for e in validate(d2, s2)['errors']})
        self.assertEqual(paid(s2['shifts'][0]), [])
        a, b = span(s2['shifts'][0])
        self.assertGreater(b - a, 7 * 60)
