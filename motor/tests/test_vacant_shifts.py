"""Öppna Före-pass är information, inte solverkapacitet."""
import importlib.util
import unittest
from copy import deepcopy

from test_rules import fixture
from bb.domain import check_input, active_employees
from bb.solver import solve


class VacantShiftModelTests(unittest.TestCase):
    def test_vacant_shifts_accepted_but_not_employees(self):
        d, _ = fixture()
        d['vacantShifts'] = [dict(
            id='open1',
            date='2026-09-07',
            start='07:00',
            end='16:00',
            type='day',
            kod='Ar',
            rowLabel='Schemarad 1',
            source='medvind',
            origin='fore',
        )]
        d['openShifts'] = d['vacantShifts']
        check_input(d)
        self.assertEqual(len(active_employees(d)), 1)
        self.assertEqual(active_employees(d)[0]['id'], 'e1')

    def test_temp_pool_is_not_solver_staff(self):
        d, _ = fixture()
        d['employees'].append({**d['employees'][0], 'id': 'pool1', 'code': 'P1', 'resourceType': 'temp_pool'})
        self.assertEqual([e['id'] for e in active_employees(d)], ['e1'])

    @unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas')
    def test_vac_f_open_shifts_do_not_change_candidate_count(self):
        d, _ = fixture()
        r1 = solve(d, 1, build_only=True)
        d2 = deepcopy(d)
        d2['vacantShifts'] = [dict(
            id='open1',
            date='2026-09-07',
            start='07:00',
            end='16:00',
            type='day',
            kod='Ar',
            rowLabel='Vakant dag',
            source='medvind',
            origin='fore',
        )]
        r2 = solve(d2, 1, build_only=True)
        self.assertEqual(r1['modelScope']['candidateShifts'], r2['modelScope']['candidateShifts'])
        self.assertEqual(r1['diagnostics']['performance']['solverVariables'], r2['diagnostics']['performance']['solverVariables'])
