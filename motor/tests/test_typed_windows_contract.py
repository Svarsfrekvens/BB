"""Synthetic, solver-free window contract regression. Run via run_typed_windows_checks.py."""
from copy import deepcopy
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch
from bb import need_windows
from bb.flora_import import prepare_case as import_flora
from bb.flora import check_case, validate_case, _normalize
from bb.flora.arithmetic import check_arithmetic
from bb.engine_methods import prepare
from bb.flora_jobs import normalize_request, digest
from bb.availability_import import source_identity
from bb.availability import normalize as normalize_availability, validate_case as validate_availability
from bb.availability.model import build_model
from test_business_engine import business_sample
from test_flora_import import sample as legacy_sample
from availability_fixtures import sample as availability_sample


def flora_fixture(semantics='START_WINDOW', duration=60):
    body, profile = business_sample('synthetic-window')
    # Fictional complete records; shift the fixture away from any business period.
    old = datetime(2026,5,11); delta = datetime(2027,1,4)-old
    def shift(x): return (datetime.fromisoformat(x)+delta).isoformat(timespec='minutes') if 'T' in x else (datetime.fromisoformat(x)+delta).date().isoformat()
    for period in body['input']['metadata']['periods']:
        for k in ('start','end'): period[k]=shift(period[k])
    for r in body['input']['schedule_segments']:
        for k in ('start','end'):r[k]=shift(r[k])
    for r in body['input']['customer_needs']:r['date']=shift(r['date'])
    profile['applicable_periods']=deepcopy(body['input']['metadata']['periods'])
    profile['candidate_windows'][0]['date']=shift(profile['candidate_windows'][0]['date'])
    md=body['input']['metadata'];md.update(dataset_id='SYNTHETIC-WINDOWS',planning_period_id='next',history_period_id='history',source_file_sha256='a'*64)
    n=body['input']['customer_needs'][0]
    n.update(window_start='09:00',window_end='09:20',duration_minutes=duration,personnel_count_candidate=1)
    if semantics is not None:n['window_semantics']=semantics
    return body,profile


def flora_result(case, start=560):
    raw=dict(segments=deepcopy(case['references']['import']['segments']),breaks=[],
             placements=[dict(id=case['needs'][0]['id'],start=start,assigned_people=['person-a'])],
             stages=[dict(status='FEASIBLE')],total_seconds=0)
    validation=validate_case(case,raw)
    result=_normalize(case,raw,validation)
    return raw,result


def availability_fixture(semantics='START_WINDOW'):
    body,profile=availability_sample()
    for row,n in zip(body['input']['customer_needs'],profile['reviewed_case']['needs']):
        if semantics is not None:row['window_semantics']=semantics
        if row['need_id']=='n1':
            row['window_end']='2026-06-01T08:50';row['duration_minutes']=60
            n.update(latest_end=n['earliest']+20,duration=60)
    profile['source_identity']=source_identity(body['input'])
    return body,profile


def availability_result(case, start=None):
    n=case['needs'][0];a=n['earliest']+20 if start is None else start
    raw=dict(solver_status='FEASIBLE',selected_duties=deepcopy(case['candidates']),selected_candidate_ids=[d['id'] for d in case['candidates']],
        assignments=[dict(need_id=n['id'],employee_id='p1',start=a,end=a+n['duration'])],
        unassigned=[dict(need_id='n2',blockers=['PERMISSION_NOT_VERIFIED'],reason='NO_VERIFIED_PERFORMER')],
        search_seconds=0,build_seconds=0,phases=[],coverage_optimal_within_model=False,phase2_status='NOT_RUN',
        week_anchors={},daily_rest_anchors={},unknown_controls=[])
    validation=validate_availability(case,raw)
    return raw,normalize_availability(case,raw,validation)


