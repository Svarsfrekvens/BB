import importlib.util
import unittest
from test_rules import fixture, cover_f01
from bb.domain import (
    build_duty_occasion, duty_occasions, iter_mergeable_chains, occasion_exceeds_max_span,
    required_rest_after_minutes, span,
)
from bb.validate import validate


def k7(sid='k7', day='2026-09-07'):
    return dict(id=sid, employeeId='e1', date=day, start='15:00', end='21:00', type='evening', skills=['Omsorg'], breaks=[])


def jour(sid='j', day='2026-09-07'):
    return dict(id=sid, employeeId='e1', date=day, start='23:00', end='06:30', type='jour', skills=[], breaks=[])


def p2(sid='p2', day='2026-09-08'):
    return dict(id=sid, employeeId='e1', date=day, start='06:30', end='10:00', type='day', skills=['Omsorg'], breaks=[])


def p5(sid='p5', day='2026-09-08'):
    return dict(id=sid, employeeId='e1', date=day, start='06:30', end='15:00', type='day', skills=['Omsorg'], breaks=[])


def next_short(sid='n', day='2026-09-08'):
    return dict(id=sid, employeeId='e1', date=day, start='16:00', end='20:00', type='evening', skills=['Omsorg'], breaks=[])


def rules_of(d=None):
    if d is None:
        d, _ = fixture()
    return d['rules']


def as_items(shifts):
    rows = []
    for s in shifts:
        a, b = span(s)
        rows.append(dict(shift=s, a=a, b=b, id=s['id']))
    return rows


class OccasionSemantics(unittest.TestCase):
    def setUp(self):
        d, s = fixture()
        d['interventions'] = []
        s['assignments'] = []
        s['shifts'] = []
        d['rules']['nightFloor'] = 0
        d['rules']['maxWeeklyHours'] = 60
        d['employees'][0]['jour'] = True
        d['employees'][0]['night'] = False
        self.d, self.s = d, s

    def test_occ_a_19h_allowed(self):
        segs = [k7(), jour(), p2()]
        self.assertEqual(len(duty_occasions(segs)), 1)
        occ = build_duty_occasion(segs, self.d['rules'])
        self.assertEqual(occ['spanMinutes'] / 60, 19)
        self.assertFalse(occasion_exceeds_max_span(segs, self.d['rules']))
        self.s['shifts'] = segs
        r = validate(self.d, self.s)
        self.assertNotIn('COMPOSITE_LENGTH', {e['rule'] for e in r['errors']})
        self.assertTrue(r['valid'])

    def test_occ_b_24h_forbidden(self):
        segs = [k7(), jour(), p5()]
        self.assertEqual(len(duty_occasions(segs)), 1)
        self.assertEqual(build_duty_occasion(segs, self.d['rules'])['spanMinutes'] / 60, 24)
        self.assertTrue(occasion_exceeds_max_span(segs, self.d['rules']))
        self.s['shifts'] = segs
        r = validate(self.d, self.s)
        self.assertIn('COMPOSITE_LENGTH', {e['rule'] for e in r['errors']})
        self.assertFalse(r['valid'])

    def test_occ_c_competing_templates_enumerated(self):
        items = as_items([k7(), jour(), p2(), p5()])
        spans = []
        for chain in iter_mergeable_chains(items):
            ids = [c['shift']['id'] for c in chain]
            if set(ids) >= {'k7', 'j'} and len(ids) == 3:
                spans.append((tuple(ids), occasion_exceeds_max_span([c['shift'] for c in chain], self.d['rules'])))
        overlong = {ids for ids, bad in spans if bad}
        legal = {ids for ids, bad in spans if not bad}
        self.assertIn(('k7', 'j', 'p5'), overlong)
        self.assertIn(('k7', 'j', 'p2'), legal)
        self.assertNotIn(('k7', 'j', 'p2'), overlong)

    def test_occ_d_template_order_does_not_change_chains(self):
        chains_a = {tuple(c['shift']['id'] for c in chain) for chain in iter_mergeable_chains(as_items([k7(), jour(), p2(), p5()]))}
        chains_b = {tuple(c['shift']['id'] for c in chain) for chain in iter_mergeable_chains(as_items([p5(), p2(), jour(), k7()]))}
        self.assertEqual(chains_a, chains_b)
        self.assertIn(('k7', 'j', 'p2'), chains_a)
        self.assertIn(('k7', 'j', 'p5'), chains_a)

    def test_rest_a_same_required_rest(self):
        long = [k7(), jour(), p5()]
        owed = required_rest_after_minutes(long, self.d['rules'])
        self.assertEqual(owed, 24 * 60)
        self.s['shifts'] = long
        groups = duty_occasions(self.s['shifts'])
        self.assertEqual(required_rest_after_minutes(groups[0], self.d['rules']), owed)

    def test_rest_c_boundary_only_is_history(self):
        self.d['boundaryShifts'] = [
            k7(sid='be', day='2026-09-05'),
            jour(sid='bj', day='2026-09-05'),
            p2(sid='bm', day='2026-09-06'),
            next_short(sid='bn', day='2026-09-06'),
        ]
        r = validate(self.d, self.s)
        self.assertTrue(r['valid'])
        self.assertNotIn('COMP_REST', {e['rule'] for e in r['errors']})
        self.assertIn('COMP_REST', {w.get('sourceRule') for w in r['warnings'] if w.get('rule') == 'BOUNDARY_HISTORY'})

    def test_rest_d_boundary_plus_candidate_is_hard(self):
        self.d['boundaryShifts'] = [
            k7(sid='be', day='2026-09-05'),
            jour(sid='bj', day='2026-09-05'),
            p2(sid='bm', day='2026-09-06'),
        ]
        self.s['shifts'] = [next_short(sid='cn', day='2026-09-06')]
        r = validate(self.d, self.s)
        self.assertIn('COMP_REST', {e['rule'] for e in r['errors']})
        self.assertFalse(r['valid'])


