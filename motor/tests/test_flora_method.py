"""Behavioral checks for the extracted method, with fictional IDs and dates."""
import copy
import unittest

from bb.flora import solve_case, validate_case


def fixture():
    need={'id':'need-X','source_row':'source-X','customer':'C','title':'Activity',
          'duration':120,'count':1,'domains':[[600,600]],'original':600,
          'exclusive':False,'parallel_permission':'confirmed-test-decision'}
    cfg=dict(shift_step=5,break_length=30,break_threshold=300,min_work_before_break=1,
             min_work_after_break=1,max_continuous_active=300,min_daily_rest=660,
             min_weekly_rest=2160,min_free_days=9,oncall_cap_28d=2880,
             max_staff_on_duty=1,min_shift=240,calendar_mode='rolling',week_break='MONDAY 00:00')
    cfg['duty_profile']=dict(max_reassigned_minutes=1440,long_jour_min_minutes=1200,night_jour_min_minutes=300,night_start_minute=1320,night_end_minute=480,compensation_trigger_minutes=720,compensation_mode='REFERENCE_UNCONFIRMED_REST_AT_LEAST_DUTY_SPAN')
    before={'id':'source-duty','person':'employee-X','start':600,'end':840,'code':'Ar','type':'AKTIVT_ARBETE'}
    return dict(origin='2026-05-11T00:00',end='2026-06-08T00:00',horizon=40320,
                staff=[dict(id='employee-X',name='Employee',ordinary=True,target_net=240,
                            all_task_skills=True,day='JA',evening='JA',sleeping_oncall='NEJ',awake_night='NEJ')],
                fixed_segments=[],candidates=[dict(id='candidate-X',person='employee-X',day=0,lo=600,hi=840,min_length=240,max_length=240)],
                needs=[need],source_needs=[copy.deepcopy(need)],reassignable_temporary_units=[],
                config=cfg,references={'import':{'segments':[before],'breaks':[],'placements':[]}},
                integration={'person_id_map':{'employee-X':'uploaded-employee'},'need_id_map':{'need-X':'uploaded-need'},
                             'period':{'id':'up-period','start':'2026-05-11','end':'2026-06-07','timezone':'Europe/Stockholm'}})


class FloraMethodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=fixture()
        cls.output=solve_case(cls.case,seconds=2,workers=1)

    def test_real_calculation_and_one_consistent_export(self):
        out=self.output
        self.assertEqual(out['after']['fully_covered_needs'],1)
        self.assertEqual(out['after']['ordinary_net_minutes'],240)
        self.assertEqual(out['schedule']['segments'][0]['person_id'],'uploaded-employee')
        self.assertEqual(out['schedule']['interventions'][0]['need_id'],'uploaded-need')
        self.assertTrue(out['schedule']['segments'][0]['start'].endswith('+02:00'))
        self.assertFalse(out['business_schedule_approved'])
        self.assertEqual(out['validation']['checked_status'],'PASS')
        self.assertEqual(out['validation']['overall'],'UNKNOWN')
        self.assertIsNone(out['after']['extra_minutes'])

    def test_preserves_input_and_detects_missing_history(self):
        c=copy.deepcopy(self.case)
        original=copy.deepcopy(c)
        solve_case(c,seconds=1,workers=1)
        self.assertEqual(c,original)
        c['references']['import']['segments'].append(dict(id='history-X',person='employee-X',start=-1440,end=-1200,code='Ar',type='AKTIVT_ARBETE'))
        v=validate_case(c,self.output)
        self.assertIn('known_actual_P1_work_missing',{x['rule'] for x in v['violations']})

    def test_recorded_boundaries_are_checked_and_unconfirmed_edges_remain_unknown(self):
        c=copy.deepcopy(self.case)
        params=dict(mode='FIXED_PER_PERSON_AND_PERIOD',period_id='up-period',timezone='Europe/Stockholm',
                    boundaries=[dict(period_id='up-period',person_id='employee-X',time='03:00',minute_of_day=180,
                                     confirmed_at='2026-10-17',source='Explicit test decision',
                                     period_start='2026-05-11',period_end='2026-06-07',timezone='Europe/Stockholm')],
                    missing_person_ids=[],status='BOUNDARIES_RECORDED_CHECK_NOT_IMPLEMENTED',validation_status='UNKNOWN')
        c['daily_rest_parameters']=copy.deepcopy(params)
        before=copy.deepcopy(c)
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(c,before)
        self.assertEqual(out['daily_rest_parameters'],params)
        rules=[row for row in out['validation']['rules'] if row['rule_id']=='daily_rest_24h']
        self.assertEqual(len(rules),1)
        self.assertEqual(rules[0]['status'],'UNKNOWN')
        self.assertNotIn('inte implementerad',rules[0]['message'])
        certificate=out['validation']['certificates']['daily_rest_24h.json']
        self.assertEqual(sum(r['status']=='PASS' for r in certificate['windows']),27)
        self.assertEqual(sum(r['status']=='UNKNOWN' for r in certificate['windows']),2)
        self.assertEqual(out['validation']['overall'],'UNKNOWN')
        self.assertTrue(out['review_required'])
        self.assertFalse(out['business_schedule_approved'])
        out['daily_rest_parameters']['boundaries'][0]['time']='07:00'
        self.assertEqual(c,before)

    def test_legacy_daily_rest_reports_missing_boundaries_without_defaulting(self):
        rules=[row for row in self.output['validation']['rules'] if row['rule_id']=='daily_rest_24h']
        self.assertEqual(rules[0]['status'],'UNKNOWN')
        self.assertIn('Dygnsbryt saknas för 1',rules[0]['message'])
        self.assertIsNone(self.output['daily_rest_parameters'])

    def test_competence_unknown_never_becomes_permission(self):
        c=copy.deepcopy(self.case);c['staff'][0]['all_task_skills']=None
        with self.assertRaisesRegex(ValueError,'behörighet'):
            solve_case(c,seconds=1)

    def test_rule_relaxation_rejected(self):
        for key,value in [('min_shift',180),('min_free_days',8)]:
            c=copy.deepcopy(self.case);c['config'][key]=value
            with self.assertRaises(ValueError):solve_case(c,seconds=1)

    def test_independent_validator_catches_break_and_net_corruption(self):
        out=copy.deepcopy(self.output['raw_solution'])
        out['breaks']=[dict(person='employee-X',start=590,end=620)]
        v=validate_case(self.case,out)
        self.assertEqual(v['overall'],'FAIL')
        self.assertIn('break_outside_contiguous_Ar',{x['rule'] for x in v['violations']})
        self.assertIn('retained_original_worked_net',{x['rule'] for x in v['violations']})

    def test_concurrent_permission_does_not_remove_shopping_exclusivity(self):
        c=copy.deepcopy(self.case)
        other=copy.deepcopy(c['needs'][0]);other['id']='shopping-X';other['exclusive']=True
        c['needs'].append(other);c['source_needs'].append(copy.deepcopy(other))
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(out['after']['fully_covered_needs'],1)
        self.assertEqual(len(out['unassigned_need_ids']),1)
        # Without the explicit shopping restriction both may share the one
        # staff member under this particular, input-authorized scenario.
        c['needs'][1]['exclusive']=False;c['source_needs'][1]['exclusive']=False
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(out['after']['fully_covered_needs'],2)

    def test_rolling_free_days_count_known_p1_calendar_dates(self):
        c=copy.deepcopy(self.case); raw=copy.deepcopy(self.output['raw_solution'])
        history=[dict(id=f'history-{d}-01',person='employee-X',start=d*1440+600,end=d*1440+840,code='Ar',type='AKTIVT_ARBETE') for d in range(-19,0)]
        c['references']['import']['segments'].extend(copy.deepcopy(history))
        c['fixed_segments'].extend(copy.deepcopy(history));raw['segments'].extend(history)
        checked=validate_case(c,raw)
        self.assertIn('free_calendar_days9',{v['rule'] for v in checked['violations']})
        self.assertEqual(checked['details']['people']['employee-X']['rolling_free_min'],8)

    def test_four_hours_applies_to_whole_jour_duty_not_each_fragment(self):
        c=copy.deepcopy(self.case)
        c['staff'][0]['sleeping_oncall']='JA';c['staff'][0]['target_net']=120
        rows=[dict(id='source-night-01',person='employee-X',start=1320,end=1380,code='Ar',type='AKTIVT_ARBETE'),
              dict(id='source-night-02',person='employee-X',start=1380,end=1830,code='Jo',type='SOVANDE_JOUR'),
              dict(id='source-night-03',person='employee-X',start=1830,end=1890,code='Ar',type='AKTIVT_ARBETE')]
        c['references']['import']['segments']=copy.deepcopy(rows);c['fixed_segments']=copy.deepcopy(rows);c['candidates']=[]
        c['needs']=[];c['source_needs']=[]
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(out['solver_status'],'OPTIMAL')
        checked=out['validation']
        self.assertEqual(checked['checked_status'],'PASS')
        self.assertNotIn('whole_occasion_under4h',{v['rule'] for v in checked['violations']})
        self.assertEqual(checked['details']['people']['employee-X']['jour_P2_minutes'],450)

    def test_original_fixed_whole_duty_below_four_hours_is_infeasible(self):
        c=copy.deepcopy(self.case)
        row=dict(id='source-short-01',person='employee-X',start=600,end=780,
                 code='Ar',type='AKTIVT_ARBETE')
        c['staff'][0]['target_net']=180
        c['references']['import']['segments']=[copy.deepcopy(row)]
        c['fixed_segments']=[copy.deepcopy(row)];c['candidates']=[]
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(out['solver_status'],'INFEASIBLE')
        self.assertEqual(out['schedule']['segments'],[])
        self.assertIsNone(out['after']['ordinary_net_minutes'])
        self.assertFalse(out['business_schedule_approved'])

    def test_original_reassignable_whole_duty_below_four_hours_is_infeasible(self):
        for ordinary_recipient in (False,True):
            with self.subTest(ordinary_recipient=ordinary_recipient):
                c=copy.deepcopy(self.case)
                row=dict(id='source-short-01',person='employee-X',start=600,end=780,
                         code='Ar',type='AKTIVT_ARBETE')
                c['staff'][0].update(ordinary=False,target_net=None)
                c['references']['import']['segments']=[copy.deepcopy(row)]
                if ordinary_recipient:
                    recipient=copy.deepcopy(self.case['staff'][0])
                    recipient.update(id='employee-Y',target_net=180)
                    c['staff'].append(recipient)
                    # Its imported three-hour reference forces the unit to the
                    # ordinary recipient; keeping its original owner cannot
                    # satisfy the ordinary per-person net constraint.
                    c['references']['import']['segments'].append(
                        dict(row,id='recipient-reference-01',person='employee-Y'))
                c['fixed_segments']=[copy.deepcopy(row)];c['candidates']=[]
                c['reassignable_temporary_units']=[dict(id='source-short',original_person='employee-X',
                                                       start=600,end=780,rows=[copy.deepcopy(row)],
                                                       segment_ids=[row['id']],ar_p2_minutes=180)]
                out=solve_case(c,seconds=2,workers=1)
                self.assertEqual(out['solver_status'],'INFEASIBLE')
                self.assertEqual(out['schedule']['segments'],[])
                self.assertFalse(out['business_schedule_approved'])

    def test_original_whole_duty_of_exactly_four_hours_remains_feasible(self):
        for reassignable in (False,True):
            with self.subTest(reassignable=reassignable):
                c=copy.deepcopy(self.case)
                row=dict(id='source-four-01',person='employee-X',start=600,end=840,
                         code='Ar',type='AKTIVT_ARBETE')
                c['references']['import']['segments']=[copy.deepcopy(row)]
                c['fixed_segments']=[copy.deepcopy(row)];c['candidates']=[]
                if reassignable:
                    c['staff'][0].update(ordinary=False,target_net=None)
                    c['reassignable_temporary_units']=[dict(id='source-four',original_person='employee-X',
                                                           start=600,end=840,rows=[copy.deepcopy(row)],
                                                           segment_ids=[row['id']],ar_p2_minutes=240)]
                out=solve_case(c,seconds=2,workers=1)
                self.assertEqual(out['solver_status'],'OPTIMAL')
                self.assertEqual(out['validation']['checked_status'],'PASS')
                self.assertEqual(out['after']['fully_covered_needs'],1)
                self.assertTrue(any(all(segment.get(key)==value for key,value in row.items())
                                    for segment in out['raw_solution']['segments']))

    def test_short_historical_and_incoming_duties_are_preserved_not_replanned(self):
        for start,end in ((-840,-660),(-120,60)):
            with self.subTest(start=start,end=end):
                c=copy.deepcopy(self.case)
                c['candidates'][0].update(day=1,lo=2340,hi=2580)
                c['references']['import']['segments'][0].update(start=2340,end=2580)
                for needs in (c['needs'],c['source_needs']):
                    needs[0].update(domains=[[2340,2340]],original=2340)
                history=dict(id='source-history-01',person='employee-X',start=start,end=end,
                             code='Ar',type='AKTIVT_ARBETE')
                c['references']['import']['segments'].append(copy.deepcopy(history))
                c['fixed_segments'].append(copy.deepcopy(history))
                c['staff'][0]['target_net']=240+max(0,end)
                out=solve_case(c,seconds=2,workers=1)
                self.assertEqual(out['solver_status'],'OPTIMAL')
                self.assertEqual(out['validation']['checked_status'],'PASS')
                self.assertEqual(out['after']['fully_covered_needs'],1)
                self.assertTrue(any(all(row.get(key)==value for key,value in history.items())
                                    for row in out['raw_solution']['segments']))

    def test_confirmed_absence_blocks_work_without_dropping_hours(self):
        c=copy.deepcopy(self.case);c['integration']['absence_mode']='preserve'
        lock=dict(id='leave-X',person='employee-X',start=0,end=1440,code='Se',type='ABSENCE')
        c['fixed_segments'].append(copy.deepcopy(lock));c['confirmed_absence_locks']=[lock]
        c['candidates'].append(dict(id='next-day-X',person='employee-X',day=1,lo=2040,hi=2280,min_length=240,max_length=240))
        out=solve_case(c,seconds=2,workers=1)
        self.assertEqual(out['after']['ordinary_net_minutes'],240)
        self.assertEqual(out['after']['fully_covered_needs'],0)
        work=[r for r in out['raw_solution']['segments'] if r['code']=='Ar']
        self.assertTrue(all(r['start']>=1440 for r in work))
        self.assertEqual(out['validation']['checked_status'],'PASS')

    def test_zero_net_target_is_not_derived_from_unknown(self):
        c=copy.deepcopy(self.case);c['staff'][0]['target_net']=None
        with self.assertRaises(ValueError):solve_case(c,seconds=1)


if __name__=='__main__':unittest.main()
