"""Isolated duty-length experiment; it does not alter a saved Flora run."""
import copy
import unittest

from bb.flora import solve_case, validate_case
from test_flora_method import fixture


def no_break_case(minutes):
    case = fixture()
    case['config']['break_policy'] = 'EXPLICIT_NO_BREAK_SCENARIO'
    case['staff'][0]['target_net'] = minutes
    case['candidates'][0].update(hi=600 + minutes, min_length=minutes, max_length=minutes)
    case['references']['import']['segments'][0]['end'] = 600 + minutes
    return case


def whole_jour_candidate_case():
    case = no_break_case(780)
    case['staff'][0]['sleeping_oncall'] = 'JA'
    case['staff'][0]['target_net'] = 960
    case['candidates'] = []
    parts = [dict(code='Ar',start=540,end=1320),
             dict(code='Jo',start=1320,end=1800),
             dict(code='Ar',start=1800,end=1980)]
    case['whole_duty_candidates'] = [dict(id='whole-night-X',person='employee-X',
                                           start=540,end=1980,parts=parts)]
    case['references']['import']['segments'] = [
        dict(id=f'source-night-{i}',person='employee-X',start=part['start'],end=part['end'],
             code=part['code'],type='SOVANDE_JOUR' if part['code']=='Jo' else 'AKTIVT_ARBETE')
        for i,part in enumerate(parts,1)]
    return case