class TypedWindowTests(unittest.TestCase):
    def test_start_import_normalize_and_actual_export(self):
        body,profile=flora_fixture();before=deepcopy((body,profile))
        request=normalize_request(body);case=prepare(profile,request)
        self.assertEqual(case['needs'][0]['domains'],[[540,560]])
        raw,out=flora_result(case)
        self.assertEqual(out['validation']['overall'],'UNKNOWN')
        self.assertFalse(out['validation']['violations'])
        self.assertEqual(out['schedule']['interventions'][0]['end'],'2027-01-04T10:20+01:00')
        self.assertEqual(out['need_window_contract'],{'version':'bb-need-window/1.0','needs':[
            dict(need_id='source-need',window_semantics='START_WINDOW',source_window_start='2027-01-04T09:00+01:00',source_window_end='2027-01-04T09:20+01:00',duration_minutes=60,personnel_count=1)]})
        self.assertEqual(out['period'],dict(id='next',start='2027-01-04',end='2027-01-31',timezone='Europe/Stockholm'))
        self.assertTrue(out['review_required']);self.assertFalse(out['business_schedule_approved'])
        self.assertEqual((body,profile),before)

    def test_independent_validator_rejects_before_and_after_inclusive_start_window(self):
        body,p=flora_fixture();c=prepare(p,normalize_request(body))
        for start,valid in [(539,False),(540,True),(560,True),(561,False)]:
            with self.subTest(start=start):
                # Corrupt numerical domains deliberately; validator still checks source bounds.
                c['needs'][0]['domains']=[[539,561]]
                raw=dict(segments=deepcopy(c['references']['import']['segments']), breaks=[], placements=[dict(id=c['needs'][0]['id'],start=start)])
                validation=validate_case(c,raw)
                errors=[r for r in validation['violations'] if r['rule']=='need_window']
                self.assertEqual(not errors,valid)
                with self.assertRaises(ValueError):_normalize(c,raw,validation)

    def test_execution_rejects_long_duration_and_end_overrun(self):
        b,p=flora_fixture('EXECUTION_WINDOW')
        with self.assertRaises(ValueError):prepare(p,normalize_request(b))
        b,p=flora_fixture('EXECUTION_WINDOW',10);c=prepare(p,normalize_request(b))
        self.assertEqual(c['needs'][0]['domains'],[[540,550]])
        for start,valid in [(550,True),(551,False)]:
            if valid:
                _,out=flora_result(c,start)
                self.assertFalse(any(r['rule']=='need_window' for r in out['validation']['violations']))
            else:
                with self.assertRaises(ValueError):flora_result(c,start)

    def test_type_conflict_unknown_and_zero_width_rejected(self):
        for value in ('EXECUTION_WINDOW','invalid'):
            b,p=flora_fixture();p['need_decisions']['source-need']['window_semantics']=value
            with self.assertRaises(ValueError):prepare(p,normalize_request(b))
        b,p=flora_fixture();b['input']['customer_needs'][0]['window_end']='09:00'
        with self.assertRaises(ValueError):prepare(p,normalize_request(b))

    def test_reviewed_type_on_untyped_row_is_not_a_guess(self):
        b,p=flora_fixture(None);p['need_decisions']['source-need']['window_semantics']='START_WINDOW'
        self.assertEqual(prepare(p,normalize_request(b))['needs'][0]['domains'],[[540,560]])

    def test_mixed_types_fail_before_result_instead_of_fabricating_evidence(self):
        b,p=flora_fixture();n=deepcopy(b['input']['customer_needs'][0]);n.pop('window_semantics');n.update(need_id='legacy-need',duration_minutes=10)
        b['input']['customer_needs'].append(n);p['need_decisions']['legacy-need']=deepcopy(p['need_decisions']['source-need']);p['need_decisions']['legacy-need']['engine_id']='legacy-engine'
        with self.assertRaisesRegex(ValueError,'Blandade'):prepare(p,normalize_request(b))

    def test_joint_legacy_import_remains_untyped_but_job_and_export_are_blocked(self):
        b,p=flora_fixture(None,10);c=import_flora(b['input'],p)
        self.assertEqual(c['needs'][0]['domains'],[[540,550]])
        self.assertNotIn('window_semantics',c['needs'][0])
        with self.assertRaisesRegex(ValueError,'NEED_WINDOW_CONTRACT_REQUIRED'):prepare(p,normalize_request(b))
        with self.assertRaisesRegex(ValueError,'NEED_WINDOW_CONTRACT_REQUIRED'):_normalize(c,{}, {})

    def test_flex_is_restricted_by_typed_source_not_exported_as_hidden_exception(self):
        b,p=flora_fixture();p['need_decisions']['source-need'].update(flex=True,flex_start_minute=480,flex_end_minute=1000)
        c=prepare(p,normalize_request(b));self.assertEqual(c['needs'][0]['domains'],[[540,560]])

    def test_offset_dates_and_overnight_source_survive(self):
        b,p=flora_fixture();n=b['input']['customer_needs'][0]
        n.update(window_start='2027-01-04T08:00Z',window_end='2027-01-04T08:20Z')
        c=prepare(p,normalize_request(b));self.assertEqual(c['needs'][0]['domains'],[[540,560]])
        self.assertEqual(flora_result(c)[1]['need_window_contract']['needs'][0]['source_window_start'],'2027-01-04T09:00+01:00')
        n.update(window_start='23:50',window_end='00:10');c=prepare(p,normalize_request(b))
        self.assertEqual(c['needs'][0]['domains'],[[1430,1450]])
        self.assertEqual(need_windows.export(c['source_needs'],lambda n:n['id'],str)['need_window_contract']['needs'][0]['source_window_end'],'1450')

    def test_period_end_clips_start_domain_not_source_and_no_partial_duration(self):
        b,p=flora_fixture();n=b['input']['customer_needs'][0]
        n.update(date='2027-01-31',window_start='23:00',window_end='23:50')
        c=prepare(p,normalize_request(b));self.assertEqual(c['needs'][0]['domains'],[[40260,40260]])
        self.assertEqual(c['needs'][0]['source_window_end'],40310)
        n['window_start']='23:01'
        with self.assertRaises(ValueError):prepare(p,normalize_request(b))

    def test_case_rejects_mutated_start_domain_before_model(self):
        b,p=flora_fixture();c=prepare(p,normalize_request(b));c['needs'][0]['domains']=[[540,561]]
        with self.assertRaisesRegex(ValueError,'kontraktet motsäger'):check_case(c)

    def test_availability_import_model_proto_and_export_no_solve(self):
        b,p=availability_fixture();c=prepare(p,normalize_request(b))
        # Model construction only; every CpSolver entry is guarded by runner.
        model,ctx=build_model(c)
        start=next(v for v in model.Proto().variables if v.name=='n1_start')
        n=c['needs'][0];self.assertEqual(list(start.domain),[n['earliest'],n['latest_end']])
        raw,out=availability_result(c)
        self.assertEqual(out['need_window_contract']['needs'][0]['source_window_end'],'2026-06-01T08:50+02:00')
        self.assertEqual(out['schedule']['interventions'][0]['end'],'2026-06-01T09:50+02:00')
        self.assertEqual(len(out['need_window_contract']['needs']),2)
        self.assertIn('n2',out['unassigned_need_ids'])
        self.assertEqual(out['validation']['overall'],'UNKNOWN')
        self.assertFalse(out['business_schedule_approved'])

    def test_availability_independent_window_checks(self):
        b,p=availability_fixture();c=prepare(p,normalize_request(b));n=c['needs'][0]
        for a,valid in [(n['earliest']-1,False),(n['earliest'],True),(n['latest_end'],True),(n['latest_end']+1,False)]:
            raw,out=availability_result(c,a)
            timing=[r for r in out['validation']['violations'] if r['rule_id']=='need_timing']
            self.assertEqual(not timing,valid,(a,timing))

    def test_availability_execution_overrun_and_mutated_source(self):
        b,p=availability_fixture('EXECUTION_WINDOW')
        with self.assertRaises(ValueError):prepare(p,normalize_request(b))
        b,p=availability_fixture();c=prepare(p,normalize_request(b))
        c['needs'][0]['earliest']-=1
        _,out=availability_result(c)
        self.assertTrue(any(r['rule_id']=='need_timing' for r in out['validation']['violations']))

    def test_availability_legacy_no_contract_and_overlay_unchanged(self):
        b,p=availability_sample();c=prepare(p,normalize_request(b));_,out=availability_result(c)
        self.assertNotIn('need_window_contract',out)
        p['reviewed_case']['needs'][0]['duration']=45
        p['decision_ledger']=[dict(need_id='n1',status='CONFIRMED_BY_USER',decision_id='synthetic',source='synthetic',changes=[dict(field='duration_minutes',before=30,after=45)])]
        self.assertEqual(prepare(p,normalize_request(b))['needs'][0]['duration'],45)

    def test_availability_binding_sha_dataset_period_and_source_unchanged(self):
        for field,value in [('source_file_sha256','b'*64),('dataset_id','OTHER'),('timezone','UTC')]:
            b,p=availability_sample();p['reviewed_case']['metadata']['source_workbook_sha256']='a'*64;b['input']['metadata']['source_file_sha256']='a'*64
            p['source_identity']=source_identity(b['input']);b['input']['metadata'][field]=value
            with self.assertRaises(ValueError):prepare(p,normalize_request(b))
        b,p=availability_sample();b['input']['metadata']['periods'][1]['end']='2026-06-29'
        with self.assertRaises(ValueError):prepare(p,normalize_request(b))

    def test_availability_typed_overlay_is_not_mislabelled_as_source(self):
        b,p=availability_fixture();p['reviewed_case']['needs'][0]['duration']=70
        p['decision_ledger']=[dict(need_id='n1',status='CONFIRMED_BY_USER',decision_id='synthetic',source='synthetic',changes=[dict(field='duration_minutes',before=60,after=70)])]
        with self.assertRaisesRegex(ValueError,'annat uttryckligt kontrakt'):prepare(p,normalize_request(b))

    def test_duration_must_be_positive_integer(self):
        for duration in [0,-1,True,1.5]:
            b,p=flora_fixture(duration=duration)
            with self.assertRaises(ValueError):prepare(p,normalize_request(b))
