"""Exact effective domains are evidence separate from original window semantics."""
import copy
import unittest
from unittest.mock import patch
from bb.flora import _normalize
from test_flora_method import fixture

class PlacementDomainExportTest(unittest.TestCase):
    def test_disjoint_domains_and_source_interval_survive_without_search(self):
        case = fixture()
        case['integration'].update(profile_id='synthetic-profile', profile_sha256='a'*64, input_sha256='b'*64)
        need = case['source_needs'][0]
        need.update(domains=[[480, 490], [600, 600]], source_window_start=600,
                    source_window_end=720, window_semantics='EXECUTION_WINDOW')
        case['needs'] = copy.deepcopy(case['source_needs'])
        before = copy.deepcopy(case)
        with patch('ortools.sat.python.cp_model.CpSolver.solve', side_effect=AssertionError('No solver')):
            out = _normalize(case, {'segments': [], 'placements': [], 'stages': []}, {'rules': [], 'unknowns': []})
        self.assertEqual(case, before)
        contract = out['placement_domain_contract']
        self.assertEqual(contract['profile_hash'], 'a'*64)
        self.assertEqual(contract['input_hash'], 'b'*64)
        self.assertEqual(contract['needs'], [{'need_id':'uploaded-need', 'start_intervals':[
            {'earliest':'2026-05-11T08:00+02:00','latest':'2026-05-11T08:10+02:00'},
            {'earliest':'2026-05-11T10:00+02:00','latest':'2026-05-11T10:00+02:00'}]}])
        source = out['need_window_contract']['needs'][0]
        self.assertEqual(source['source_window_start'], '2026-05-11T10:00+02:00')
        self.assertEqual(source['source_window_end'], '2026-05-11T12:00+02:00')
        self.assertEqual(source['window_semantics'], 'EXECUTION_WINDOW')

    def test_missing_profile_identity_never_creates_domain_authority(self):
        out = _normalize(fixture(), {'segments': [], 'placements': [], 'stages': []}, {'rules': [], 'unknowns': []})
        self.assertIsNone(out['placement_domain_contract'])

    def test_effective_breaks_and_targets_replace_stale_scenario_labels(self):
        c=fixture();c['config']['break_policy']='EXPLICIT_NO_BREAK_SCENARIO'
        c['scenario_override']={'breaks':'30 minutes', 'net_targets_minutes':{'employee-X':210}}
        out=_normalize(c, {'segments':[], 'placements':[], 'stages':[]}, {'rules':[], 'unknowns':[]})
        a={x['id']:x for x in out['assumptions']}
        self.assertEqual(a['breaks']['effective_break_minutes'],0)
        self.assertEqual(a['net_targets_minutes']['values'],{'uploaded-employee':240})
        self.assertEqual(c['scenario_override']['breaks'],'30 minutes')
