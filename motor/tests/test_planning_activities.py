"""All data fictional. Run only with run_activity_checks.py (solver/SQL guards)."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bb.api import app
from bb.engine_methods import prepare
from bb.flora_jobs import normalize_request, digest
from bb.flora import validate_case, _normalize
from bb.flora.optimizer import build
from bb.planning_activities import ActivityReviewRequired, VERSION, model_result
from test_typed_windows_contract import flora_fixture, availability_fixture


def activity(identity='journal', **values):
    return dict(id=identity,name='Syntetisk aktivitet '+identity,category='kundnara',on=True,
        minutes=10,freq='per_shift',occurrences=None,shift_override=None,anchor='shift_start',
        person_id=None,customer_id=None,slots=[]) | values


def slot(**values):
    return dict(id='slot-1',date='2027-01-04',start='10:30',window_from=None,window_to=None,
        minutes=30,person_id='person-a',customer_id='customer-a') | values


def fixture(acts=None):
    body,profile=flora_fixture()
    row=next(x for x in body['input']['schedule_segments'] if x['segment_id']=='active-row')
    row['sequence_id']='verified-duty-1'
    profile['segment_decisions']['active-row'].update(mode='fixed',whole_duty_id='verified-duty-1')
    profile['candidate_windows']=[]
    body['settings']={'activities':acts if acts is not None else [activity()]}
    return body,profile


def case_for(acts=None):
    body,profile=fixture(acts)
    return prepare(profile,normalize_request(body))


def result_for(case, explicit_starts=None, need_start=560):
    starts=explicit_starts or {}
    rows=[]
    for r in case.get('planning_activities',{}).get('occurrences',[]):
        if r['id'] in starts:start=starts[r['id']]
        else:
            assert len(r['domains'])==1 and r['domains'][0][0]==r['domains'][0][1], 'Test needs explicit start for variable slot'
            start=r['domains'][0][0]
        rows.append(dict(id=r['id'],person_id=r['person_id'],start=start,end=start+r['minutes']))
    raw=dict(segments=deepcopy(case['references']['import']['segments']),breaks=[],
        placements=[dict(id=case['needs'][0]['id'],start=need_start,assigned_people=['person-a'])],
        stages=[dict(status='FEASIBLE')],total_seconds=0)
    if rows:raw['planning_activities']=rows
    validation=validate_case(case,raw)
    return raw,_normalize(case,raw,validation)


def probe_aggregate(acts=None, stop_key=None):
    if acts is None:acts=[activity(),activity('write',minutes=15,anchor=None),
        activity('contact',minutes=30,freq='per_customer_week',anchor=None,customer_id='customer-a',person_id='person-a',slots=[slot()]),
        activity('weekly',minutes=60,freq='per_customer_week',anchor=None,customer_id='customer-a',person_id='person-a'),
        activity('gp',minutes=60,freq='per_customer_month',anchor=None)]
    body,profile=fixture(acts)
    registry={'schema_version':'bb-business-profiles/1.0','workspaces':{'org:synthetic-window':{
        'business_id':'synthetic-window','data_use':'development','profile_path':'/synthetic/profile'}}}
    def read(path,label):return deepcopy(registry if path=='/synthetic/registry' else profile)
    with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic-token','BB_ENGINE_PROFILE_REGISTRY':'/synthetic/registry'}),patch('bb.business_profiles._read',side_effect=read):
        with TestClient(app) as client:
            headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'org:synthetic-window'}
            if stop_key:headers['Idempotency-Key']=stop_key
            response=client.post('/api/engine/jobs',json=body,headers=headers)
    return dict(http=response.status_code,body=response.json())


class ActivityTests(unittest.TestCase):
    def test_anchor_and_actual_export_no_customer_kpi(self):
        b,p=fixture();before=deepcopy((b,p));c=prepare(p,normalize_request(b))
        r=c['planning_activities']['occurrences'][0]
        self.assertEqual(r['domains'],[[480,480]])
        self.assertEqual(r['person_id'],'person-a');self.assertEqual(r['pass_id'],'reviewed:verified-duty-1')
        raw,out=result_for(c);e=out['planning_activity_contract']
        self.assertFalse(out['validation']['violations']);self.assertEqual(out['validation']['overall'],'UNKNOWN')
        self.assertEqual(e['total_minutes'],10);self.assertEqual(e['placed_occurrences'],1)
        self.assertEqual(e['placements'][0]['start'],'2027-01-04T08:00+01:00')
        self.assertIsNone(e['placements'][0]['customer_id']);self.assertIsNone(e['direct_customer_minutes'])
        self.assertFalse(e['included_in_customer_need_coverage'])
        self.assertEqual(out['after']['total_needs'],1)
        self.assertEqual(e['binding']['profile_hash'],digest(p))
        self.assertEqual(e['binding']['input_hash'],digest(b['input']))
        self.assertEqual((b,p),before)

    def test_end_anchor(self):
        c=case_for([activity(anchor='shift_end')]);self.assertEqual(c['planning_activities']['occurrences'][0]['domains'],[[710,710]])

    def test_one_per_verified_duty_not_one_per_segment(self):
        b,p=fixture();r=next(x for x in b['input']['schedule_segments'] if x['segment_id']=='active-row')
        second=deepcopy(r);second.update(segment_id='part-2',start='2027-01-04T10:00');r['end']='2027-01-04T10:00'
        b['input']['schedule_segments'].append(second);p['segment_decisions']['part-2']=deepcopy(p['segment_decisions']['active-row'])
        c=prepare(p,normalize_request(b));self.assertEqual(len(c['planning_activities']['occurrences']),1)
        second['sequence_id']='verified-duty-2'
        p['segment_decisions']['part-2']['whole_duty_id']='verified-duty-2'
        c=prepare(p,normalize_request(b))
        self.assertEqual([x['domains'] for x in c['planning_activities']['occurrences']],[[[480,480]],[[600,600]]])

    def test_valid_activity_reaches_only_next_preflight_not_job_manager(self):
        response=probe_aggregate([activity()],stop_key='STOP/BEFORE_MANAGER')
        self.assertEqual(response,dict(http=422,body={'detail':'Ogiltig körningsnyckel.'}))

    def test_touching_segments_without_whole_duty_proof_rejected(self):
        b,p=fixture();p['segment_decisions']['active-row'].pop('whole_duty_id')
        with self.assertRaisesRegex(ActivityReviewRequired,'Aktiviteterna'):prepare(p,normalize_request(b))

    def test_variable_passes_not_silently_excluded(self):
        b,p=flora_fixture();b['settings']={'activities':[activity()]}
        with self.assertRaises(ActivityReviewRequired) as caught:prepare(p,normalize_request(b))
        self.assertIn('VARIABLE_OR_NEW_DUTIES',caught.exception.issues[0]['unsupported_reason'])

    def test_source_duty_cannot_disappear_when_no_candidate_was_generated(self):
        b,p=fixture()
        row=deepcopy(next(x for x in b['input']['schedule_segments'] if x['segment_id']=='active-row'))
        row.update(segment_id='unmodeled-duty',start='2027-01-05T08:00',end='2027-01-05T12:00',sequence_id='other-duty')
        b['input']['schedule_segments'].append(row)
        p['segment_decisions']['unmodeled-duty']=deepcopy(p['segment_decisions']['active-row'])
        p['segment_decisions']['unmodeled-duty'].update(mode='mutable',whole_duty_id='other-duty')
        with self.assertRaises(ActivityReviewRequired) as caught:prepare(p,normalize_request(b))
        self.assertIn('SOURCE_DUTY_NOT_FIXED',caught.exception.issues[0]['unsupported_reason'])

    def test_contact_slot_with_active_pass(self):
        c=case_for([activity('contact',freq='per_customer_week',anchor=None,minutes=30,slots=[slot()],customer_id='customer-a',person_id='person-a')])
        raw,out=result_for(c);e=out['planning_activity_contract']
        self.assertFalse(out['validation']['violations'])
        self.assertEqual(e['placements'][0]['slot_id'],'slot-1')
        self.assertEqual(e['placements'][0]['customer_id'],'customer-a')
        self.assertEqual(e['activities'][0]['scope'],'EXPLICIT_SLOTS_ONLY')
        self.assertEqual(e['activities'][0]['frequency_extent_status'],'NOT_FULLY_PLACED_OR_VERIFIED')
        self.assertTrue(e['activities'][0]['outside_claims'])

    def test_slot_outside_pass_rejected(self):
        with self.assertRaises(ActivityReviewRequired) as caught:case_for([activity(anchor=None,slots=[slot(start='13:00')])])
        self.assertIn('SLOT_NOT_COVERED',caught.exception.issues[0]['unsupported_reason'])

    def test_window_is_domain_not_guessed_placement(self):
        c=case_for([activity(anchor=None,slots=[slot(start=None,window_from='10:30',window_to='11:30')])])
        self.assertEqual(c['planning_activities']['occurrences'][0]['domains'],[[630,660]])
        model,*_=build(c);self.assertFalse(model.Validate())
        r=model._planning_activities[0]
        self.assertEqual(list(model.Proto().variables[r['start'].Index()].domain),[630,660])

    def test_model_result_exports_source_bound_reservation_without_search(self):
        c=case_for();model,*_=build(c)
        class FixedAssignment:
            def Value(self,var):
                domain=list(model.Proto().variables[var.Index()].domain)
                assert domain==[480,480]
                return 480
        rows=model_result(model,FixedAssignment())
        raw,_=result_for(c);self.assertEqual(rows,raw['planning_activities'])

    def test_window_result_uses_explicit_test_start_and_preserves_domain(self):
        c=case_for([activity(anchor=None,slots=[slot(start=None,window_from='10:30',window_to='11:30')])])
        r=c['planning_activities']['occurrences'][0]
        raw,out=result_for(c,{r['id']:645})
        self.assertFalse(out['validation']['violations'])
        p=out['planning_activity_contract']['placements'][0]
        self.assertEqual(p['start'],'2027-01-04T10:45+01:00')
        self.assertEqual(p['placement_domain'],[{'earliest':'2027-01-04T10:30+01:00','latest':'2027-01-04T11:00+01:00'}])

    def test_unknown_person_customer_window_and_period(self):
        for change in [dict(person_id=None),dict(person_id='foreign'),dict(customer_id='foreign'),dict(date='2027-02-01'),dict(date='2027-02-31'),dict(start=None),dict(window_from='09:00'),dict(minutes=0)]:
            with self.subTest(change=change),self.assertRaises(ActivityReviewRequired):case_for([activity(anchor=None,slots=[slot(**change)])])

    def test_task_binding_never_guessed(self):
        with self.assertRaises(ActivityReviewRequired):case_for([activity(anchor=None,person_id='person-a',slots=[slot(person_id=None)])])

    def test_all_three_incomplete_rows_in_one_422(self):
        r=probe_aggregate();self.assertEqual(r['http'],422)
        self.assertEqual(r['body']['detail']['code'],'ACTIVITY_REVIEW_REQUIRED')
        issues=r['body']['detail']['activities'];self.assertEqual({a['activity_id'] for a in issues},{'write','weekly','gp'})
        self.assertIn('occurrences',next(a for a in issues if a['activity_id']=='gp')['missing_fields'])
        self.assertTrue(all('received' in a and 'unsupported_reason' in a for a in issues))

    def test_pass_evidence_failure_joins_other_activity_errors(self):
        b,p=fixture([activity(),activity('write',anchor=None)]);p['segment_decisions']['active-row'].pop('whole_duty_id')
        with self.assertRaises(ActivityReviewRequired) as caught:prepare(p,normalize_request(b))
        self.assertEqual({e['activity_id'] for e in caught.exception.issues},{'journal','write'})

    def test_off_activity_zero_no_record_even_with_saved_slots(self):
        c=case_for([activity(on=False,slots=[slot()])]);self.assertNotIn('planning_activities',c)
        model,*_=build(c);self.assertEqual(model._planning_activities,[])
        self.assertNotIn('planning_activity_contract',result_for(c)[1])

    def test_soft_competence_override_and_monthly_unknown_not_assumed(self):
        for change in [dict(strength='soft'),dict(competence='Medicinsk delegation'),dict(shift_override=2),dict(freq='per_month',anchor=None,occurrences=None,slots=[slot()]),dict(freq='per_month',anchor=None,occurrences=0,slots=[slot()])]:
            with self.subTest(change=change),self.assertRaises(ActivityReviewRequired):case_for([activity(**change)])

    def test_activity_capacity_is_absence_not_added_shift(self):
        c=case_for();model,variables,tasks,breaks,objectives=build(c)
        self.assertFalse(model.Validate());self.assertEqual(variables,[])
        index=model._planning_activities[0]['interval'].Index()
        self.assertTrue(any(index in constraint.cumulative.intervals for constraint in model.Proto().constraints if constraint.has_cumulative()))
        self.assertTrue(any(index in constraint.no_overlap.intervals for constraint in model.Proto().constraints if constraint.has_no_overlap()))

    def test_customer_capacity_decreases_but_Ar_and_weekly_work_remain(self):
        b,p=fixture([activity(anchor=None,slots=[slot(start='09:20',minutes=60)])]);c=prepare(p,normalize_request(b))
        raw,out=result_for(c)
        self.assertTrue(any(v['rule']=='executor_coverage' for v in out['validation']['violations']))
        self.assertEqual(out['after']['ordinary_net_minutes'],240)
        self.assertEqual(out['after']['ordinary_gross_minutes'],240)
        self.assertEqual(out['after']['break_minutes'],0)

    def test_result_cannot_drop_or_mutate_activity(self):
        c=case_for();raw,_=result_for(c)
        for field,value in [('person_id','foreign'),('start',481),('end',491)]:
            bad=deepcopy(raw);bad['planning_activities'][0][field]=value
            v=validate_case(c,bad);self.assertTrue(any(e['rule']=='planning_activity' for e in v['violations']))
        bad=deepcopy(raw);bad.pop('planning_activities')
        self.assertTrue(any(e['rule']=='planning_activity' for e in validate_case(c,bad)['violations']))

    def test_result_break_and_activity_cannot_use_same_person_minute(self):
        c=case_for();raw,_=result_for(c)
        raw['breaks']=[dict(person='person-a',start=480,end=510)]
        self.assertTrue(any(e['rule']=='planning_activity' for e in validate_case(c,raw)['violations']))

    def test_result_activity_overlap_is_independently_rejected(self):
        acts=[activity('a',anchor=None,slots=[slot(start=None,window_from='10:30',window_to='11:30')]),
              activity('b',anchor=None,slots=[slot(id='slot-2',start=None,window_from='10:30',window_to='11:30')])]
        c=case_for(acts);starts={r['id']:630 for r in c['planning_activities']['occurrences']}
        raw,out=result_for(c,starts)
        self.assertTrue(any(e['rule']=='planning_activity' for e in out['validation']['violations']))

    def test_malformed_and_duplicate_ids_are_structured(self):
        for acts in [[activity(id=[])],[activity('a'),activity('a',on=False)],
                     [activity(anchor=None,slots=[slot(person_id=[])])], [None]]:
            with self.subTest(acts=acts),self.assertRaises(ActivityReviewRequired):case_for(acts)

    def test_exact_activity_overlap_rejected_together(self):
        with self.assertRaises(ActivityReviewRequired) as caught:case_for([activity('a'),activity('b')])
        self.assertEqual({e['activity_id'] for e in caught.exception.issues},{'a','b'})

    def test_known_break_blocks_slot(self):
        b,p=fixture([activity(anchor=None,slots=[slot()])]);p['reference_breaks']=[dict(segment_id='active-row',offset=150,length=30)]
        with self.assertRaises(ActivityReviewRequired):prepare(p,normalize_request(b))

    def test_other_strategy_fails_closed(self):
        b,p=availability_fixture();b['settings']={'activities':[activity()]}
        with self.assertRaises(ActivityReviewRequired) as caught:prepare(p,normalize_request(b))
        self.assertIn('ACTIVITY_STRATEGY_NOT_IMPLEMENTED',caught.exception.issues[0]['unsupported_reason'])

    def test_names_do_not_select_behavior(self):
        c=case_for([activity('unknown-id',name='Godtyckligt namn')])
        self.assertEqual(c['planning_activities']['activities'][0]['activity_id'],'unknown-id')

    def test_input_and_settings_hashes_not_confused(self):
        b,p=fixture();c=prepare(p,normalize_request(b));b['settings']['activities'][0]['minutes']=11
        changed=prepare(p,normalize_request(b))
        left=c['planning_activities']['binding'];right=changed['planning_activities']['binding']
        self.assertEqual(left['input_hash'],right['input_hash']);self.assertNotEqual(left['settings_sha256'],right['settings_sha256'])
        self.assertEqual(left['profile_hash'],right['profile_hash'])

    def test_legacy_route_stops_before_manager(self):
        b,p=fixture([activity(anchor=None)]);b['input']['metadata'].pop('business_id');b['input']['metadata']['schema_version']='flora-bb-input/1.0'
        with patch.dict(os.environ,{'BB_API_TOKEN':'synthetic-token'}),patch('bb.flora_jobs.load_profile',return_value=(p,digest(p))):
            with TestClient(app) as client:
                response=client.post('/api/flora/jobs',json=b,headers={'Authorization':'Bearer synthetic-token','X-BB-Job-Owner':'synthetic-owner'})
        self.assertEqual(response.status_code,422);self.assertEqual(response.json()['detail']['code'],'ACTIVITY_REVIEW_REQUIRED')

    def test_need_window_contract_is_identical(self):
        c=case_for();raw,out=result_for(c);bare=deepcopy(c);bare.pop('planning_activities')
        raw.pop('planning_activities');other=_normalize(bare,raw,validate_case(bare,raw))
        self.assertEqual(out['need_window_contract'],other['need_window_contract'])
