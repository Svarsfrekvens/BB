"""P0: Galaxen 28d inputtak, precheck och explicit temporary. Ändrar inte solver.py."""
from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from bb.domain import add_days, check_input, days, occurrences
from bb.limits import CEILING_MAX_OCCURRENCES
from bb.precheck import feasibility_precheck, has_critical_precheck
from bb.jour_capacity import analyze_jour_capacity

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / 'qa' / 'scripts' / '_galaxen_28d.json'


def _load():
    raw = json.loads(DUMP.read_text(encoding='utf-8'))
    return raw['data']


def _temps(data, n=6):
    jour_base = next(e for e in data['employees'] if e.get('jour'))
    out = deepcopy(data)
    mallar = [t['id'] for t in (data.get('templates') or [])]
    for i in range(n):
        e = deepcopy(jour_base)
        e['id'] = f'temp{i+1}'
        e['code'] = f'T{i+1}'
        e['name'] = f'Extra {i+1}'
        e['resourceType'] = 'temporary'
        e['status'] = 'active'
        e['jour'] = True
        e['night'] = True
        e['ssg'] = 0
        e['ssgWindows'] = []
        e.pop('workTimeWindows', None)
        e.pop('workTimeModelId', None)
        e['profiles'] = mallar
        wp = data['workplace']
        datum = [add_days(wp['start'], -1), *days(wp['start'], wp['end'])]
        e['constraints'] = dict(
            hard=dict(
                weekendMode='all',
                allowedTypes=['day', 'evening', 'night', 'jour'],
                dates=datum,
            ),
        )
        out['employees'].append(e)
    return out


@unittest.skipUnless(DUMP.exists(), 'Galaxen 28d-dump saknas')
class Galaxen28dInput(unittest.TestCase):
    def test_2541_with_ceiling_limit_is_accepted(self):
        d = _load()
        d['limits'] = dict(maxOccurrences=CEILING_MAX_OCCURRENCES)
        check_input(d)
        self.assertEqual(len(occurrences(d)), 2541)

    def test_2541_without_limits_is_rejected_at_default(self):
        d = _load()
        d.pop('limits', None)
        with self.assertRaises(ValueError) as ctx:
            check_input(d)
        self.assertIn('1600', str(ctx.exception))

    def test_more_than_4000_is_stopped(self):
        d = _load()
        d['limits'] = dict(maxOccurrences=CEILING_MAX_OCCURRENCES)
        check_input(d)
        with self.assertRaises(ValueError):
            d2 = deepcopy(d)
            d2['limits'] = dict(maxOccurrences=4001)
            check_input(d2)
        extra = deepcopy(d['interventions'][0])
        while len(d['interventions']) <= 4000:
            i = len(d['interventions'])
            d['interventions'].append(dict(extra, id=f'over{i}', date='2026-08-03'))
        with self.assertRaises(ValueError) as ctx:
            check_input(d)
        self.assertRegex(str(ctx.exception), r'4000|Högst|interventions')


@unittest.skipUnless(DUMP.exists(), 'Galaxen 28d-dump saknas')
class Galaxen28dPrecheck(unittest.TestCase):
    def test_five_named_staff_has_critical_jour_shortfall(self):
        d = _load()
        d['limits'] = dict(maxOccurrences=4000)
        check_input(d)
        jour = analyze_jour_capacity(d)
        diagnoses = feasibility_precheck(d, jour_payload=jour)
        self.assertTrue(has_critical_precheck(diagnoses))
        self.assertTrue(any(x.get('code') == 'JOUR_CAPACITY_SHORTFALL' for x in diagnoses))
        self.assertTrue(any(x.get('code') == 'INSUFFICIENT_TOTAL_CAPACITY' for x in diagnoses))
        self.assertGreaterEqual(int(jour.get('minimumExternalJourSlots') or 0), 9)
        vacant = d.get('vacantShifts') or d.get('openShifts') or []
        self.assertEqual(len([e for e in d['employees'] if e.get('status') == 'active']), 5)
        self.assertFalse(any(e.get('resourceType') == 'temporary' for e in d['employees']))

    def test_explicit_temporary_can_clear_jour_shortfall_and_reach_cpsat_build(self):
        d = _temps(_load(), 6)
        d['limits'] = dict(maxOccurrences=4000)
        check_input(d)
        jour = analyze_jour_capacity(d)
        diagnoses = feasibility_precheck(d, jour_payload=jour)
        self.assertFalse(
            any(x.get('code') == 'JOUR_CAPACITY_SHORTFALL' and x.get('severity') == 'critical' for x in diagnoses),
            diagnoses,
        )
        self.assertFalse(has_critical_precheck(diagnoses))
        from bb.solver import solve
        built = solve(d, seconds=1, build_only=True, occurrence_encoding='support_z')
        self.assertEqual(built['schedule']['solverStatus'], 'NOT_RUN')
        self.assertGreater(built['modelScope']['candidateShifts'], 0)
        self.assertGreater(built['modelScope']['solverVariables'], 0)
