from copy import deepcopy
import tempfile
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from bb.availability_profile import build_profile
from bb.business_profiles import _read, BusinessProfileError
from bb.flora_jobs import digest
from bb.profile_encoding import encode_profile, decode_profile, MAX_BYTES
from availability_fixtures import sample


class ProfileEncodingTests(unittest.TestCase):
    def test_private_profile_roundtrip_is_deterministic_and_keeps_canonical_identity(self):
        _, profile=sample()
        encoded=encode_profile(profile)
        self.assertEqual(encoded,encode_profile(profile))
        self.assertEqual(decode_profile(encoded),profile)
        self.assertEqual(digest(decode_profile(encoded)),digest(profile))
        with tempfile.TemporaryDirectory() as root:
            file=Path(root)/'profile.json';file.write_text(json.dumps(encoded))
            self.assertEqual(_read(file,'Testprofil'),profile)
            encoded['sha256']='0'*64;file.write_text(json.dumps(encoded))
            with self.assertRaises(BusinessProfileError):_read(file,'Testprofil')

    def test_corruption_declared_limits_and_nested_wrappers_fail_closed(self):
        _, profile=sample(); valid=encode_profile(profile)
        for key,value in [('data','not base64'),('uncompressed_bytes',MAX_BYTES+1),
                          ('uncompressed_bytes',True),('uncompressed_bytes',3),('encoding','unknown')]:
            invalid=deepcopy(valid);invalid[key]=value
            with self.assertRaises((ValueError,OSError,EOFError)):decode_profile(invalid)
        with self.assertRaises(ValueError):decode_profile(encode_profile(valid))

    def test_builder_validates_without_a_search_and_preserves_input(self):
        request, original=sample(); case=original['reviewed_case']
        case['needs'][0]['original_fields']={'fixture':'Original source prose retained in input/archive'}
        before=deepcopy((request,case))
        with patch('ortools.sat.python.cp_model.CpModel',side_effect=AssertionError('No search during profile preparation')):
            profile=build_profile(request['input'],case,business_id='synthetic-a',profile_id='synthetic-build',
                review_source='Synthetic reviewed source',reviewed_at='2026-10-19')
        self.assertNotIn('original_fields',profile['reviewed_case']['needs'][0])
        self.assertEqual(profile['source_identity'],original['source_identity'])
        self.assertEqual((request,case),before)
