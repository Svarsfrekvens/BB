"""Two-field server overlay tests; synthetic profiles only, no server writes."""
import json
from copy import deepcopy
import unittest
from unittest.mock import patch
from bb.business_profiles import _source_bound_profile, BusinessProfileError
from bb.flora_jobs import digest
from test_source_basis import reviewed_fixture


class SourceProfileBindingTests(unittest.TestCase):
    def fixture(self):
        body,profile=reviewed_fixture()
        additions={k:profile.pop(k) for k in ['source_identity','source_file_sha256']}
        binding=dict(schema_version='bb-source-profile-binding/1.0',profile_id=profile['profile_id'],
            business_id=profile['business_id'],data_use=profile['data_use'],dataset_id=body['input']['metadata']['dataset_id'],
            base_profile_sha256=digest(profile),**additions)
        return body,profile,binding

    def apply(self,profile,binding,dataset=None):
        with patch('bb.business_profiles.Path.read_text',return_value=json.dumps(binding)):
            return _source_bound_profile(profile,dataset or binding['dataset_id'])

    def test_only_two_fields_added_and_original_not_mutated(self):
        body,profile,binding=self.fixture();before=deepcopy(profile)
        after=self.apply(profile,binding)
        self.assertEqual(set(after)-set(profile),{'source_identity','source_file_sha256'})
        self.assertEqual({k:v for k,v in after.items() if k in profile},profile)
        self.assertEqual(profile,before)

    def test_idempotent_for_already_bound_profile(self):
        body,profile,binding=self.fixture();after=self.apply(profile,binding)
        self.assertEqual(self.apply(after,binding),after)

    def test_other_profile_is_unchanged(self):
        body,profile,binding=self.fixture();profile['profile_id']='other'
        self.assertIs(self.apply(profile,binding),profile)

    def test_changed_rule_or_group_or_prior_hash_fails_closed(self):
        body,profile,binding=self.fixture()
        for change in ['config','segment_decisions','source_identity']:
            changed=deepcopy(profile);changed[change]={} if change!='source_identity' else 'b'*64
            with self.subTest(change=change),self.assertRaises(BusinessProfileError) as caught:self.apply(changed,binding)
            self.assertEqual(caught.exception.status,503)

    def test_wrong_dataset_is_client_error(self):
        body,profile,binding=self.fixture()
        with self.assertRaises(BusinessProfileError) as caught:self.apply(profile,binding,'foreign')
        self.assertEqual(caught.exception.status,422);self.assertEqual(caught.exception.code,'DATASET_MISMATCH')

    def test_wrong_business_or_purpose_does_not_receive_overlay(self):
        body,profile,binding=self.fixture()
        for key,value in [('business_id','foreign'),('data_use','operational')]:
            changed=deepcopy(profile);changed[key]=value
            with self.subTest(key=key),self.assertRaises(BusinessProfileError):self.apply(changed,binding)

    def test_incomplete_or_malformed_server_manifest_is_configuration_error(self):
        body,profile,binding=self.fixture()
        missing=deepcopy(binding);missing.pop('dataset_id')
        for bad in [[],missing]:
            with patch('bb.business_profiles.Path.read_text',return_value=json.dumps(bad)):
                with self.assertRaises(BusinessProfileError) as caught:_source_bound_profile(profile,binding['dataset_id'])
                self.assertEqual(caught.exception.status,503)
