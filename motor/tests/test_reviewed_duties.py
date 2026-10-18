"""Synthetic regression for reviewed whole-duty IDs and source activity names."""
from copy import deepcopy
import unittest
from bb.flora_import import prepare_case, FloraImportError
from bb.flora import solve_case, validate_case
from test_flora_import import sample
from test_rule_policy import night_case


class ReviewedDutyTests(unittest.TestCase):
    def test_activity_mapping_preserves_source_without_guessing_function(self):
        raw, p = sample(); r = raw['schedule_segments'][1]
        r.update(category='ARBETE_BRUTTO', sequence_id='whole', segment_type='UNKNOWN')
        d = p['segment_decisions'][r['segment_id']]; d['expected']['category'] = 'ARBETE_BRUTTO'
        d.update(model_type='AKTIVT_ARBETE', whole_duty_id='whole')
        before = deepcopy((raw, p)); case = prepare_case(raw, p)
        imported = next(x for x in case['references']['import']['segments'] if x['id'] == r['segment_id'])
        self.assertEqual(imported['type'], 'AKTIVT_ARBETE')
        self.assertEqual(imported['whole_duty_id'], 'whole')
        self.assertEqual((raw, p), before)
        self.assertEqual(case['import_provenance']['upload']['schedule_segments'][1]['segment_type'], 'UNKNOWN')
        d['model_type'] = 'SOVANDE_JOUR'
        with self.assertRaisesRegex(FloraImportError, 'modelltypen'): prepare_case(raw, p)

    def test_changed_sequence_or_disconnected_group_requires_review(self):
        raw, p = sample(); r = raw['schedule_segments'][1]; r['sequence_id'] = 'whole'
        p['segment_decisions'][r['segment_id']]['whole_duty_id'] = 'whole'
        second = deepcopy(r)
        second.update(segment_id='unrelated-suffix-portion', start='2027-01-29T13:00', end='2027-01-29T14:00')
        raw['schedule_segments'].append(second)
        p['segment_decisions'][second['segment_id']] = deepcopy(p['segment_decisions'][r['segment_id']])
        with self.assertRaisesRegex(FloraImportError, 'sammanhängande'): prepare_case(raw, p)
        second.update(start=r['end']); prepare_case(raw, p)
        second['sequence_id'] = 'different'
        with self.assertRaisesRegex(FloraImportError, 'källkoppling'): prepare_case(raw, p)

    def test_solver_and_independent_validator_use_reviewed_whole_id_not_suffix(self):
        case = night_case()
        for i, row in enumerate(case['fixed_segments']):
            row['id'] = ['source-A1', 'source-gap-J-extra', 'source-morning-A-extra'][i]
            row['whole_duty_id'] = 'reviewed-whole'
        case['references']['import']['segments'] = deepcopy(case['fixed_segments'])
        result = solve_case(case, seconds=1, workers=1)
        self.assertIn('segments', result['raw_solution'])
        self.assertNotIn('whole_occasion_under4h', {x['rule'] for x in result['validation']['violations']})
        self.assertEqual(result['validation']['checked_status'], 'PASS')
        # A solver label cannot hide a shorter occasion in the reviewed source.
        shorter = deepcopy(case)
        for row in shorter['references']['import']['segments']: row.pop('whole_duty_id')
        for row in result['raw_solution']['segments']: row['whole_duty_id'] = 'forged'
        checked = validate_case(shorter, result)
        self.assertIn('whole_occasion_under4h', {x['rule'] for x in checked['violations']})
