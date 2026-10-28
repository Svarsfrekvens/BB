from copy import deepcopy
import unittest
from ortools.sat.python import cp_model
from bb.flora.daily_rest import assess, constrain


def sample(boundaries=None):
    return dict(origin='2026-05-11T00:00', horizon=2880,
                config={'min_daily_rest':660,'known_from':0,'known_to':2880},
                staff=[{'id':'person-a'}], references={'import':{'segments':[]}},
                daily_rest_parameters={'period_id':'P2','boundaries':[
                    {'person_id':p,'period_id':'P2','minute_of_day':minute}
                    for p,minute in (boundaries if boundaries is not None else {'person-a':0}).items()]})


def row(key,start,end,code='Ar',person='person-a'):
    return dict(id=key,person=person,start=start,end=end,code=code)


def assess_explicit_fixture(case, raw):
    # These arithmetic fixtures explicitly declare separate reviewed duties.
    # Absence of evidence is tested independently; production never adds this.
    case = deepcopy(case)
    case['references']['import']['segments'] = [dict(r, whole_duty_id='reviewed-'+r['id']) for r in raw['segments']]
    return assess(case, raw)


class FixedDailyRestTests(unittest.TestCase):
    def test_contiguous_not_total_rest_and_exact_eleven_hours(self):
        c=sample()
        bad=assess_explicit_fixture(c,{'segments':[row('duty-1',360,1080)]})
        self.assertEqual(bad['windows'][0]['longest_rest_minutes'],360)
        self.assertEqual(bad['status'],'FAIL')  # 6 + 6 hours is not 11 continuous.
        good=assess_explicit_fixture(c,{'segments':[row('duty-1',660,1440)]})
        self.assertEqual(good['windows'][0]['longest_rest_minutes'],660)
        self.assertEqual(good['status'],'PASS')
        self.assertEqual(assess_explicit_fixture(c,{'segments':[row('duty-1',659,1440)]})['status'],'FAIL')

    def test_fixed_boundary_changes_outcome_and_edges_are_unknown(self):
        c=sample({'person-a':180})
        out=assess_explicit_fixture(c,{'segments':[row('duty-1',420,960)]})
        middle=next(r for r in out['windows'] if r['start']=='2026-05-11T03:00')
        self.assertEqual(middle['longest_rest_minutes'],660)
        self.assertEqual(middle['status'],'PASS')
        self.assertEqual([r['reason'] for r in out['windows'] if r['status']=='UNKNOWN'],
                         ['PERIOD_EDGE_OR_BOUNDARY_SCOPE']*2)

    def test_missing_boundaries_and_other_policy_never_default(self):
        c=sample({})
        self.assertEqual(assess(c,{'segments':[]})['missing_person_ids'],['person-a'])
        self.assertEqual(assess(c,{'segments':[]})['status'],'UNKNOWN')
        c=sample();c['config']['min_daily_rest']=540
        out=assess(c,{'segments':[]})
        self.assertEqual(out['status'],'UNKNOWN')
        self.assertEqual(out['windows'][0]['reason'],'UNSUPPORTED_REST_POLICY')

    def test_jour_and_overtime_never_count_as_rest(self):
        for code in ('Jo','Kl','Öv'):
            with self.subTest(code=code):
                out=assess_explicit_fixture(sample(),{'segments':[row('duty-1',360,1080,code)]})
                self.assertEqual(out['windows'][0]['longest_rest_minutes'],360)
                self.assertEqual(out['status'],'FAIL')

    def test_gap_in_whole_duty_not_invented_as_rest(self):
        c=sample();rows=[row('duty-1',0,60),row('duty-2',1380,1440)]
        c['references']['import']['segments']=[dict(r,whole_duty_id='known-whole') for r in rows]
        out=assess(c,{'segments':rows})
        self.assertEqual(out['windows'][0]['longest_rest_minutes'],0)
        self.assertEqual(out['windows'][0]['reason'],'UNVERIFIED_WHOLE_DUTY_GAPS')
        self.assertEqual(out['status'],'UNKNOWN')

    def test_combined_jour_conditions_do_not_approve_unverified_exception(self):
        c=sample()
        rows=[row('night-1',0,360,'Jo'),row('night-2',360,1440)]
        c['references']['import']['segments']=[dict(r,whole_duty_id='reviewed-night') for r in rows]
        out=assess(c,{'segments':rows})
        self.assertEqual(out['windows'][0]['longest_rest_minutes'],0)
        self.assertEqual(out['windows'][0]['status'],'UNKNOWN')
        duty=out['conditional_jour_duties'][0]
        self.assertEqual(duty['night_jour_status'],'PASS')
        self.assertEqual(duty['compensation_status'],'PASS')
        self.assertEqual(duty['applicability'],'UNKNOWN')
        # 24h rest is interrupted even by one minute of known overtime.
        out=assess(c,{'segments':rows+[row('extra-1',2879,2880,'Kl')]})
        self.assertEqual(out['conditional_jour_duties'][0]['compensation_status'],'FAIL')
        c['config']['known_to']=2879
        out=assess(c,{'segments':rows})
        self.assertEqual(out['conditional_jour_duties'][0]['compensation_status'],'UNKNOWN')

    def test_short_night_block_detected_and_jour_daytime_does_not_help(self):
        c=sample()
        rows=[row('night-1',0,299,'Jo'),row('night-2',299,600),
              row('night-3',600,900,'Jo'),row('night-4',900,1440)]
        c['references']['import']['segments']=[dict(r,whole_duty_id='reviewed-night') for r in rows]
        out=assess(c,{'segments':rows})
        duty=out['conditional_jour_duties'][0]
        self.assertEqual(duty['longest_night_jour_minutes'],299)
        self.assertEqual(duty['night_jour_status'],'FAIL')

    def test_fixed_daily_solver_constraint_rejects_split_rest(self):
        c=sample();model=cp_model.CpModel()
        constrain(c,model,'person-a',[dict(start=360,end=1080,present=1)])
        self.assertEqual(cp_model.CpSolver().Solve(model),cp_model.INFEASIBLE)

    def test_generated_dated_ids_are_distinct_duties(self):
        rows=[row('NEW-person-a-2026-05-11',720,960),
              row('NEW-person-a-2026-05-12',2160,2400)]
        result=assess(sample(),{'segments':rows})
        self.assertEqual(result['status'],'UNKNOWN')
        self.assertEqual([r['longest_rest_minutes'] for r in result['windows']],[720,720])

    def test_optional_exception_only_applies_when_selected_for_same_person(self):
        for selected,expected in [(0,cp_model.INFEASIBLE),(1,cp_model.OPTIMAL)]:
            c=sample();model=cp_model.CpModel();pr=model.NewBoolVar('selected');model.Add(pr==selected)
            constrain(c,model,'person-a',[dict(start=360,end=1080,present=1),
                dict(start=0,end=1440,present=pr,combined_jour=True)])
            self.assertEqual(cp_model.CpSolver().Solve(model),expected)

    def test_three_businesses_use_their_own_boundary_without_mutation(self):
        observed=[]
        for business,minute in [('Flora',0),('Galaxen',360),('Vintergatan',1080)]:
            c=sample({'person-a':minute});c['business_id']=business;before=deepcopy(c)
            out=assess_explicit_fixture(c,{'segments':[row('day-1',360,1080)]})
            observed.append(out['status'])
            self.assertEqual(c,before)
            self.assertFalse(out['other_business_decisions_inherited'])
        self.assertEqual(observed,['FAIL','UNKNOWN','UNKNOWN'])


if __name__=='__main__':unittest.main()
