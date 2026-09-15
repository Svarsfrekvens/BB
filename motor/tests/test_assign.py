import unittest
from test_rules import fixture
from bb.assign import occurrence_employee_ok, prune_duplicate_cover_windows, support_options_for_occurrence
from bb.domain import occurrences, span, paid
from bb.precheck import employee_available


def _cand(sid, eid, day, start, end, typ='day'):
    s = dict(id=sid, employeeId=eid, date=day, start=start, end=end, type=typ, skills=['Omsorg'], breaks=[])
    a, b = span(s)
    return dict(shift=s, a=a, b=b, work=paid(s), x=0)


class SupportPruning(unittest.TestCase):
    def test_skill_filter(self):
        d, _ = fixture()
        d['interventions'][0]['skills'] = ['Läkemedel']
        o = occurrences(d)[0]
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))

    def test_customer_block(self):
        d, _ = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(forbiddenCustomerIds=['c1']))
        o = occurrences(d)[0]
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))

    def test_absence_blocks(self):
        d, _ = fixture()
        d['absences'] = [dict(id='a', employeeId='e1', start='2026-09-07', end='2026-09-07')]
        o = occurrences(d)[0]
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))
        wa, wb = o['earliest'], o['latest'] + o['task']['minutes']
        self.assertFalse(employee_available(d['employees'][0], o['date'], wa, wb, d))

    def test_night_requires_eligibility(self):
        d, _ = fixture()
        d['interventions'][0].update(start='22:00', latestEnd='06:00', minutes=480, type='fixed')
        d['employees'][0]['night'] = False
        o = occurrences(d)[0]
        self.assertTrue(occurrence_employee_ok(d['employees'][0], o, d))
        night = _cand('n1', 'e1', o['date'], '21:00', '07:30', 'night')
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d, shift=night['shift']))

    def test_hard_allowed_types(self):
        d, _ = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(allowedTypes=['night']))
        o = occurrences(d)[0]
        day = _cand('d1', 'e1', o['date'], '06:00', '14:00', 'day')
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d, shift=day['shift']))

    def test_jour_only_is_not_daytime_capacity_or_ar_support(self):
        d, _ = fixture()
        d['employees'][0].update(jour=True, night=False)
        d['employees'][0]['constraints'] = dict(hard=dict(allowedTypes=['jour']))
        o = occurrences(d)[0]
        wa, wb = o['earliest'], o['latest'] + o['task']['minutes']
        self.assertFalse(employee_available(d['employees'][0], o['date'], wa, wb, d))
        self.assertTrue(employee_available(d['employees'][0], o['date'], wa, wb, d, for_jour=True))
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))
        day = _cand('d1', 'e1', o['date'], '06:00', '14:00', 'day')
        packed = support_options_for_occurrence(o, d['employees'], {'e1': [day]}, d, 0)
        self.assertEqual(packed['after'], 0)
        self.assertEqual(packed['per_emp'], [])
        jour = _cand('j1', 'e1', o['date'], '23:00', '06:30', 'jour')
        self.assertTrue(occurrence_employee_ok(d['employees'][0], o, d, shift=jour['shift']))

    def test_no_variable_for_blocked_employee(self):
        d, _ = fixture()
        d['employees'].append({**d['employees'][0], 'id': 'e2', 'code': 'M02',
                               'constraints': dict(hard=dict(forbiddenCustomerIds=['c1']))})
        o = occurrences(d)[0]
        c1 = _cand('s1', 'e1', '2026-09-07', '06:00', '14:00')
        c2 = _cand('s2', 'e2', '2026-09-07', '06:00', '14:00')
        packed = support_options_for_occurrence(o, d['employees'], {'e1': [c1], 'e2': [c2]}, d, 0)
        ids = [e['id'] for e, _ in packed['per_emp']]
        self.assertEqual(ids, ['e1'])
        self.assertGreater(packed['before'], packed['after'])

    def test_dominance_only_same_shift_window(self):
        a = _cand('short', 'e1', '2026-09-07', '08:00', '12:00')
        b = _cand('long', 'e1', '2026-09-07', '07:00', '16:00')
        kept = prune_duplicate_cover_windows([(a, 1, 2), (b, 1, 2), (a, 1, 2)])
        ids = [c['shift']['id'] for c, _, _ in kept]
        self.assertEqual(ids, ['short', 'long'])


