import importlib.util
import unittest
from datetime import date, timedelta
from test_rules import fixture, cover_f01
from bb.validate import validate
from bb.domain import add_days


def sources(result):
    return {(w.get('sourceRule') or w.get('rule')) for w in result.get('warnings') or [] if w.get('rule') == 'BOUNDARY_HISTORY'}


def day_shift(sid, day, start, end, typ='day', eid='e1'):
    return dict(id=sid, employeeId=eid, date=day, start=start, end=end, type=typ, skills=['Omsorg'] if typ != 'jour' else [], breaks=[])


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class BoundaryFacts(unittest.TestCase):
    def base(self):
        d, _ = fixture()
        d['interventions'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['jourFloor'] = 0
        d['employees'][0]['jour'] = True
        cover_f01(d)
        return d

    def solve(self, d, seconds=8):
        from bb.solver import solve
        return solve(d, seconds)

    def test_a_boundary_boundary_rest_is_history_not_infeasible(self):
        d = self.base()
        d['boundaryShifts'] = [
            day_shift('b1', '2026-09-06', '06:30', '10:00'),
            day_shift('b2', '2026-09-06', '15:00', '23:00', 'evening'),
        ]
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('REST', sources(val))
        self.assertNotIn('REST', {e['rule'] for e in val['errors']})

    def test_b_boundary_candidate_rest_forbids_candidate(self):
        d, s = fixture()
        d['rules']['nightFloor'] = 0
        cover_f01(d)
        d['boundaryShifts'] = [{**s['shifts'][0], 'id': 'before', 'date': '2026-09-06', 'start': '13:00', 'end': '21:00'}]
        r = self.solve(d, 5)
        self.assertEqual(r['schedule']['shifts'], [])
        self.assertEqual(sum(u['count'] for u in r['schedule']['uncovered']), 1)

    def test_c_candidate_candidate_rest_unchanged(self):
        d, s = fixture()
        cover_f01(d)
        d['rules']['nightFloor'] = 0
        s['shifts'] = [
            day_shift('s1', '2026-09-07', '06:30', '10:00'),
            day_shift('s2', '2026-09-07', '15:00', '23:00', 'evening'),
        ]
        s['assignments'] = []
        d['interventions'] = []
        err = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('REST', err)

    def test_d_boundary_only_jour_over_48h_is_history(self):
        d = self.base()
        d['templates'].append(dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]))
        d['employees'][0]['profiles'] = ['D', 'J']
        rows = []
        start = date.fromisoformat('2026-08-15')
        for i in range(8):
            day = (start + timedelta(days=i)).isoformat()
            rows.append(day_shift(f'j{i}', day, '23:00', '06:30', 'jour'))
        d['boundaryShifts'] = rows
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('JOUR_4W', sources(val))
        self.assertNotIn('JOUR_4W', {e['rule'] for e in val['errors']})

    def test_e_no_new_jour_when_fixed_already_over_48h(self):
        d = self.base()
        d['workplace']['start'] = '2026-09-07'
        d['workplace']['end'] = '2026-09-13'
        cover_f01(d)
        d['templates'].append(dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]))
        d['employees'][0]['profiles'] = ['D', 'J']
        rows = []
        start = date.fromisoformat('2026-08-20')
        for i in range(8):
            day = (start + timedelta(days=i)).isoformat()
            rows.append(day_shift(f'j{i}', day, '23:00', '06:30', 'jour'))
        d['boundaryShifts'] = rows
        d['rules']['jourFloor'] = 0
        r = self.solve(d, 10)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        new_jour = [s for s in r['schedule']['shifts'] if s.get('type') == 'jour' and s['date'] <= '2026-09-16']
        self.assertEqual(new_jour, [])

    def test_f_boundary_only_week_rest_is_history(self):
        d = self.base()
        rows = []
        for i in range(6):
            day = add_days('2026-09-01', i)
            rows.append(day_shift(f'w{i}', day, '08:00', '20:00'))
        d['boundaryShifts'] = rows
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('WEEK_REST', sources(val))
        self.assertNotIn('WEEK_REST', {e['rule'] for e in val['errors']})

    def test_g_candidate_cannot_destroy_valid_week_rest(self):
        d, s = fixture()
        cover_f01(d)
        d['rules']['nightFloor'] = 0
        d['rules']['minWeeklyRestHours'] = 36
        d['workplace']['end'] = '2026-09-13'
        cover_f01(d)
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = [
            day_shift(f'd{i}', f'2026-09-{7 + i:02d}', '08:00', '20:00')
            for i in range(6)
        ]
        s['shifts'].append(day_shift('j', '2026-09-07', '23:00', '06:30', 'jour'))
        err = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('WEEK_REST', err)

    def test_h_boundary_only_compensatory_rest_is_history(self):
        d = self.base()
        d['boundaryShifts'] = [
            day_shift('e', '2026-09-05', '15:00', '23:00', 'evening'),
            day_shift('j', '2026-09-05', '23:00', '06:30', 'jour'),
            day_shift('m', '2026-09-06', '10:00', '12:00'),
        ]
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('COMP_REST', sources(val))
        self.assertNotIn('COMP_REST', {e['rule'] for e in val['errors']})

    def test_i_composite_boundary_history_and_candidate_forbidden(self):
        d = self.base()
        d['boundaryShifts'] = [
            day_shift('e', '2026-09-05', '15:00', '23:00', 'evening'),
            day_shift('j', '2026-09-05', '23:00', '06:30', 'jour'),
            day_shift('m', '2026-09-06', '06:30', '15:00'),
        ]
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('COMPOSITE_LENGTH', sources(val))
        self.assertNotIn('COMPOSITE_LENGTH', {e['rule'] for e in val['errors']})

        d2, s2 = fixture()
        d2['interventions'] = []
        d2['rules']['nightFloor'] = 0
        d2['employees'][0]['jour'] = True
        cover_f01(d2)
        s2['assignments'] = []
        s2['shifts'] = [
            day_shift('e', '2026-09-07', '15:00', '23:00', 'evening'),
            day_shift('j', '2026-09-07', '23:00', '06:30', 'jour'),
            day_shift('m', '2026-09-08', '06:30', '15:00'),
        ]
        self.assertIn('COMPOSITE_LENGTH', {e['rule'] for e in validate(d2, s2)['errors']})

    def test_j_f01_history_vs_candidate_limit(self):
        d = self.base()
        rows = []
        start = date.fromisoformat('2026-08-11')
        for i in range(20):
            day = (start + timedelta(days=i)).isoformat()
            rows.append(day_shift(f'w{i}', day, '08:00', '16:00'))
        d['boundaryShifts'] = rows
        r = self.solve(d)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r['validation'] or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('REST_DAYS', sources(val))
        self.assertNotIn('REST_DAYS', {e['rule'] for e in val['errors']})
