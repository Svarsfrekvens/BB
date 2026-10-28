"""Server-owned business bindings for the shared engine.

Uploads are inputs, never training updates. A profile is selected by the app
server's verified workspace, not by a filename, display name or client path.
No default business or inheritance from the legacy Flora profile is allowed.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import zlib

from .flora_jobs import JobInputError, canonical, digest

REGISTRY_SCHEMA = 'bb-business-profiles/1.0'
INPUT_SCHEMAS = ('bb-input/1.0', 'flora-bb-input/1.0')


class BusinessProfileError(JobInputError):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.status = code, status


def _read(path, label):
    try:
        from .profile_encoding import decode_profile
        value = decode_profile(json.loads(Path(path).read_bytes()))
    except (OSError, ValueError, TypeError, EOFError, zlib.error) as exc:
        raise BusinessProfileError('PROFILE_CONFIGURATION_UNAVAILABLE',
                                   f'{label} kunde inte läsas på servern.', 503) from exc
    if not isinstance(value, dict):
        raise BusinessProfileError('PROFILE_CONFIGURATION_INVALID', f'{label} har fel format.', 503)
    return value


def binding_for(owner):
    configured = os.environ.get('BB_ENGINE_PROFILE_REGISTRY', '').strip()
    if not configured:
        raise BusinessProfileError('BUSINESS_PROFILE_REQUIRED',
            'En separat beslutsprofil behöver anslutas för verksamhetens arbetsyta.', 503)
    registry = _read(configured, 'Verksamhetsregistret')
    if registry.get('schema_version') != REGISTRY_SCHEMA or not isinstance(registry.get('workspaces'), dict):
        raise BusinessProfileError('PROFILE_CONFIGURATION_INVALID', 'Verksamhetsregistret har fel format.', 503)
    binding = registry['workspaces'].get(owner)
    if binding is None:
        raise BusinessProfileError('BUSINESS_PROFILE_REQUIRED',
            'Arbetsytan saknar en egen ansluten beslutsprofil. Ingen annan verksamhets profil används.', 422)
    if not isinstance(binding, dict):
        raise BusinessProfileError('PROFILE_CONFIGURATION_INVALID', 'Arbetsytans profilkoppling har fel format.', 503)
    business = binding.get('business_id')
    if (not isinstance(business, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', business)
            or binding.get('data_use') not in ('development', 'operational')
            or not isinstance(binding.get('profile_path'), str)
            or not Path(binding['profile_path']).is_absolute()):
        raise BusinessProfileError('PROFILE_CONFIGURATION_INVALID', 'Arbetsytans profilkoppling är ofullständig.', 503)
    variants = binding.get('dataset_profiles', {})
    if (not isinstance(variants, dict) or any(
            not isinstance(key, str) or not key.strip() or not isinstance(path, str)
            or not Path(path).is_absolute() for key, path in variants.items())):
        raise BusinessProfileError('PROFILE_CONFIGURATION_INVALID',
                                   'Arbetsytans underlagsprofiler har fel format.', 503)
    return {**{k: binding[k] for k in ('business_id', 'data_use', 'profile_path')},
            'dataset_profiles': variants, 'request_contracts': binding.get('request_contracts', {})}


def scope_for(owner, binding):
    # Include purpose: development jobs cannot be mistaken for operational jobs.
    return 'engine:' + digest({'workspace': owner, 'business_id': binding['business_id'],
                               'data_use': binding['data_use']})


def selected_profile(owner, dataset_id):
    binding = binding_for(owner)
    # Resolve only the server's registered dataset mapping; never a client profile path/name.
    if not isinstance(dataset_id, str) or dataset_id not in binding['dataset_profiles']:
        raise BusinessProfileError('DATASET_MISMATCH', 'Underlaget saknar en exakt serverregistrerad profilkoppling.')
    variant = binding['dataset_profiles'][dataset_id]
    profile = _read(variant, 'Verksamhetens beslutsprofil')
    if (profile.get('schema_version') != 'bb-analysis-input-profile/1.0'
            or not isinstance(profile.get('profile_id'), str) or not profile['profile_id']
            or profile.get('business_id') != binding['business_id']
            or profile.get('data_use') != binding['data_use']):
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH',
            'Beslutsprofilen är inte uttryckligen kopplad till rätt verksamhet och användning.', 503)
    decision = profile.get('review_provenance')
    if not isinstance(decision, dict) or not all(isinstance(decision.get(k), str) and decision[k].strip()
                                                 for k in ('source', 'reviewed_at')):
        raise BusinessProfileError('PROFILE_REVIEW_REQUIRED',
            'Beslutsprofilen saknar dokumenterad källa och granskningsdatum.', 503)
    context = {'business_id': binding['business_id'], 'data_use': binding['data_use'],
               'profile_id': profile['profile_id'], 'automatic_learning': False}
    return profile, sha256(canonical(profile).encode()).hexdigest(), scope_for(owner, binding), context


def request_contract(owner, dataset_id, profile, profile_hash):
    binding = binding_for(owner)
    contract = binding['request_contracts'].get(dataset_id) if isinstance(binding['request_contracts'], dict) else None
    if not isinstance(contract, dict) or contract.get('version') != 'bb-request-binding/1.0':
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH', 'Serverns versionsbundna requestkontrakt saknas.', 503)
    if not isinstance(profile.get('source'), dict) or not isinstance(profile.get('applicable_periods'), list):
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH', 'Serverprofilen saknar käll- eller periodkontrakt.', 503)
    fields = ('source_file_sha256', 'dataset_id', 'business_id', 'profile_id', 'profile_hash', 'data_use', 'schema_version')
    period = contract.get('period')
    if (any(not isinstance(contract.get(k), str) or not contract[k] for k in fields)
            or not isinstance(period, dict) or any(not isinstance(period.get(k), str) or not period[k] for k in ('id','start','end','timezone'))
            or contract['schema_version'] not in INPUT_SCHEMAS
            or contract['dataset_id'] != dataset_id or contract['business_id'] != binding['business_id']
            or contract['business_id'] != profile['business_id'] or contract['data_use'] != profile['data_use']
            or contract['data_use'] != binding['data_use'] or contract['profile_id'] != profile['profile_id']
            or contract['profile_hash'] != profile_hash
            or contract['source_file_sha256'] != profile.get('source', {}).get('raw_workbook_sha256')
            or period['id'] != profile.get('period_id')
            or {k:period[k] for k in ('id','start','end')} not in profile.get('applicable_periods', [])):
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH', 'Serverns profil och requestkontrakt är inkonsistenta.', 503)
    return contract


def assert_claims(value, profile_hash, profile_id):
    # Check redundant assertions before normalization can discard them.
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r'[^a-z0-9]', '', key.lower())
            if normalized.endswith(('profilehash', 'profilesha256')) and child != profile_hash:
                raise BusinessProfileError('PROFILE_HASH_MISMATCH', 'Motstridig profilhash i requestmetadata.')
            if normalized.endswith('profileid') and child != profile_id:
                raise BusinessProfileError('PROFILE_UNKNOWN', 'Requestens profil är inte den servervalda profilen.')
            assert_claims(child, profile_hash, profile_id)
    elif isinstance(value, list):
        for child in value:
            assert_claims(child, profile_hash, profile_id)


def profile_for(owner, request):
    source = request.get('input') if isinstance(request, dict) else None
    md = source.get('metadata') if isinstance(source, dict) else None
    if not isinstance(md, dict):
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH', 'Requestmetadata saknas.')
    profile, ph, scope, context = selected_profile(owner, md.get('dataset_id'))
    contract = request_contract(owner, md.get('dataset_id'), profile, ph)
    codes = {'source_file_sha256':'SOURCE_FILE_SHA_MISMATCH', 'dataset_id':'DATASET_MISMATCH',
             'business_id':'BUSINESS_MISMATCH', 'profile_id':'PROFILE_UNKNOWN',
             'profile_hash':'PROFILE_HASH_MISMATCH', 'data_use':'DATA_USE_MISMATCH',
             'schema_version':'SCHEMA_VERSION_UNSUPPORTED'}
    for field, code in codes.items():
        if md.get(field) != contract[field]:
            raise BusinessProfileError(code, 'Requestens ' + field + ' matchar inte serverkontraktet.')
    period = md.get('period')
    if period != contract['period'] or md.get('timezone') != contract['period']['timezone']:
        raise BusinessProfileError('PERIOD_MISMATCH', 'Requestens period eller tidszon matchar inte serverkontraktet.')
    periods = md.get('periods')
    expected = {k:contract['period'][k] for k in ('id','start','end')}
    matches = [p for p in periods if isinstance(p, dict) and p.get('id') == expected['id']] if isinstance(periods,list) else []
    if matches != [expected]:
        raise BusinessProfileError('PERIOD_MISMATCH', 'Periodlistan motsäger det bundna periodkontraktet.')
    assert_claims(request, ph, profile['profile_id'])
    return profile, ph, scope, context