class GeneratedShiftPruning(unittest.TestCase):
    def test_short_generated_without_capacity_is_dropped(self):
        from bb.assign import prune_unusable_generated_templates
        from bb.generate import generate_shift_templates, merge_templates
        d, _ = fixture()
        d['planningMode'] = 'generateFromNeeds'
        d['employees'][0]['profiles'] = ['D']
        d['interventions'][0].update(start='08:00', latestEnd='11:00', minutes=180)
        d['rules']['withinPassMinutesPerShift'] = 30
        d['templates'] = [dict(id='D', name='Dag', start='07:00', end='16:00', type='day', skills=['Omsorg'], breaks=[],
                               dates=['2026-09-07'])]
        raw = merge_templates(d['templates'], generate_shift_templates(d))
        pruned, stats = prune_unusable_generated_templates(d, raw)
        gen_after = [t for t in pruned if t.get('generated')]
        self.assertGreater(stats['generatedShiftTemplatesBeforePruning'], stats['generatedShiftTemplatesAfterPruning'])
        self.assertTrue(any(t['id'] == 'D' for t in pruned))
        self.assertFalse(any(t.get('start') == '08:00' and t.get('end') == '11:00' for t in gen_after))

    def test_short_that_can_cover_is_kept(self):
        from bb.assign import prune_unusable_generated_templates
        from bb.generate import generate_shift_templates
        d, _ = fixture()
        d['planningMode'] = 'generateFromNeeds'
        d['employees'][0]['profiles'] = []
        d['templates'] = []
        d['rules']['withinPassMinutesPerShift'] = 0
        raw = generate_shift_templates(d)
        pruned, _ = prune_unusable_generated_templates(d, raw)
        self.assertTrue(any(t['start'] == '09:00' and t['end'] == '10:00' for t in pruned))

    def test_night_generated_is_not_pruned(self):
        from bb.assign import prune_unusable_generated_templates
        from bb.generate import generate_shift_templates
        from test_generate_from_needs import gen_base, task
        d, _ = gen_base()
        d['interventions'] = [task('n1', '22:00', 480)]
        raw = generate_shift_templates(d)
        self.assertTrue(any(t['type'] == 'night' for t in raw))
        pruned, _ = prune_unusable_generated_templates(d, raw)
        self.assertTrue(any(t['type'] == 'night' for t in pruned))


def _occ(d, start, latest, minutes, typ='flexible'):
    d['interventions'][0].update(start=start, latestEnd=latest, minutes=minutes, type=typ)
    d['employees'][0]['night'] = False
    d['rules']['nightFloor'] = 0
    return occurrences(d)[0]


class AssignNightSemantics(unittest.TestCase):
    def packed(self, o, d, cands):
        by = {}
        for c in cands:
            by.setdefault(c['shift']['employeeId'], []).append(c)
        return support_options_for_occurrence(o, d['employees'], by, d, 0)

    def test_assign_night_a_evening_after_22_without_night_flag(self):
        d, _ = fixture()
        o = _occ(d, '22:15', '22:30', 15, 'fixed')
        eve = _cand('e1s', 'e1', o['date'], '15:00', '23:00', 'evening')
        packed = self.packed(o, d, [eve])
        self.assertGreater(packed['after'], 0)
        self.assertEqual([e['id'] for e, _ in packed['per_emp']], ['e1'])

    def test_assign_night_b_night_type_requires_flag(self):
        d, _ = fixture()
        o = _occ(d, '22:15', '22:30', 15, 'fixed')
        night = _cand('n1', 'e1', o['date'], '21:00', '07:30', 'night')
        packed = self.packed(o, d, [night])
        self.assertEqual(packed['after'], 0)
        self.assertEqual(packed['per_emp'], [])
        d['employees'][0]['night'] = True
        packed_ok = self.packed(o, d, [night])
        self.assertGreater(packed_ok['after'], 0)

    def test_grid_infeasible_cover_window_is_dropped(self):
        d, _ = fixture()
        d['rules']['flexibilityStep'] = 15
        o = _occ(d, '08:07', '08:22', 15, 'flexible')
        short = _cand('s', 'e1', o['date'], '08:00', '08:20')
        packed = self.packed(o, d, [short])
        self.assertEqual(packed['after'], 0)
        long = _cand('l', 'e1', o['date'], '08:00', '09:00')
        packed_ok = self.packed(o, d, [long])
        self.assertGreater(packed_ok['after'], 0)

    def test_assign_night_c_flexible_window_crossing_22(self):
        d, _ = fixture()
        o = _occ(d, '21:30', '22:30', 5, 'flexible')
        eve = _cand('e1s', 'e1', o['date'], '15:00', '23:00', 'evening')
        packed = self.packed(o, d, [eve])
        self.assertGreater(packed['before'], 0)
        self.assertGreater(packed['after'], 0)
        self.assertTrue(occurrence_employee_ok(d['employees'][0], o, d, shift=eve['shift']))

    def test_assign_night_d_jour_is_not_awake_night_or_paid_cover(self):
        d, _ = fixture()
        d['employees'][0]['jour'] = True
        o = _occ(d, '23:00', '06:30', 30, 'fixed')
        jour = _cand('j1', 'e1', o['date'], '23:00', '06:30', 'jour')
        self.assertTrue(occurrence_employee_ok(d['employees'][0], o, d, shift=jour['shift']))
        packed = self.packed(o, d, [jour])
        self.assertEqual(packed['after'], 0)
        self.assertEqual(jour['work'], [])

    def test_assign_night_e_night_false_still_no_night_support(self):
        d, _ = fixture()
        o = _occ(d, '21:00', '07:30', 60, 'fixed')
        night = _cand('n1', 'e1', o['date'], '21:00', '07:30', 'night')
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d, shift=night['shift']))
        packed = self.packed(o, d, [night])
        self.assertEqual(packed['after'], 0)

    def test_assign_night_f_window_edges_do_not_change_evening_rule(self):
        d, _ = fixture()
        o = _occ(d, '21:30', '22:30', 5, 'flexible')
        eve = _cand('e1s', 'e1', o['date'], '15:00', '23:00', 'evening')
        a = self.packed(o, d, [eve])
        o2 = _occ(d, '22:00', '22:30', 5, 'flexible')
        b = self.packed(o2, d, [eve])
        self.assertGreater(a['after'], 0)
        self.assertGreater(b['after'], 0)
        rev = self.packed(o, d, list(reversed([eve, eve])))
        self.assertEqual(a['after'] > 0, rev['after'] > 0)

