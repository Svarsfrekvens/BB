"""Invented source rows and reviewed decisions only; no business upload data."""
from copy import deepcopy
from bb.availability_import import source_identity, minute


def sample(business='synthetic-a'):
    zone = 'Europe/Stockholm'
    lo = minute('2026-06-01T00:00', zone)
    hi = lo+28*1440
    a, b = lo+8*60, lo+12*60
    periods = [dict(id='history', start='2026-05-04', end='2026-05-31'),
               dict(id='next', start='2026-06-01', end='2026-06-28')]
    source = [dict(segment_id='s1', sequence_id='pass1', person_id='p1', start='2026-06-01T08:00',
                   end='2026-06-01T12:00', source_code='Ar', staffing_status='ASSIGNED', source_ref='SYNTHETIC:1'),
              dict(segment_id='vacant1', sequence_id='vacant', person_id=None, start='2026-06-01T08:00',
                   end='2026-06-01T12:00', source_code='Ar', staffing_status='VACANT', source_ref='SYNTHETIC:2')]
    raw = dict(metadata=dict(schema_version='bb-input/1.0', dataset_id='synthetic-availability',
        business_id=business, data_use='development', timezone=zone, periods=periods,
        planning_period_id='next', history_period_id='history', source_layout='synthetic/1.0'),
        staff=[dict(person_id='p1', alias='Invented person')], customers=[dict(customer_id='k1', scope='INDIVIDUAL')],
        schedule_segments=source, customer_needs=[dict(need_id='n1', date='2026-06-01', customer_id='k1',
            window_start='2026-06-01T08:30', window_end='2026-06-01T09:30', duration_minutes=30,personnel_count_candidate=1),
            dict(need_id='n2', date='2026-06-01', customer_id='k1', window_start='2026-06-01T09:30',
                 window_end='2026-06-01T10:30', duration_minutes=30,personnel_count_candidate=1)], business_rules=[], vc_answers=[])
    person = dict(id='p1', alias='Invented person', planned_Ar_target_minutes=240, staffing_type='ORDINARY_SOURCE',
        availability_status='VERIFIED', allowed_presence_windows=[dict(start=a, end=b, status='VERIFIED')],
        history_known=True, skills_known=[], hard_condition_unknown=False,
        source_role_permissions={role:dict(allowed=value, status='VERIFIED', source_ref='SYNTHETIC')
            for role,value in [('day',True),('evening',True),('sleeping_oncall',False),('awake_night',False)]})
    candidate = dict(id='c1', employee_id='p1', start=a, end=b, work=[[a,b]], jour=[], variable=False,
        mode='CROP_SOURCE', is_original=False, is_new_or_shortened=True, staffing_type='ORDINARY_SOURCE')
    needs = [dict(id='n1', customer_id='k1', earliest=a+30, latest_end=a+90, duration=30, count=1, count_confirmed=1,
        eligible_employee_ids=['p1'], required_skills_confirmed=[], movable=True, locked_start=None, blockers=[]),
        dict(id='n2', customer_id='k1', earliest=a+90, latest_end=a+150, duration=30, count=1, count_confirmed=1,
        eligible_employee_ids=[], required_skills_confirmed=[], movable=True, locked_start=None,
        blockers=['PERMISSION_NOT_VERIFIED'])]
    case = dict(schema_version='bb-availability-case/1.0', period=dict(lo=lo, hi=hi, start='2026-06-01T00:00',
        end_exclusive='2026-06-29T00:00', history_lo=lo-28*1440, timezone=zone),
        employees=[person], needs=needs, candidates=[candidate], frozen_duties=[], vacancy_duties=[],
        source_schedule_segments=[dict(segment_id=r['segment_id'], person_id=r['person_id'], start=r['start'],
            end=r['end'], source_code='Ar', is_vacant=r['staffing_status']=='VACANT') for r in source],
        rules=dict(min_duty_minutes=240, min_free_days=9, free_days_mode='rolling28', daily_rest_minutes=660,
            weekly_rest_minutes=2160, week_anchor=None, week_anchor_mode='PER_EMPLOYEE_FIXED_SELECTED',
            jour_cap_minutes=2880, jour_window_minutes=40320, breaks='OMITTED_SCENARIO',
            jour_compensation=dict(mode='IMMEDIATE_REST_MINUTES', status='CONFIRMED', rest_minutes=660, source_ref='SYNTHETIC')),
        unknown_controls=[], metadata={}, resource_budget={})
    profile = dict(schema_version='bb-analysis-input-profile/1.0', profile_id=business+'-availability',
        business_id=business, data_use='development', engine_strategy='reviewed-availability/1.0',
        source_identity=source_identity(raw), reviewed_case=deepcopy(case),
        partial_input_policy='KEEP_ALL_NEEDS_BLOCK_UNVERIFIED_ASSIGNMENTS',
        review_provenance=dict(source='SYNTHETIC DECISIONS', reviewed_at='2026-10-19'), decision_ledger=[])
    return dict(input=raw, seconds=1, scenario=dict(absence_mode='preserve'), objective_mode='coverage_then_temporary'), profile
