"""Shared implementation, distinct business choices and real solver enforcement."""
from copy import deepcopy
import unittest

from bb.flora import solve_case, validate_case
from bb.flora_import import FloraImportError, prepare_case
from bb.rule_policy import VERSION, resolve_policy, shared_principles
from test_flora_import import sample
from test_flora_method import fixture


def decision(minutes):
    return dict(max_whole_duty_minutes=minutes,source='Explicit synthetic planning decision',confirmed_at='2026-10-18')


def night_case(start=540,reassignable=False):
    case=fixture();case['staff'][0].update(ordinary=False,target_net=0,sleeping_oncall='JA')
    case['candidates']=[];case['needs']=[];case['source_needs']=[]
    rows=[dict(id='night-01',person='employee-X',start=start,end=start+900,code='Ar',type='AKTIVT_ARBETE'),
          dict(id='night-02',person='employee-X',start=start+900,end=start+1290,code='Jo',type='SOVANDE_JOUR'),
          dict(id='night-03',person='employee-X',start=start+1290,end=start+1440,code='Ar',type='AKTIVT_ARBETE')]
    case['fixed_segments']=deepcopy(rows);case['references']['import']['segments']=deepcopy(rows)
    if reassignable:
        case['reassignable_temporary_units']=[dict(id='night',original_person='employee-X',start=start,end=start+1440,
            rows=deepcopy(rows),segment_ids=[r['id'] for r in rows],ar_p2_minutes=1050)]
    return case


class PolicyImportTests(unittest.TestCase):
    def test_same_method_three_businesses_keep_independent_limits(self):
        manifests=[]
        for business,limit in [('flora',1200),('galaxen',1440),('vintergatan',None)]:
            raw,profile=sample();profile['business_id']=business;profile['data_use']='development'
            if limit:profile['planning_limits']=decision(limit)
            before=deepcopy((raw,profile))
            case=prepare_case(raw,profile)
            self.assertEqual((raw,profile),before)
            self.assertEqual(case['config'].get('max_whole_duty_minutes'),limit)
            policy=case['rule_policy'];self.assertEqual(policy['version'],VERSION)
            self.assertEqual(policy['business_id'],business)
            self.assertFalse(policy['other_business_decisions_inherited'])
            manifests.append(policy)
        self.assertEqual(len({p['fingerprint'] for p in manifests}),3)
        self.assertEqual(len({tuple(p['shared_principle_ids']) for p in manifests}),1)

    def test_explicit_scenario_tightens_without_changing_profile(self):
        raw,profile=sample();profile['planning_limits']=decision(1440)
        scenario={'workspace':{'unit_rules':{'planning_limits':decision(1200)}}}
        before=deepcopy((raw,profile,scenario))
        case=prepare_case(raw,profile,scenario)
        self.assertEqual(case['config']['max_whole_duty_minutes'],1200)
        self.assertEqual((raw,profile,scenario),before)
        profile['planning_limits']=decision(1200);scenario['workspace']['unit_rules']['planning_limits']=decision(1440)
        with self.assertRaisesRegex(FloraImportError,'höja'):prepare_case(raw,profile,scenario)

    def test_invalid_or_undocumented_limits_fail_explicitly(self):
        for value in (None,{},True,{'max_whole_duty_minutes':1440},decision(True),decision(1500),
                      dict(decision(1200),confirmed_at='2026-02-31'),dict(decision(1200),source='')):
            with self.subTest(value=value):
                raw,profile=sample()
                with self.assertRaises(FloraImportError):
                    prepare_case(raw,profile,{'workspace':{'unit_rules':{'planning_limits':value}}})
        raw,profile=sample();profile['config']['max_whole_duty_minutes']=1200
        with self.assertRaises(FloraImportError):prepare_case(raw,profile)

    def test_legacy_profile_has_no_invented_20_or_24h_choice(self):
        raw,profile=sample();case=prepare_case(raw,profile)
        self.assertEqual(case['rule_policy']['planning_limits']['status'],'NOT_SELECTED')
        self.assertNotIn('max_whole_duty_minutes',case['config'])
        self.assertFalse(shared_principles()['legal_approval'])


class PolicyCalculationTests(unittest.TestCase):
    def test_24h_duty_rejected_by_20h_solver_and_independent_validator(self):
        for movable in (False,True):
            with self.subTest(reassignable=movable):
                case=night_case(reassignable=movable);case['config']['max_whole_duty_minutes']=1440
                before=deepcopy(case)
                result=solve_case(case,seconds=1,workers=1)
                self.assertEqual(case,before)
                self.assertIn('segments',result['raw_solution'])
                self.assertEqual(next(r for r in result['validation']['rules'] if r['rule_id']=='whole_duty_maximum')['status'],'PASS')
                case['config']['max_whole_duty_minutes']=1200
                checked=validate_case(case,result)
                self.assertIn('whole_duty_over_selected_limit',{e['rule'] for e in checked['violations']})
                impossible=solve_case(case,seconds=1,workers=1)
                self.assertEqual(impossible['solver_status'],'INFEASIBLE')
                self.assertNotIn('segments',impossible['raw_solution'])

    def test_incoming_historical_duty_not_trimmed_to_selected_limit(self):
        case=night_case(start=-900);case['config']['max_whole_duty_minutes']=1200
        result=solve_case(case,seconds=1,workers=1)
        self.assertEqual(len(result['raw_solution']['segments']),3)
        self.assertNotIn('whole_duty_over_selected_limit',{r['rule'] for r in result['validation']['violations']})

    def test_resolved_policy_exported_without_mutating_case(self):
        case=fixture()
        case['rule_policy']=resolve_policy({'profile_id':'test-reviewed'},
            {'workspace':{'unit_rules':{'planning_limits':decision(1200)}}},case['config'],None)
        before=deepcopy(case)
        result=solve_case(case,seconds=1,workers=1)
        self.assertEqual(result['rule_policy'],case['rule_policy'])
        self.assertEqual(case,before)
        self.assertFalse(result['business_schedule_approved'])
        self.assertEqual(result['validation']['overall'],'UNKNOWN')
