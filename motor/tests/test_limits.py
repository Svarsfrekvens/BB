import importlib.util
import os
import unittest
from copy import deepcopy

from test_rules import fixture
from bb.domain import check_input
from bb.limits import (
    DEFAULT_MAX_OCCURRENCES,
    effective_max_occurrences,
    reported_limits,
)


class OccurrenceLimitConfig(unittest.TestCase):
    def test_default_occurrence_limit_is_1600(self):
        self.assertEqual(DEFAULT_MAX_OCCURRENCES, 1600)
        self.assertEqual(effective_max_occurrences({}), 1600)
        self.assertEqual(reported_limits()['defaultMaxOccurrences'], 1600)
        self.assertEqual(reported_limits()['source'], 'motor')

    def test_default_rejects_above_1600_without_explicit_limit(self):
        d, _ = fixture()
        base = d['interventions'][0]
        d['interventions'] = [dict(base, id=f't{i}', date='2026-09-07') for i in range(1601)]
        with self.assertRaises(ValueError) as ctx:
            check_input(d)
        self.assertIn('1600', str(ctx.exception))
        d['limits'] = dict(maxOccurrences=2000)
        check_input(d)
        d, _ = fixture()
        d['limits'] = dict(maxOccurrences=2800)
        check_input(d)
        self.assertEqual(effective_max_occurrences(d), 2800)

    def test_invalid_limit_is_fail_closed(self):
        d, _ = fixture()
        for bad in (0, -1, 4001, 1.5, 'abc', True):
            d2 = deepcopy(d)
            d2['limits'] = dict(maxOccurrences=bad)
            with self.assertRaises(ValueError):
                check_input(d2)

    def test_env_override_without_payload(self):
        old = os.environ.get('BB_MAX_OCCURRENCES')
        os.environ['BB_MAX_OCCURRENCES'] = '2000'
        try:
            self.assertEqual(effective_max_occurrences({}), 2000)
        finally:
            if old is None:
                os.environ.pop('BB_MAX_OCCURRENCES', None)
            else:
                os.environ['BB_MAX_OCCURRENCES'] = old

    def test_payload_overrides_env(self):
        old = os.environ.get('BB_MAX_OCCURRENCES')
        os.environ['BB_MAX_OCCURRENCES'] = '2000'
        try:
            self.assertEqual(effective_max_occurrences({'limits': {'maxOccurrences': 2500}}), 2500)
        finally:
            if old is None:
                os.environ.pop('BB_MAX_OCCURRENCES', None)
            else:
                os.environ['BB_MAX_OCCURRENCES'] = old


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas')
class BuildOnly(unittest.TestCase):
    def test_build_only_does_not_solve(self):
        from bb.solver import solve
        d, _ = fixture()
        r = solve(d, 5, build_only=True)
        self.assertEqual(r['schedule']['solverStatus'], 'NOT_RUN')
        self.assertGreater(r['modelScope']['solverVariables'], 0)
        self.assertEqual(r['schedule']['shifts'], [])


@unittest.skipUnless(importlib.util.find_spec('fastapi') and importlib.util.find_spec('httpx'), 'FastAPI/httpx saknas')
class HealthLimits(unittest.TestCase):
    def test_health_reports_server_authoritative_limits(self):
        from fastapi.testclient import TestClient
        from bb.api import app
        r = TestClient(app).get('/api/health')
        self.assertEqual(r.status_code, 200)
        lim = r.json()['limits']
        self.assertEqual(lim['maxOccurrences'], 1600)
        self.assertEqual(lim['source'], 'motor')
        self.assertEqual(lim['defaultMaxSupportCombinations'], 120000)
