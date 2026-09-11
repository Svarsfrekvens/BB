import importlib.util
import unittest
from test_rules import fixture, cover_f01
from bb.domain import span
from bb.replan import apply_impact, collect_locked_shifts, impact_from_change
from bb.validate import validate


def _shift(sid, eid, day, start, end, typ='day'):
    return dict(id=sid, employeeId=eid, date=day, start=start, end=end, type=typ, skills=['Omsorg'], breaks=[])


class Berordhet(unittest.TestCase):
    def test_absence_opens_person_and_buffer_not_whole_period(self):
        d, s = fixture()
        cover_f01(d)
        d['workplace']['end'] = '2026-10-04'
        d['existingSchedule'] = dict(shifts=[
            _shift('p1', 'e1', '2026-09-14', '08:00', '16:00'),
            _shift('p2', 'e1', '2026-09-21', '08:00', '16:00'),
        ])
        impact = impact_from_change(d, dict(type='absence', employeeId='e1', start='2026-09-21', end='2026-09-23'))
        self.assertEqual(impact['planningRange']['start'], '2026-09-20')
        self.assertEqual(impact['planningRange']['end'], '2026-09-24')
        self.assertIn('e1', impact['affectedEmployeeIds'])
        self.assertIn('p2', impact['affectedShiftIds'])
        self.assertNotIn('p1', impact['affectedShiftIds'])
        self.assertTrue(impact['lockedOutsidePlanningRange'])
        span_days = ( __import__('datetime').date.fromisoformat(impact['planningRange']['end'])
                      - __import__('datetime').date.fromisoformat(impact['planningRange']['start']) ).days
        self.assertLess(span_days, 20)

    def test_need_change_opens_those_dates(self):
        d, _ = fixture()
        cover_f01(d)
        d['workplace']['end'] = '2026-10-04'
        d['existingSchedule'] = dict(shifts=[_shift('k1', 'e1', '2026-09-10', '09:00', '15:00')])
        impact = impact_from_change(d, dict(type='customerNeed', date='2026-09-10', customerId='c1'))
        self.assertEqual(impact['planningRange']['start'], '2026-09-10')
        self.assertEqual(impact['planningRange']['end'], '2026-09-10')
        apply_impact(d, dict(type='customerNeed', date='2026-09-10'))
        self.assertEqual(d['planningRange']['start'], '2026-09-10')
        self.assertTrue(d['lockedOutsidePlanningRange'])


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas')
class LasningSolver(unittest.TestCase):
    def _base(self):
        d, s = fixture()
        d['planningMode'] = 'generateFromNeeds'
        d['templates'] = []
        d['employees'][0]['profiles'] = []
        d['employees'][0]['night'] = True
        d['rules']['nightFloor'] = 0
        d['workplace']['end'] = '2026-10-04'
        cover_f01(d)
        d['interventions'] = [
            dict(id='t1', customerId='c1', name='Stöd', type='fixed', start='09:00', latestEnd='10:00',
                 minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-07', skills=['Omsorg']),
            dict(id='t2', customerId='c1', name='Stöd', type='fixed', start='09:00', latestEnd='10:00',
                 minutes=60, doubleStaff=False, weekdays=[1], date='2026-09-21', skills=['Omsorg']),
        ]
        return d, s

    def test_locked_outside_range_kept_exactly(self):
        from bb.solver import solve
        d, _ = self._base()
        locked = _shift('lock-w1', 'e1', '2026-09-07', '09:00', '10:00')
        d['existingSchedule'] = dict(shifts=[locked])
        d['planningRange'] = dict(start='2026-09-21', end='2026-09-27')
        d['lockedOutsidePlanningRange'] = True
        self.assertEqual([s['id'] for s in collect_locked_shifts(d)], ['lock-w1'])
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        kept = [s for s in r['schedule']['shifts'] if s['id'] == 'lock-w1']
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]['start'], '09:00')
        self.assertEqual(kept[0]['end'], '10:00')
        self.assertEqual(kept[0]['date'], '2026-09-07')
        moved = [s for s in r['schedule']['shifts'] if s['date'] == '2026-09-07' and s['id'] != 'lock-w1']
        self.assertEqual(moved, [])
        err = {e['rule'] for e in r['validation']['errors']}
        self.assertNotIn('REST_DAYS', err)

    def test_locked_shift_ids_cannot_be_moved(self):
        from bb.solver import solve
        d, _ = self._base()
        locked = _shift('pin', 'e1', '2026-09-21', '09:00', '10:00')
        d['existingSchedule'] = dict(shifts=[locked])
        d['lockedShiftIds'] = ['pin']
        d['planningRange'] = dict(start='2026-09-21', end='2026-09-27')
        r = solve(d, 8)
        pin = [s for s in r['schedule']['shifts'] if s['id'] == 'pin']
        self.assertEqual(len(pin), 1)
        self.assertEqual((pin[0]['start'], pin[0]['end']), ('09:00', '10:00'))

    def test_locked_conflict_explains_and_does_not_unlock(self):
        from bb.solver import solve
        d, _ = self._base()
        d['absences'] = [dict(id='a', employeeId='e1', start='2026-09-07', end='2026-09-07')]
        locked = _shift('trap', 'e1', '2026-09-07', '09:00', '16:00')
        d['existingSchedule'] = dict(shifts=[locked])
        d['lockedShiftIds'] = ['trap']
        r = solve(d, 4)
        self.assertEqual(r['schedule']['solverStatus'], 'INFEASIBLE')
        self.assertIn('LOCKED_CONFLICT', {x['code'] for x in r['schedule']['preCheck']})
        self.assertIn('inte hävts', r['schedule']['explanation'])
        self.assertEqual(d['lockedShiftIds'], ['trap'])

    def test_rest_and_week_rest_see_locked_across_range(self):
        d, s = self._base()
        s['shifts'] = [
            _shift('late', 'e1', '2026-09-20', '14:00', '22:00'),
            _shift('early', 'e1', '2026-09-21', '07:00', '15:00'),
        ]
        s['assignments'] = []
        d['interventions'] = []
        d['planningRange'] = dict(start='2026-09-21', end='2026-09-27')
        d['lockedOutsidePlanningRange'] = True
        d['existingSchedule'] = dict(shifts=[s['shifts'][0]])
        codes = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('REST', codes)
        a, b = span(s['shifts'][0])
        self.assertGreater(b - a, 7 * 60)

    def test_week_rest_still_applies_with_range(self):
        d, s = fixture()
        d['workplace']['end'] = '2026-10-04'
        cover_f01(d)
        d['interventions'] = []
        d['rules']['nightFloor'] = 0
        s['assignments'] = []
        s['shifts'] = [_shift(f'w{i}', 'e1', f'2026-09-{7+i:02d}', '08:00', '20:00') for i in range(7)]
        d['planningRange'] = dict(start='2026-09-10', end='2026-09-13')
        d['existingSchedule'] = dict(shifts=list(s['shifts']))
        d['lockedOutsidePlanningRange'] = True
        codes = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('WEEK_REST', codes)

    def test_f01_counts_locked_outside_range(self):
        d, s = fixture()
        d['workplace']['end'] = '2026-10-04'
        cover_f01(d)
        d['interventions'] = []
        d['rules']['nightFloor'] = 0
        days = [f'2026-09-{i:02d}' for i in range(7, 27)]
        s['shifts'] = [_shift(f'w{i}', 'e1', day, '08:00', '16:00') for i, day in enumerate(days)]
        s['assignments'] = []
        d['planningRange'] = dict(start='2026-09-28', end='2026-10-04')
        d['lockedOutsidePlanningRange'] = True
        d['existingSchedule'] = dict(shifts=list(s['shifts']))
        codes = {e['rule'] for e in validate(d, s)['errors']}
        self.assertIn('REST_DAYS', codes)
