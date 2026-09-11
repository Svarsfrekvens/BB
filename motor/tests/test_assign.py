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
        d['interventions'][0].update(start='22:00', latestEnd='06:00', minutes=480)
        d['employees'][0]['night'] = False
        o = occurrences(d)[0]
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))

    def test_hard_allowed_types(self):
        d, _ = fixture()
        d['employees'][0]['constraints'] = dict(hard=dict(allowedTypes=['night']))
        o = occurrences(d)[0]
        self.assertFalse(occurrence_employee_ok(d['employees'][0], o, d))

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
