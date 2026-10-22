"""The person-bound scenario cannot cover two customers with one worker at once."""

import copy
import unittest

from bb.flora import solve_case, validate_case
from test_flora_method import fixture


def case_for(customers=('C1', 'C2'), two_workers=False):
    case = fixture()
    case['config']['break_policy'] = 'EXPLICIT_NO_BREAK_SCENARIO'
    case['config']['sequential_individual_customers'] = True
    case['config']['non_individual_customer_ids'] = []
    case['needs'][0]['customer'] = customers[0]
    second = copy.deepcopy(case['needs'][0])
    second.update(id='need-Y', source_row='source-Y', customer=customers[1])
    case['needs'].append(second)
    case['source_needs'] = copy.deepcopy(case['needs'])
    if two_workers:
        worker = copy.deepcopy(case['staff'][0])
        worker.update(id='employee-Y', name='Second', ordinary=False, target_net=0)
        case['staff'].append(worker)
        candidate = copy.deepcopy(case['candidates'][0])
        candidate.update(id='candidate-Y', person='employee-Y')
        case['candidates'].append(candidate)
        case['config']['max_staff_on_duty'] = 2
    return case


class SequentialCustomerTest(unittest.TestCase):
    def test_one_worker_cannot_cover_two_customers_at_same_time(self):
        result = solve_case(case_for(), seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 1)
        self.assertEqual(len(result['schedule']['interventions']), 1)
        self.assertEqual(next(r for r in result['validation']['rules']
                              if r['rule_id'] == 'sequential_individual_customers')['status'], 'PASS')

    def test_two_workers_can_cover_two_customers(self):
        case = case_for(two_workers=True)
        result = solve_case(case, seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 2)
        self.assertEqual(len({row['person_id'] for row in result['schedule']['interventions']}), 2)
        self.assertEqual(result['validation']['checked_status'], 'PASS')

        tampered = copy.deepcopy(result['raw_solution'])
        for placement in tampered['placements']:
            placement['assigned_people'] = ['employee-X']
        validation = validate_case(case, tampered)
        self.assertIn('same_person_different_customers',
                      {row['rule'] for row in validation['violations']})

    def test_same_customer_may_share_a_worker(self):
        result = solve_case(case_for(customers=('C1', 'C1')), seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 2)
        self.assertEqual({row['person_id'] for row in result['schedule']['interventions']},
                         {'uploaded-employee'})

    def test_adjacent_different_customer_tasks_are_allowed(self):
        case = case_for()
        case['needs'][0]['duration'] = 60
        case['needs'][1]['duration'] = 60
        case['needs'][1]['domains'] = [[660,660]]
        case['needs'][1]['original'] = 660
        case['source_needs'] = copy.deepcopy(case['needs'])
        result = solve_case(case, seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 2)
        self.assertEqual(result['validation']['checked_status'], 'PASS')

    def test_nonindividual_group_uses_its_explicit_exception(self):
        case = case_for(customers=('C1','COMMON'))
        case['config']['non_individual_customer_ids'] = ['COMMON']
        result = solve_case(case, seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 2)
        case['needs'][1]['exclusive'] = True
        case['source_needs'] = copy.deepcopy(case['needs'])
        result = solve_case(case, seconds=2, workers=1)
        self.assertEqual(result['after']['fully_covered_needs'], 1)

    def test_missing_assignments_are_rejected(self):
        case = case_for(two_workers=True)
        result = solve_case(case, seconds=2, workers=1)
        tampered = copy.deepcopy(result['raw_solution'])
        tampered['placements'][0].pop('assigned_people')
        validation = validate_case(case, tampered)
        self.assertIn('invalid_person_assignment',
                      {row['rule'] for row in validation['violations']})

    def test_profile_must_name_real_nonindividual_groups(self):
        case = case_for()
        case['config']['non_individual_customer_ids'] = ['not-a-customer']
        with self.assertRaisesRegex(ValueError, 'grupp-ID'):
            solve_case(case, seconds=1, workers=1)
        case['config'].pop('non_individual_customer_ids')
        with self.assertRaisesRegex(ValueError, 'grupp-ID'):
            solve_case(case, seconds=1, workers=1)


if __name__ == '__main__':
    unittest.main()
