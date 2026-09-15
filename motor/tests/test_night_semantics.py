import importlib.util
import unittest
from test_rules import fixture, cover_f01
from bb.domain import is_night, pass_requires_night_eligibility, span, time_overlaps_night_interval
from bb.precheck import slot_eligible
from bb.validate import validate


def evening_15_23(eid='e1', sid='e'):
    return dict(id=sid, employeeId=eid, date='2026-09-07', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[])


def night_21_0730(eid='e1', sid='n'):
    return dict(id=sid, employeeId=eid, date='2026-09-07', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])


def jour_23_0630(eid='e1', sid='j'):
    return dict(id=sid, employeeId=eid, date='2026-09-07', start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def _slot(e, template, day, data):
    sample = dict(template, date=day, breaks=template.get('breaks') or [])
    a, b = span(sample)
    return slot_eligible(e, template, day, a, b, data, data['rules'], [], [])


class NightSemantics(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 60
        d['rules']['fullTimeWeeklyHours'] = 60
        d['employees'][0]['night'] = False
        d['employees'][0]['jour'] = False
        self.d, self.s = d, s

    def codes(self):
        r = validate(self.d, self.s)
        return {e['rule'] for e in r['errors']}, {w.get('sourceRule') for w in r['warnings'] if w.get('rule') == 'BOUNDARY_HISTORY'}, r['valid']

    def test_night_a_evening_15_23_without_night_flag(self):
        tpl = dict(id='E', name='Kväll', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[])
        a, b = span(evening_15_23())
        self.assertTrue(time_overlaps_night_interval(a, b))
        self.assertTrue(is_night(a, b))
        self.assertFalse(pass_requires_night_eligibility(tpl))
        self.assertTrue(_slot(self.d['employees'][0], tpl, '2026-09-07', self.d))
        self.s['shifts'] = [evening_15_23()]
        err, _, valid = self.codes()
        self.assertNotIn('NIGHT', err)
        self.assertTrue(valid)

    def test_night_b_night_type_without_flag_forbidden(self):
        tpl = dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])
        self.assertTrue(pass_requires_night_eligibility(tpl))
        self.assertFalse(_slot(self.d['employees'][0], tpl, '2026-09-07', self.d))
        self.s['shifts'] = [night_21_0730()]
        err, _, valid = self.codes()
        self.assertIn('NIGHT', err)
        self.assertFalse(valid)

    def test_night_c_night_type_with_flag_allowed(self):
        self.d['employees'][0]['night'] = True
        tpl = dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])
        self.assertTrue(_slot(self.d['employees'][0], tpl, '2026-09-07', self.d))
        self.s['shifts'] = [night_21_0730()]
        err, _, valid = self.codes()
        self.assertNotIn('NIGHT', err)
        self.assertTrue(valid)

    def test_night_d_jour_without_night_flag(self):
        self.d['employees'][0]['jour'] = True
        tpl = dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[])
        self.assertFalse(pass_requires_night_eligibility(tpl))
        self.assertTrue(_slot(self.d['employees'][0], tpl, '2026-09-07', self.d))
        self.s['shifts'] = [jour_23_0630()]
        err, _, valid = self.codes()
        self.assertNotIn('NIGHT', err)
        self.assertNotIn('JOUR', err)
        self.assertTrue(valid)

    def test_night_e_boundary_night_is_history(self):
        self.d['boundaryShifts'] = [night_21_0730(sid='bn')]
        r = validate(self.d, self.s)
        self.assertTrue(r['valid'])
        self.assertNotIn('NIGHT', {e['rule'] for e in r['errors']})
        hist = [w for w in r['warnings'] if w.get('rule') == 'BOUNDARY_HISTORY' and w.get('sourceRule') == 'NIGHT']
        self.assertEqual(len(hist), 1)


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class NightSemanticsSolver(unittest.TestCase):
    def solve(self, d, seconds=8):
        from bb.solver import solve
        return solve(d, seconds)

    def evening_payload(self, night=False):
        d, _ = fixture()
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Kväll', type='fixed', start='16:00', latestEnd='17:00',
                 minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-07', skills=['Omsorg']),
        ]
        d['templates'] = [dict(id='E', name='Kväll', start='15:00', end='23:00', type='evening', skills=['Omsorg'], breaks=[])]
        d['employees'][0]['profiles'] = ['E']
        d['employees'][0]['night'] = night
        d['rules']['nightFloor'] = 0
        cover_f01(d)
        return d

    def test_night_a_solver_allows_evening(self):
        r = self.solve(self.evening_payload(False))
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(any(s.get('type') == 'evening' for s in r['schedule']['shifts']))
        val = r.get('validation') or {}
        self.assertNotIn('NIGHT', {e['rule'] for e in val.get('errors') or []})
        self.assertTrue(val.get('valid'))

    def test_night_b_solver_rejects_night_without_flag(self):
        d, _ = fixture()
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Natt', type='fixed', start='23:00', latestEnd='00:00',
                 minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-07', skills=['Omsorg']),
        ]
        d['templates'] = [dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])]
        d['employees'][0]['profiles'] = ['N']
        d['employees'][0]['night'] = False
        d['rules']['nightFloor'] = 0
        cover_f01(d)
        r = self.solve(d)
        self.assertFalse(any(s.get('type') == 'night' for s in r['schedule']['shifts']))
        val = r.get('validation') or {}
        self.assertNotIn('NIGHT', {e['rule'] for e in val.get('errors') or []})

    def test_night_c_solver_allows_night_with_flag(self):
        d, _ = fixture()
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Natt', type='fixed', start='23:00', latestEnd='00:00',
                 minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-07', skills=['Omsorg']),
        ]
        d['templates'] = [dict(id='N', name='Natt', start='21:00', end='07:30', type='night', skills=['Omsorg'], breaks=[])]
        d['employees'][0]['profiles'] = ['N']
        d['employees'][0]['night'] = True
        d['rules']['nightFloor'] = 0
        cover_f01(d)
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(any(s.get('type') == 'night' for s in r['schedule']['shifts']))

    def test_night_d_solver_allows_jour_without_night(self):
        d, _ = fixture()
        d['interventions'] = []
        d['templates'].append(dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]))
        d['employees'][0]['profiles'] = ['D', 'J']
        d['employees'][0]['night'] = False
        d['employees'][0]['jour'] = True
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 1
        d['rules']['jour'] = dict(start='23:00', end='06:30', weekdays=[1])
        cover_f01(d)
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        self.assertTrue(any(s.get('type') == 'jour' for s in r['schedule']['shifts']))
        val = r.get('validation') or {}
        self.assertNotIn('NIGHT', {e['rule'] for e in val.get('errors') or []})

    def test_night_e_solver_boundary_night_not_invalid(self):
        d, _ = fixture()
        d['interventions'] = []
        d['employees'][0]['night'] = False
        d['rules']['nightFloor'] = 0
        d['boundaryShifts'] = [night_21_0730(sid='bn')]
        cover_f01(d)
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r.get('validation') or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertNotIn('NIGHT', {e['rule'] for e in val['errors']})
        self.assertIn('NIGHT', {w.get('sourceRule') for w in val['warnings'] if w.get('rule') == 'BOUNDARY_HISTORY'})
