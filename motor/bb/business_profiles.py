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
            'Arbetsytan saknar en egen ansluten beslutsprofil. Ingen annan verksamhets profil används.', 503)
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
            'dataset_profiles': variants}


def scope_for(owner, binding):
    # Include purpose: development jobs cannot be mistaken for operational jobs.
    return 'engine:' + digest({'workspace': owner, 'business_id': binding['business_id'],
                               'data_use': binding['data_use']})


def profile_for(owner, request):
    binding = binding_for(owner)
    md = request['input']['metadata']
    if md.get('business_id') != binding['business_id']:
        raise BusinessProfileError('BUSINESS_MISMATCH',
            'Underlagets verksamhets-ID stämmer inte med serverns verifierade arbetsyta.')
    if md.get('data_use') != binding['data_use']:
        raise BusinessProfileError('DATA_USE_MISMATCH',
            'Underlaget och arbetsytan måste avse samma användning: utveckling eller drift.')
    # Only server-registered variants in this authenticated business may be
    # selected. Dataset names are routing hints, never proof that rows are valid:
    # prepare_case still checks the complete reviewed mapping before queuing.
    dataset_id = md.get('dataset_id')
    variant = binding['dataset_profiles'].get(dataset_id) if isinstance(dataset_id, str) else None
    profile = _read(variant or binding['profile_path'], 'Verksamhetens beslutsprofil')
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
    profile = _source_bound_profile(profile, dataset_id)
    from .flora_window_binding import bind_profile
    profile = bind_profile(profile, dataset_id)
    context = {'business_id': binding['business_id'], 'data_use': binding['data_use'],
               'profile_id': profile['profile_id'], 'automatic_learning': False}
    return profile, sha256(canonical(profile).encode()).hexdigest(), scope_for(owner, binding), context


def _source_bound_profile(profile, dataset_id):
    """Versioned server-only two-field overlay; never write the mounted profile.

    Guard the entire existing decision profile, including whole-duty groups.
    The returned profile (and its new hash) is what the existing worker receives.
    """
    try:
        binding = json.loads(Path(__file__).with_name('flora_source_binding.json').read_text())
        fields = {'schema_version', 'profile_id', 'business_id', 'data_use', 'dataset_id',
                  'base_profile_sha256', 'source_identity', 'source_file_sha256'}
        if (not isinstance(binding, dict) or set(binding) != fields
                or binding.get('schema_version') != 'bb-source-profile-binding/1.0'):
            raise ValueError('schema')
        if profile.get('profile_id') != binding['profile_id']:
            return profile
        if any(profile.get(k) != binding[k] for k in ('business_id', 'data_use')):
            raise ValueError('owner')
        additions = {k: binding[k] for k in ('source_identity', 'source_file_sha256')}
        if any(not isinstance(v, str) or not re.fullmatch(r'[a-f0-9]{64}', v) for v in additions.values()):
            raise ValueError('hash')
        if any(k in profile and profile[k] != v for k, v in additions.items()):
            raise ValueError('existing binding')
        unchanged = {k: v for k, v in profile.items() if k not in additions}
        if digest(unchanged) != binding['base_profile_sha256']:
            raise ValueError('decision profile changed')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise BusinessProfileError('PROFILE_BINDING_MISMATCH',
            'Serverns källbindning matchar inte den granskade beslutsprofilen.', 503) from exc
    if dataset_id != binding['dataset_id']:
        raise BusinessProfileError('DATASET_MISMATCH', 'Underlaget matchar inte profilens granskade dataset.')
    return {**profile, **additions}
