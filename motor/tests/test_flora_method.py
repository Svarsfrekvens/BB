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
        checked=validate_case(c,dict(segments=rows,breaks=[],placements=[],temporary_unit_reassignments=[]))
        self.assertNotIn('whole_occasion_under4h',{v['rule'] for v in checked['violations']})
        self.assertEqual(checked['details']['people']['employee-X']['jour_P2_minutes'],450)

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
