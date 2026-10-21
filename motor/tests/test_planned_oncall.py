"""Reviewed planning decisions must not rewrite sickness outcomes."""
from copy import deepcopy
import unittest
from test_flora_import import sample
from bb.flora_import import prepare_case, FloraImportError


def fixture():
    raw, profile = sample()
    for suffix, start, end, code in [('01','00:00','02:00','St'), ('02','02:00','05:00','Jo'),
                                      ('03','05:00','07:00','St')]:
        sid = 'test-duty-' + suffix
        row = dict(segment_id=sid, person_id='person-a', start='2027-01-31T'+start,
                   end='2027-01-31T'+end, source_code=code,
                   category='UNKNOWN' if code == 'St' else 'SOVANDE_JOUR')
        raw['schedule_segments'].append(row)
        profile['segment_decisions'][sid] = dict(expected={k:row[k] for k in
            ('person_id','source_code','category')}, mode='excluded' if code=='St' else 'fixed',
            reference_import=code=='Jo')
    profile['planned_oncall_replacements'] = [dict(id='test-duty-PLAN01',
        source_segment_id='test-duty-01', expected_start='2027-01-31T00:00',
        expected_end='2027-01-31T02:00', start='2027-01-31T00:00', end='2027-01-31T02:00',
        status='SCENARIO', source='Synthetic reviewed night plan'), dict(id='test-duty-PLAN03',
        source_segment_id='test-duty-03', expected_start='2027-01-31T05:00',
        expected_end='2027-01-31T07:00', start='2027-01-31T05:00', end='2027-01-31T06:30',
        status='SCENARIO', source='Synthetic reviewed night plan')]
    return raw, profile


