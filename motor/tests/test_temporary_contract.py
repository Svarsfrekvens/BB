"""P0: temporary med ssg=0 får inte fällas av SSG-CONTRACT.

Produktsemantik: temporary är explicit, utan syntetisk SSG.
ssg=0 är inte ett nolltimmarskontrakt. Periodtak är bara maxPaidMinutes.
"""
from __future__ import annotations

import importlib.util
import unittest
from copy import deepcopy

from test_rules import fixture
from bb.validate import validate


def _temporary(d, **hard):
    e = d['employees'][0]
    e['resourceType'] = 'temporary'
    e['ssg'] = 0
    e['ssgWindows'] = []
    e['hourlyCost'] = 350
    wp = d['workplace']
    dates = [wp['start'], wp['end']]
    e['constraints'] = dict(
        hard=dict(
            weekendMode='all',
            allowedTypes=['day', 'evening', 'night'],
            dates=dates,
            **hard,
        )
    )
    return d


class TemporaryContractSemantics(unittest.TestCase):
    def test_ssg_zero_temporary_shift_is_not_ssg_contract(self):
        d, s = fixture()
        _temporary(d)
        s = deepcopy(s)
        s['shifts'][0]['employeeId'] = d['employees'][0]['id']
        s['assignments'][0]['employeeId'] = d['employees'][0]['id']
        val = validate(d, s)
        self.assertFalse(any(e.get('rule') == 'CONTRACT' for e in val['errors']))
        self.assertTrue(val['valid'])

    def test_employee_ssg_zero_still_contract(self):
        d, s = fixture()
        d['employees'][0]['ssg'] = 0
        val = validate(d, s)
        self.assertIn('CONTRACT', {e.get('rule') for e in val['errors']})
        self.assertFalse(val['valid'])

    def test_temporary_max_paid_is_enforced(self):
        d, s = fixture()
        _temporary(d, maxPaidMinutes=30)
        s = deepcopy(s)
        val = validate(d, s)
        self.assertIn('CONTRACT', {e.get('rule') for e in val['errors']})
        self.assertTrue(any('maxtak' in (e.get('message') or '') for e in val['errors']))


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas')
class TemporarySolveValidatorSync(unittest.TestCase):
    def test_solve_ssg_zero_temporary_is_not_model_invalid(self):
        from bb.solver import solve
        d, _ = fixture()
        _temporary(d)
        r = solve(d, 5)
        sch = r['schedule']
        self.assertIn(sch.get('solverStatus'), ('OPTIMAL', 'FEASIBLE'))
        self.assertTrue(sch.get('assignments'))
        self.assertNotEqual(sch.get('solverStatus'), 'MODEL_INVALID')
        val = r.get('validation') or {}
        self.assertTrue(val.get('valid'))
        self.assertFalse(any(e.get('rule') == 'CONTRACT' for e in val.get('errors') or []))
        replay = validate(d, sch)
        self.assertEqual(replay.get('valid'), val.get('valid'))
        self.assertEqual(
            {e.get('rule') for e in replay.get('errors') or []},
            {e.get('rule') for e in val.get('errors') or []},
        )