@unittest.skipUnless(importlib.util.find_spec('ortools'), 'OR-Tools saknas: solver-tester är INTE körda')
class OccasionSolver(unittest.TestCase):
    def forced_status(self, shifts, rules, require=None, order=None):
        from ortools.sat.python import cp_model
        from bb.domain import paid as paid_work
        from bb.solver import _as_bool, forbid_compensatory_rest, forbid_overlong_occasions
        model = cp_model.CpModel()
        rows = list(order or shifts)
        require = set(require or [s['id'] for s in shifts])
        items = []
        for s in rows:
            a, b = span(s)
            x = model.new_bool_var(s['id'])
            if s['id'] in require:
                model.add(x == 1)
            items.append(dict(shift=s, a=a, b=b, work=paid_work(s), x=x))
        lit = lambda var, name: _as_bool(model, var, name)
        forbid_overlong_occasions(model, items, rules, lit, prefix='t')
        forbid_compensatory_rest(model, items, rules, lit, prefix='r')
        sv = cp_model.CpSolver()
        return sv.status_name(sv.solve(model))

    def test_occ_a_solver_allows_19h(self):
        d, _ = fixture()
        segs = [k7(), jour(), p2()]
        self.assertIn(self.forced_status(segs, d['rules']), ['OPTIMAL', 'FEASIBLE'])

    def test_occ_b_solver_forbids_24h(self):
        d, _ = fixture()
        segs = [k7(), jour(), p5()]
        self.assertEqual(self.forced_status(segs, d['rules']), 'INFEASIBLE')

    def test_occ_c_solver_allows_short_forbids_long_with_both_templates(self):
        d, _ = fixture()
        both = [k7(), jour(), p2(), p5()]
        self.assertIn(self.forced_status(both, d['rules'], require={'k7', 'j', 'p2'}), ['OPTIMAL', 'FEASIBLE'])
        self.assertEqual(self.forced_status(both, d['rules'], require={'k7', 'j', 'p5'}), 'INFEASIBLE')

    def test_occ_d_solver_order_independent(self):
        d, _ = fixture()
        both = [k7(), jour(), p2(), p5()]
        rev = [p5(), p2(), jour(), k7()]
        self.assertEqual(
            self.forced_status(both, d['rules'], require={'k7', 'j', 'p2'}, order=rev),
            self.forced_status(both, d['rules'], require={'k7', 'j', 'p2'}, order=both),
        )
        self.assertEqual(self.forced_status(both, d['rules'], require={'k7', 'j', 'p5'}, order=rev), 'INFEASIBLE')
        self.assertEqual(self.forced_status(both, d['rules'], require={'k7', 'j', 'p5'}, order=both), 'INFEASIBLE')

    def test_rest_a_solver_rest_matches_validator(self):
        d, _ = fixture()
        long = [k7(), jour(), p5()]
        owed = required_rest_after_minutes(long, d['rules'])
        self.assertEqual(owed, 24 * 60)
        self.assertEqual(self.forced_status(long, d['rules']), 'INFEASIBLE')

    def test_rest_b_solver_forbids_next_inside_rest(self):
        d, _ = fixture()
        segs = [k7(), jour(), p2(), next_short()]
        self.assertEqual(required_rest_after_minutes([k7(), jour(), p2()], d['rules']), 19 * 60)
        self.assertEqual(self.forced_status(segs, d['rules']), 'INFEASIBLE')
        self.assertIn(self.forced_status(segs, d['rules'], require={'k7', 'j', 'p2'}), ['OPTIMAL', 'FEASIBLE'])

    def test_rest_c_boundary_only_feasible(self):
        from bb.solver import solve
        d, _ = fixture()
        d['interventions'] = []
        d['rules']['nightFloor'] = 0
        d['employees'][0]['jour'] = True
        cover_f01(d)
        d['boundaryShifts'] = [
            k7(sid='be', day='2026-09-05'),
            jour(sid='bj', day='2026-09-05'),
            p2(sid='bm', day='2026-09-06'),
            next_short(sid='bn', day='2026-09-06'),
        ]
        r = solve(d, 8)
        self.assertIn(r['schedule']['solverStatus'], ['OPTIMAL', 'FEASIBLE'])
        val = r.get('validation') or validate(d, r['schedule'])
        self.assertTrue(val['valid'])
        self.assertIn('COMP_REST', {w.get('sourceRule') for w in val['warnings'] if w.get('rule') == 'BOUNDARY_HISTORY'})
        self.assertNotIn('COMP_REST', {e['rule'] for e in val['errors']})

    def test_rest_d_boundary_plus_candidate_forbidden(self):
        d, _ = fixture()
        bound = [
            k7(sid='be', day='2026-09-05'),
            jour(sid='bj', day='2026-09-05'),
            p2(sid='bm', day='2026-09-06'),
        ]
        cand = next_short(sid='cn', day='2026-09-06')
        from ortools.sat.python import cp_model
        from bb.domain import paid as paid_work, is_fixed_choice
        from bb.solver import _as_bool, forbid_compensatory_rest, forbid_overlong_occasions
        model = cp_model.CpModel()
        items = []
        for s in bound:
            a, b = span(s)
            items.append(dict(shift=s, a=a, b=b, work=paid_work(s), x=1))
        a, b = span(cand)
        x = model.new_bool_var('cn')
        model.add(x == 1)
        items.append(dict(shift=cand, a=a, b=b, work=paid_work(cand), x=x))
        lit = lambda var, name: _as_bool(model, var, name)
        forbid_overlong_occasions(model, items, d['rules'], lit, prefix='t')
        forbid_compensatory_rest(model, items, d['rules'], lit, prefix='r')
        sv = cp_model.CpSolver()
        self.assertEqual(sv.status_name(sv.solve(model)), 'INFEASIBLE')
        self.assertTrue(is_fixed_choice(1))
