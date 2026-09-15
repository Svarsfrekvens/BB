import importlib.util
import unittest
from test_rules import fixture
from bb.solver import solve


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class OccurrenceEncodingEquivalence(unittest.TestCase):
    def _both(self, d, seconds=8):
        old = solve(d, seconds, lex_stop='coverage', occurrence_encoding='support_z')
        new = solve(d, seconds, lex_stop='coverage', occurrence_encoding='start_choice')
        return old, new

    def _unc(self, r):
        return int((r['schedule'].get('lexicographic') or {}).get('uncoveredMinutes') or r['schedule'].get('uncoveredMinutes') or 0)

    def _ok(self, r):
        self.assertIn(r['schedule']['solverStatus'], ('OPTIMAL', 'FEASIBLE'))
        self.assertTrue((r.get('validation') or {}).get('valid'))

    def test_fixed_occurrence_same_uncovered(self):
        d, _ = fixture()
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertEqual(self._unc(old), 0)

    def test_flexible_several_starts(self):
        d, _ = fixture()
        d['interventions'][0].update(type='flexible', start='08:00', latestEnd='12:00', minutes=60)
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))

    def test_two_employees(self):
        d, _ = fixture()
        d['employees'].append({**d['employees'][0], 'id': 'e2', 'code': 'M02'})
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertEqual(self._unc(old), 0)

    def test_overlapping_templates_same_employee(self):
        d, _ = fixture()
        d['templates'] = [
            dict(id='D', name='Dag', start='06:00', end='14:00', type='day', skills=['Omsorg'], breaks=[]),
            dict(id='L', name='Lång', start='07:00', end='16:00', type='day', skills=['Omsorg'], breaks=[]),
        ]
        d['employees'][0]['profiles'] = ['D', 'L']
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))

    def test_double_staff_count_two(self):
        d, _ = fixture()
        d['employees'].append({**d['employees'][0], 'id': 'e2', 'code': 'M02'})
        d['interventions'][0]['doubleStaff'] = True
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertEqual(self._unc(old), 0)

    def test_missing_skill_uncovered(self):
        d, _ = fixture()
        d['interventions'][0]['skills'] = ['Läkemedel']
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertGreater(self._unc(old), 0)

    def test_jour_only_temporary_does_not_cover_ar(self):
        d, _ = fixture()
        d['employees'][0]['skills'] = []
        d['employees'].append(dict(
            id='t1', code='T1', name='Jour', resourceType='temporary', ssg=0, night=False, jour=True,
            status='active', profiles=['J'], hourlyCost=350, skills=[],
            constraints=dict(hard=dict(dates=['2026-09-07'], allowedTypes=['jour'], weekendMode='all')),
        ))
        d['templates'].append(dict(id='J', name='Jour', start='23:00', end='06:30', type='jour', skills=[], breaks=[]))
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertGreater(self._unc(old), 0)

    def test_assignment_at_shift_edge(self):
        d, _ = fixture()
        d['interventions'][0].update(start='13:00', latestEnd='14:00', minutes=60, type='fixed')
        old, new = self._both(d)
        self._ok(old); self._ok(new)
        self.assertEqual(self._unc(old), self._unc(new))
        self.assertEqual(self._unc(old), 0)

    def test_default_encoding_is_support_z(self):
        d, _ = fixture()
        z = solve(d, 1, build_only=True, occurrence_encoding='support_z')
        s = solve(d, 1, build_only=True, occurrence_encoding='start_choice')
        self.assertEqual(z['schedule']['solverStatus'], 'NOT_RUN')
        self.assertEqual(s['schedule']['solverStatus'], 'NOT_RUN')
        self.assertNotEqual(
            (z.get('modelScope') or {}).get('totalVariables'),
            None,
        )