class PlannedOncallTest(unittest.TestCase):
    def test_reviewed_source_duty_identity_reaches_explicit_replacements(self):
        raw,profile=fixture()
        without=prepare_case(raw,profile)
        self.assertFalse(any(r.get('whole_duty_id') for r in without['fixed_segments']
                             if 'PLAN' in r['id']))
        for row in raw['schedule_segments'][3:]:
            row['sequence_id']='test-duty'
            profile['segment_decisions'][row['segment_id']]['whole_duty_id']='test-duty'
        reviewed=prepare_case(raw,profile)
        planned=[r for r in reviewed['fixed_segments'] if 'PLAN' in r['id']]
        self.assertEqual(len(planned),2)
        self.assertEqual({r.get('whole_duty_id') for r in planned},{'test-duty'})
        self.assertEqual({r['locked_reason'] for r in planned},
                         {'EXPLICIT_PLANNED_ACTIVITY_SCENARIO'})
        self.assertEqual({r['code'] for r in planned},{'Jo'})
        self.assertEqual([r['source_code'] for r in raw['schedule_segments'][3:]],
                         ['St','Jo','St'])

    def test_reviewed_active_morning_does_not_change_source_or_net_target(self):
        raw,profile=fixture()
        before=prepare_case(raw,profile)
        profile['planned_active_replacements']=[dict(id='test-duty-PLANAR03',
            source_segment_id='test-duty-03', expected_start='2027-01-31T05:00',
            expected_end='2027-01-31T07:00', start='2027-01-31T06:30', end='2027-01-31T07:00',
            status='SCENARIO', source='Approved active morning planning decision')]
        result=prepare_case(raw,profile)
        self.assertEqual(result['references'],before['references'])
        self.assertEqual(result['staff'],before['staff'])
        self.assertEqual(result['import_provenance'],before['import_provenance'])
        planned=next(r for r in result['fixed_segments'] if r['id']=='test-duty-PLANAR03')
        self.assertEqual((planned['code'],planned['end']-planned['start']),('Ar',30))
        from bb.flora.daily_rest import occasions
        duty=next(d for d in occasions(result,{'segments':result['fixed_segments']}) if d['id']=='test-duty')
        self.assertEqual(duty['end']-duty['start'],420)
        self.assertEqual(len(duty['rows']),4)
        profile['planned_active_replacements'][0]['start']='2027-01-31T06:00'
        with self.assertRaises(FloraImportError):prepare_case(raw,profile)

    def test_explicit_plan_preserves_source_and_before_and_absence(self):
        raw, profile = fixture()
        before = deepcopy((raw, profile))
        old = prepare_case(raw, {k:v for k,v in profile.items() if k!='planned_oncall_replacements'},
                           {'absence_mode':'preserve'})
        result = prepare_case(raw, profile, {'absence_mode':'preserve'})
        self.assertEqual((raw, profile), before)
        self.assertEqual(result['references'], old['references'])
        self.assertEqual(result['confirmed_absence_locks'], old['confirmed_absence_locks'])
        self.assertEqual(result['staff'], old['staff'])
        self.assertEqual(result['integration']['period']['id'], 'next')
        self.assertEqual(sum(r['end']-r['start'] for r in result['fixed_segments'] if r['code']=='Jo'),390)
        self.assertEqual(len(result['import_provenance']['excluded_segments']),2)
        self.assertEqual(len(result['integration']['planned_oncall_replacements']),2)
        from bb.flora.daily_rest import occasions
        duties=occasions(result, {'segments': result['fixed_segments']})
        duty=next(d for d in duties if d['id']=='test-duty')
        self.assertEqual(duty['end']-duty['start'],390)
        self.assertEqual(len(duty['rows']),3)

    def test_no_automatic_reconstruction_without_decision(self):
        raw, profile = fixture()
        del profile['planned_oncall_replacements']
        result=prepare_case(raw,profile)
        self.assertEqual(sum(r['end']-r['start'] for r in result['fixed_segments'] if r['code']=='Jo'),180)

    def test_rejects_changed_source_missing_decision_and_overlap(self):
        for field,value in [('expected_start','2027-01-31T00:01'), ('status','APPROVED'),
                            ('source',''), ('end','2027-01-31T02:01'),
                            ('start','2027-01-31T03:00'), ('id','unrelated-plan')]:
            raw,profile=fixture()
            profile['planned_oncall_replacements'][0][field]=value
            with self.subTest(field=field), self.assertRaises(FloraImportError):
                prepare_case(raw,profile)
        raw,profile=fixture()
        raw['schedule_segments'][2].update(start='2027-01-31T00:30',end='2027-01-31T01:00')
        with self.assertRaises(FloraImportError): prepare_case(raw,profile,{'absence_mode':'preserve'})

    def test_reassignment_keeps_planned_jour_with_whole_unit(self):
        raw,profile=fixture()
        profile['reassignable_units']=[dict(id='test-duty',segment_ids=['test-duty-02'])]
        result=prepare_case(raw,profile)
        unit=result['reassignable_temporary_units'][0]
        self.assertEqual(set(unit['segment_ids']),{'test-duty-02','test-duty-PLAN01','test-duty-PLAN03'})
        self.assertEqual(sum(r['end']-r['start'] for r in unit['rows']),390)

    def test_cannot_reconstruct_history_or_replace_confirmed_absence(self):
        raw,profile=fixture()
        for r in raw['schedule_segments'][3:]:
            for k in ('start','end'):r[k]=r[k].replace('2027-01-31','2027-01-28')
        for p in profile['planned_oncall_replacements']:
            for k in ('start','end','expected_start','expected_end'):
                p[k]=p[k].replace('2027-01-31','2027-01-28')
        with self.assertRaises(FloraImportError): prepare_case(raw,profile)
        for code in ('Se','Ti'):
            raw,profile=fixture()
            raw['schedule_segments'][3]['source_code']=code
            profile['segment_decisions']['test-duty-01']['expected']['source_code']=code
            with self.subTest(code=code), self.assertRaises(FloraImportError):
                prepare_case(raw,profile,{'absence_mode':'preserve'})