class NoBreakDutyExperiment(unittest.TestCase):
    def test_four_six_seven_eight_and_thirteen_hour_active_duties(self):
        for hours in (4, 6, 7, 8, 13):
            with self.subTest(hours=hours):
                case = no_break_case(hours * 60)
                result = solve_case(case, seconds=2, workers=1)
                self.assertEqual(result['solver_status'], 'OPTIMAL')
                self.assertEqual(result['validation']['checked_status'], 'PASS')
                self.assertEqual(result['after']['ordinary_net_minutes'], hours * 60)
                self.assertEqual(result['after']['break_minutes'], 0)
                self.assertEqual(result['schedule']['breaks'], [])
                self.assertEqual(result['schedule']['segments'][0]['code'], 'Ar')
                self.assertEqual(result['schedule']['segments'][0]['end'][-6:], '+02:00')
                self.assertEqual(result['time_accounting']['before_break_reference']['kind'],
                                 'EXPLICIT_NO_BREAK_EXPERIMENT')
                self.assertIn('no_break_applicability', {u['rule_id'] for u in result['validation']['unknowns']})

    def test_under_four_or_over_thirteen_hours_is_rejected(self):
        for minutes in (180, 840):
            with self.subTest(minutes=minutes):
                with self.assertRaises(ValueError):
                    solve_case(no_break_case(minutes), seconds=1)

    def test_no_break_scenario_rejects_recorded_source_breaks(self):
        case = no_break_case(480)
        case['references']['import']['breaks'] = [dict(person='employee-X', start=720, end=750)]
        with self.assertRaisesRegex(ValueError, 'referensraster'):
            solve_case(case, seconds=1)

    def test_thirteen_hour_active_limit_does_not_cut_a_whole_jour_duty(self):
        case = no_break_case(780)
        case['staff'][0]['sleeping_oncall'] = 'JA'
        case['staff'][0]['target_net'] = 960
        rows = [
            dict(id='source-night-01', person='employee-X', start=540, end=1320,
                 code='Ar', type='AKTIVT_ARBETE'),
            dict(id='source-night-02', person='employee-X', start=1320, end=1800,
                 code='Jo', type='SOVANDE_JOUR'),
            dict(id='source-night-03', person='employee-X', start=1800, end=1980,
                 code='Ar', type='AKTIVT_ARBETE'),
        ]
        case['references']['import']['segments'] = copy.deepcopy(rows)
        case['fixed_segments'] = copy.deepcopy(rows)
        case['candidates'] = []
        case['needs'] = []
        case['source_needs'] = []
        result = solve_case(case, seconds=2, workers=1)
        self.assertEqual(result['solver_status'], 'OPTIMAL')
        self.assertEqual(result['validation']['checked_status'], 'PASS')
        self.assertEqual(result['after']['ordinary_net_minutes'], 960)
        self.assertEqual(result['after']['jour_minutes'], 480)
        self.assertEqual(result['after']['break_minutes'], 0)
        self.assertFalse(result['schedule']['breaks'])

    def test_new_whole_jour_candidate_is_selected_as_one_pass(self):
        case=whole_jour_candidate_case()
        result=solve_case(case,seconds=2,workers=1)
        self.assertEqual(result['solver_status'],'OPTIMAL')
        self.assertEqual(result['validation']['checked_status'],'PASS')
        self.assertEqual(result['after']['ordinary_net_minutes'],960)
        self.assertEqual(result['after']['jour_minutes'],480)
        self.assertEqual(result['after']['break_minutes'],0)
        self.assertEqual(result['after']['fully_covered_needs'],1)
        self.assertEqual({r['pass_id'] for r in result['schedule']['segments']},
                         {'generated:whole-night-X'})
        self.assertEqual([r['code'] for r in result['schedule']['segments']],['Ar','Jo','Ar'])
        raw=copy.deepcopy(result['raw_solution'])
        raw['segments']=[r for r in raw['segments'] if r['id']!='whole-night-X:2']
        self.assertIn('incomplete_whole_duty_candidate',
                      {v['rule'] for v in validate_case(case,raw)['violations']})

    def test_sick_time_cannot_become_a_whole_duty_candidate(self):
        case=whole_jour_candidate_case()
        case['whole_duty_candidates'][0]['parts'][1]['code']='St'
        with self.assertRaisesRegex(ValueError,'Ar–Jo–Ar'):
            solve_case(case,seconds=1)

    def test_whole_candidate_cannot_overlap_fixed_work(self):
        case=whole_jour_candidate_case()
        case['fixed_segments']=[dict(id='fixed-work',person='employee-X',
                                     code='Ar',start=600,end=660)]
        with self.assertRaisesRegex(ValueError,'överlappar samma persons låsta arbete'):
            solve_case(case,seconds=1)

    def test_active_candidate_cannot_overlap_fixed_work(self):
        case=no_break_case(480)
        case['fixed_segments']=[dict(id='fixed-work',person='employee-X',
                                     code='Ar',start=600,end=660)]
        with self.assertRaisesRegex(ValueError,'Arbetspasskandidat överlappar'):
            solve_case(case,seconds=1)

    def test_whole_candidate_cannot_reuse_source_row_id(self):
        case=whole_jour_candidate_case()
        case['whole_duty_candidates'][0]['id']='source-night-1'
        with self.assertRaisesRegex(ValueError,'krockar med befintligt schemarad-ID'):
            solve_case(case,seconds=1)

    def test_malformed_whole_candidate_is_rejected_cleanly(self):
        case=whole_jour_candidate_case()
        case['whole_duty_candidates'][0]['parts']=None
        with self.assertRaisesRegex(ValueError,'helt 24-timmarspass'):
            solve_case(case,seconds=1)

    def test_whole_candidate_requires_night_jour_and_obeys_rolling_cap(self):
        case=whole_jour_candidate_case()
        case['whole_duty_candidates'][0]['parts']=[
            dict(code='Ar',start=540,end=600),dict(code='Jo',start=600,end=1080),
            dict(code='Ar',start=1080,end=1980)]
        with self.assertRaisesRegex(ValueError,'nattjour'):
            solve_case(case,seconds=1)
        case=whole_jour_candidate_case()
        case['config']['oncall_cap_28d']=300
        result=solve_case(case,seconds=2,workers=1)
        self.assertEqual(result['solver_status'],'INFEASIBLE')
        self.assertFalse(result['schedule']['segments'])

    def test_validator_catches_inserted_break_and_long_active_duty(self):
        case = no_break_case(780)
        result = solve_case(case, seconds=2, workers=1)
        raw = copy.deepcopy(result['raw_solution'])
        raw['breaks'] = [dict(person='employee-X', start=720, end=750)]
        self.assertIn('unexpected_break_in_authorized_without_breaks_test',
                      {v['rule'] for v in validate_case(case, raw)['violations']})
        raw = copy.deepcopy(result['raw_solution'])
        raw['segments'][0]['end'] += 60
        rules = {v['rule'] for v in validate_case(case, raw)['violations']}
        self.assertIn('active_only_duty_over13h', rules)
        self.assertIn('candidate_bounds_or_length', rules)


if __name__ == '__main__':
    unittest.main()
