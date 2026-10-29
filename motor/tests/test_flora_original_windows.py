"""Targeted solver-free tests for the versioned original-window overlay.

Private input/profile snapshots are supplied explicitly by the operator. No
business payload is stored in this test module or printed by assertions.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from bb.api import app
from bb.business_profiles import profile_for, BusinessProfileError
from bb.flora_window_binding import bind_profile, verify_input, _checked
from bb.flora_jobs import normalize_request, digest
from bb.engine_methods import prepare
from bb.flora_import import prepare_case
from bb import need_windows
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from bb.flora import _normalize


class OriginalWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(os.environ['BB_TEST_PRIVATE_SNAPSHOTS'])
        cls.raw=json.loads((root/'exact-input.json').read_text())
        cls.old=json.loads((root/'selected-profile-bound.json').read_text())
        cls.basis=json.loads((root/'positive-source-basis.json').read_text())
        cls.bound=bind_profile(cls.old,'FLORA-RADATA')
        cls.case=prepare_case(cls.raw,cls.bound)
        # Source-evidence projection only: no accepted model/result for the unresolved locks.
        stamp=lambda t:(datetime.fromisoformat(cls.case['origin'])+timedelta(minutes=t)).replace(tzinfo=ZoneInfo('Europe/Stockholm')).isoformat(timespec='minutes')
        cls.result=need_windows.export(cls.case['source_needs'],lambda n:cls.case['integration']['need_id_map'][n['id']],stamp,required=True)
        cls.result['source_basis']=cls.case['integration']['source_basis']

    def test_all_1451_bound_with_unchanged_original_values(self):
        rows=self.result['need_window_contract']['needs'];byid={n['need_id']:n for n in self.raw['customer_needs']}
        self.assertEqual(len(rows),1451);self.assertEqual(len({r['need_id'] for r in rows}),1451)
        self.assertEqual({r['need_id'] for r in rows},{n['need_id'] for n in self.raw['customer_needs'] if '2026-05-11'<=n['date'][:10]<='2026-06-07'})
        for n in rows:
            src=byid[n['need_id']]
            self.assertEqual(n['window_semantics'],'EXECUTION_WINDOW')
            self.assertEqual(n['duration_minutes'],src['duration_minutes'])
            self.assertEqual(n['personnel_count'],1)
        for n in self.case['needs']:
            self.assertEqual(n['domains'],[[n['original'],n['original_window_end']-n['duration']]])
            self.assertEqual(n['source_window_start'],n['original'])
            self.assertEqual(n['source_window_end'],n['original_window_end'])

    def test_only_window_type_flex_and_evidence_change(self):
        from bb.flora_timing_decisions import strip_verified
        restored=strip_verified(self.bound);evidence=restored.pop('window_binding')
        for nid,d in restored['need_decisions'].items():
            self.assertEqual(d.pop('window_semantics'),'EXECUTION_WINDOW')
            self.assertIs(d['flex'],False)
            d['flex']=self.old['need_decisions'][nid]['flex']
        self.assertEqual(restored,self.old)
        self.assertEqual(len(evidence['inactive_flex_need_ids']),286)
        self.assertEqual(len(evidence['inactive_k3_need_ids']),8)

    def test_all_286_extensions_and_eight_k3_exceptions_inactive(self):
        evidence=self.bound['window_binding'];ids=self.case['integration']['need_id_map']
        needs={ids[n['id']]:n for n in self.case['needs']}
        for nid in set(evidence['inactive_flex_need_ids']+evidence['inactive_k3_need_ids']):
            n=needs[nid]
            self.assertIs(n['flex'],False)
            self.assertEqual(n['domains'],[[n['original'],n['original_window_end']-n['duration']]])
        self.assertNotIn('placement_domain_contract',self.result)

    def test_both_reference_systems_and_provenance_retained(self):
        evidence=self.bound['window_binding']
        self.assertEqual(evidence['decision_ref'],'FLORA-INTERVALL-20261024')
        for n in evidence['needs']:
            self.assertEqual(n['decision_reference']['coordinate_system'],'physical_worksheet_row')
            self.assertEqual(n['original_source_reference']['coordinate_system'],'stored_source_row')
            self.assertEqual(n['decision_reference']['row'],n['app_workbook_reference']['row'])
            self.assertEqual(n['app_reference_literal'],f"03_SEKOIA_ORIGINAL rad {n['original_source_reference']['row']}")

    def test_source_basis_292_exactly_unchanged(self):
        self.assertEqual(self.result['source_basis'],self.basis)
        self.assertEqual(len(self.result['source_basis']['segments']),292)
        self.assertEqual(len({s['segment_id'] for s in self.result['source_basis']['segments']}),292)

    def test_missing_changed_or_added_input_stops_entire_binding(self):
        def row(r):return next(n for n in r['customer_needs'] if n['need_id']==self.bound['window_binding']['needs'][0]['need_id'])
        changes={
            'start':lambda r:row(r).__setitem__('window_start','00:01'),
            'end':lambda r:row(r).__setitem__('window_end','23:59'),
            'duration':lambda r:row(r).__setitem__('duration_minutes',999),
            'count':lambda r:row(r).__setitem__('personnel_count_candidate',2),
            'customer':lambda r:row(r).__setitem__('customer_id','foreign'),
            'date':lambda r:row(r).__setitem__('date','2026-06-08'),
            'reference':lambda r:row(r).__setitem__('source_ref','other'),
            'missing_reference':lambda r:row(r).pop('source_ref'),
            'missing_field':lambda r:row(r).pop('window_end'),
            'missing_need':lambda r:r['customer_needs'].remove(row(r)),
            'extra_need':lambda r:r['customer_needs'].append(dict(row(r),need_id='extra')),
            'duplicate_need':lambda r:r['customer_needs'].append(deepcopy(row(r))),
            'file_sha':lambda r:r['metadata'].__setitem__('source_file_sha256','b'*64),
            'dataset':lambda r:r['metadata'].__setitem__('dataset_id','other'),
            'organization':lambda r:r['metadata'].__setitem__('business_id','other'),
            'data_use':lambda r:r['metadata'].__setitem__('data_use','operational'),
            'timezone':lambda r:r['metadata'].__setitem__('timezone','UTC'),
            'period':lambda r:r['metadata'].__setitem__('planning_period_id','P1'),
        }
        for name,change in changes.items():
            raw=deepcopy(self.raw);change(raw)
            with self.subTest(name=name),self.assertRaises(ValueError):prepare(self.bound,normalize_request({'input':raw}))

    def test_corrupt_evidence_and_profile_fail_closed(self):
        for field,value in [('decision_ref','OTHER'),('window_semantics','START_WINDOW'),('source_file_sha256','b'*64),('needs',[])]:
            p=deepcopy(self.bound);p['window_binding'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):verify_input(self.raw,p)
        for field,value in [('flex',True),('window_semantics','START_WINDOW'),('exclusive',True)]:
            p=deepcopy(self.bound)
            nid=p['window_binding']['inactive_flex_need_ids'][0]
            p['need_decisions'][nid][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):verify_input(self.raw,p)
        p=deepcopy(self.old);p['config']['min_shift']=241
        with self.assertRaises(BusinessProfileError):bind_profile(p,'FLORA-RADATA')

    def test_placement_outside_original_rejected_before_export(self):
        n=next(n for n in self.case['needs'] if n['source_row'] in self.bound['window_binding']['inactive_flex_need_ids'])
        for start in [n['original']-1,n['original_window_end']-n['duration']+1]:
            with self.subTest(start=start),self.assertRaises(ValueError):
                _normalize(self.case,{'placements':[{'id':n['id'],'start':start}]},{})
        # Pure placement boundary validation, no fictitious full schedule.
        from bb.need_windows import check_joint
        for start in [n['original'],n['original_window_end']-n['duration']]:
            with self.assertRaisesRegex(ValueError,'NEED_DEPENDENCY_EVIDENCE_REQUIRED'):
                check_joint(self.case,{'placements':[{'id':n['id'],'start':start}]})

    def test_server_selection_and_preflight_stop_before_manager(self):
        owner='org:'+self.old['business_id']
        registry={'schema_version':'bb-business-profiles/1.0','workspaces':{owner:{
            'business_id':self.old['business_id'],'data_use':'development',
            'profile_path':'/snapshot/profile','dataset_profiles':{'FLORA-RADATA':'/snapshot/profile'}}}}
        def read(path,label):return deepcopy(registry if path=='/snapshot/registry' else self.old)
        with patch.dict(os.environ,{'BB_ENGINE_PROFILE_REGISTRY':'/snapshot/registry','BB_API_TOKEN':'synthetic-local-token','BB_ENGINE_REMOTE_ENABLED':'1'}),patch('bb.business_profiles._read',side_effect=read):
            selected,h,_,_=profile_for(owner,normalize_request({'input':self.raw}))
            self.assertEqual(selected,self.bound);self.assertEqual(h,digest(self.bound))
            with TestClient(app) as client:
                response=client.post('/api/engine/jobs',json={'input':self.raw},headers={'Authorization':'Bearer synthetic-local-token','X-BB-Job-Owner':owner,'Idempotency-Key':'STOP/BEFORE_MANAGER'})
            self.assertEqual(response.status_code,422)
            self.assertEqual(response.json()['detail']['code'],'INPUT_REVIEW_REQUIRED')
            self.assertIn('NEED_DEPENDENCY_EVIDENCE_REQUIRED: 132',response.json()['detail']['message'])

    def test_input_and_original_profile_unchanged(self):
        original=deepcopy((self.raw,self.old))
        selected=bind_profile(self.old,'FLORA-RADATA')
        verify_input(self.raw,selected)
        self.assertEqual((self.raw,self.old),original)

    def test_other_profiles_unchanged(self):
        p={'profile_id':'other'}
        self.assertIs(bind_profile(p,'other'),p)

    def test_remaining_132_event_conditions_stop_before_job_or_result(self):
        with self.assertRaisesRegex(ValueError,'NEED_DEPENDENCY_EVIDENCE_REQUIRED: 132'):
            prepare(self.bound,normalize_request({'input':self.raw}))
        with self.assertRaisesRegex(ValueError,'NEED_DEPENDENCY_EVIDENCE_REQUIRED: 132'):
            _normalize(self.case,{}, {})
        self.assertEqual(sum(n['source_window_end']-n['source_window_start']==n['duration'] for n in self.case['needs']),176)
