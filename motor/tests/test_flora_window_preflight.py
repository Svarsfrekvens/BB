"""Integrated window/no-break/sequential checks; no optimization calls."""
import copy
import unittest
from unittest.mock import patch
from bb.flora import check_case
from bb.flora.arithmetic import check_arithmetic
from test_flora_method import fixture

class WindowPreflightTest(unittest.TestCase):
    def setUp(self):
        self.guard=patch('ortools.sat.python.cp_model.CpSolver.solve',side_effect=AssertionError('No solver in preflight'))
        self.guard.start();self.addCleanup(self.guard.stop)

    def setup_case(self,semantics='START_WINDOW',start=620):
        c=fixture();c['config']['break_policy']='EXPLICIT_NO_BREAK_SCENARIO'
        n=c['needs'][0]
        n.update(window_semantics=semantics,source_window_start=600,source_window_end=620,
                 original_window_end=620,domains=[[600,620]],flex=False)
        c['source_needs']=copy.deepcopy(c['needs'])
        s={'segments':[copy.deepcopy(c['references']['import']['segments'][0])], 'breaks':[],
           'placements':[{'id':'need-X','start':start,'assigned_people':['employee-X']}], 'stages':[]}
        return c,s

    def errors(self,c,s):return check_arithmetic(c,s)['summary']['scope_errors']

    def test_independent_start_end_and_full_duration(self):
        c,s=self.setup_case();check_case(c)
        self.assertFalse(any(e['rule']=='need_window' for e in self.errors(c,s)))
        s['placements'][0]['start']=621
        c['needs'][0]['domains']=[[600,621]] # Detect malformed model domains independently.
        self.assertTrue(any(e.get('source')=='source_window_semantics' for e in self.errors(c,s)))

    def test_execution_interval_cannot_hide_overrun(self):
        c,s=self.setup_case('EXECUTION_WINDOW',600)
        self.assertTrue(any(e['rule']=='need_window' for e in self.errors(c,s)))

    def test_explicit_exception_preserves_original_and_is_validated(self):
        c,s=self.setup_case('EXECUTION_WINDOW',603);n=c['needs'][0]
        n.update(source_window_end=720,original_window_end=720,domains=[[600,603]],
                 approved_window_extension={'original_window_end':720,'approved_window_end':723,
                   'decision_id':'synthetic-scoped-decision','decision_source':'Synthetic source'})
        c['source_needs']=copy.deepcopy(c['needs'])
        self.assertFalse(any(e['rule']=='need_window' for e in self.errors(c,s)))
        self.assertEqual(n['source_window_end'],720)
        n['approved_window_extension']['original_window_end']=719
        self.assertTrue(any(e.get('source')=='invalid_window_extension' for e in self.errors(c,s)))

    def test_sequential_rule_survives_window_integration(self):
        c,s=self.setup_case()
        c['config'].update(sequential_individual_customers=True,non_individual_customer_ids=[])
        second=copy.deepcopy(c['needs'][0]);second.update(id='need-Y',customer='C2')
        c['needs'].append(second);c['source_needs']=copy.deepcopy(c['needs'])
        s['placements'].append({'id':'need-Y','start':620,'assigned_people':['employee-X']})
        check_case(c)
        self.assertTrue(any(e['rule']=='same_person_different_customers' for e in self.errors(c,s)))

    def test_no_break_shift_limits_remain(self):
        c,_=self.setup_case()
        for minutes in (240,360,420,480,780):
            c['candidates'][0].update(lo=480,hi=480+minutes,min_length=minutes,max_length=minutes)
            check_case(c)
        c['candidates'][0].update(lo=480,hi=1261,min_length=781,max_length=781)
        with self.assertRaisesRegex(ValueError,'4–13'):check_case(c)
