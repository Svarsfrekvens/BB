"""Shared, workspace-scoped engine API. Authentication stays in bb.api.

The app server must authenticate the user and authorize workspace membership
before sending X-BB-Job-Owner. Never put the service token in browser code.
"""
import os
import re

from fastapi import APIRouter, HTTPException, Request

from .business_profiles import (BusinessProfileError, INPUT_SCHEMAS, binding_for,
                                profile_for, selected_profile, request_contract, scope_for)
from .flora_api import json_body
from .flora_jobs import IdempotencyConflict, JobInputError, get_manager, normalize_request
from .rule_policy import shared_principles

router = APIRouter()


def verified_owner(request):
    local = request.client and request.client.host in ('127.0.0.1', '::1', 'testclient')
    if not local and os.environ.get('BB_ENGINE_REMOTE_ENABLED') != '1':
        raise HTTPException(403, 'Den gemensamma motorn är inte aktiverad för externa anrop.')
    owner = request.headers.get('x-bb-job-owner', '')
    if not re.fullmatch(r'[A-Za-z0-9_.:@-]{1,160}', owner):
        raise HTTPException(403, 'Serverns verifierade arbetsyta saknas.')
    if not local and not os.environ.get('BB_API_TOKEN'):
        raise HTTPException(403, 'Beräkningstjänsten saknar skyddad anslutning.')
    return owner


def profile_error(exc):
    return HTTPException(exc.status, {'code': exc.code, 'message': str(exc)})


@router.get('/api/engine/capabilities')
async def capabilities(request: Request):
    owner = verified_owner(request)
    report = dict(schema_version='bb-engine-capabilities/1.0', input_schemas=list(INPUT_SCHEMAS),
                  shared_engine=True, automatic_learning=False,
                  workspace_scoped_profiles=True, raw_excel_import=False,
                  review_required=True, profile_status='NOT_CONFIGURED')
    report['shared_principles']=shared_principles()
    try:
        binding = binding_for(owner)
        # Read the profile as well: an environment variable alone is not readiness.
        metadata = {**binding, 'dataset_id': request.query_params.get('dataset_id')}
        profile, ph, _, context = selected_profile(owner, metadata['dataset_id'])
        request_contract(owner, metadata['dataset_id'], profile, ph)
        report.update(business_id=context['business_id'], data_use=context['data_use'],
                      profile_status='CONFIGURED_INPUT_REVIEW_REQUIRED')
        if profile.get('engine_strategy') == 'reviewed-availability/1.0':
            report['recommended_search_seconds'] = 300
    except BusinessProfileError as exc:
        report.update(profile_error_code=exc.code, profile_message=str(exc))
    return report


@router.post('/api/engine/jobs', status_code=202)
async def create_job(request: Request):
    owner = verified_owner(request)
    try:
        # The shared route matches the app gateway's bounded 8 MiB transfer.
        # The legacy Flora endpoint retains its existing 6 MiB limit.
        raw_body = await json_body(request, max_body=8*1024*1024)
        profile, profile_hash, scope, context = profile_for(owner, raw_body)
        body = normalize_request(raw_body)
        # Fail changed dates/IDs/missing decisions before a job is queued. This
        # pure adapter never runs the solver or changes the submitted workbook.
        from .engine_methods import prepare
        prepare(profile, body)
        client_key = request.headers.get('idempotency-key') or None
        if client_key and not re.fullmatch(r'[A-Za-z0-9_.:@-]{1,160}', client_key):
            raise JobInputError('Ogiltig körningsnyckel.')
        body['engine_context'] = context  # server-generated; client cannot override
        manager = get_manager()
        job, created = manager.store.submit(scope, body, profile, profile_hash, client_key)
        manager.wake()
        return {**job, 'deduplicated': not created, 'engine_context': context}
    except BusinessProfileError as exc:
        raise profile_error(exc) from exc
    except IdempotencyConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except JobInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, {'code': 'INPUT_REVIEW_REQUIRED', 'message': str(exc)}) from exc
    except (KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(422, {'code': 'INPUT_REVIEW_REQUIRED',
                                 'message': 'Underlaget eller beslutsprofilen är ofullständig.'}) from exc


@router.get('/api/engine/jobs/{job_id}')
async def read_job(job_id: str, request: Request):
    owner = verified_owner(request)
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    try:
        scope = scope_for(owner, binding_for(owner))
        job = get_manager().store.get(job_id, scope)
    except BusinessProfileError as exc:
        raise profile_error(exc) from exc
    except JobInputError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not job:
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    return job


@router.get('/api/engine/jobs/{job_id}/submitted-source')
async def read_submitted_source(job_id: str, request: Request):
    """Private, immutable job input for comparison before any working-copy transfer."""
    owner = verified_owner(request)
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    try:
        scope = scope_for(owner, binding_for(owner))
        source = get_manager().store.submitted_source(job_id, scope)
    except BusinessProfileError as exc:
        raise profile_error(exc) from exc
    except JobInputError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not source:
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    return source


@router.get('/api/engine/jobs/{job_id}/pass-preflight')
async def read_pass_preflight(job_id: str, request: Request):
    """Aggregate current profile evidence for this saved input, without solving."""
    owner = verified_owner(request)
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    try:
        binding = binding_for(owner)
        source = get_manager().store.submitted_source(job_id, scope_for(owner, binding))
        if source is None:
            raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
        profile, profile_hash, _, _ = profile_for(owner, source['request'])
        from .ap12_preflight import pass_mapping_preflight
        return pass_mapping_preflight(source['request'], profile,
                                      saved_profile_hash=source['profile_hash'],
                                      current_profile_hash=profile_hash,
                                      input_hash=source['input_hash'])
    except BusinessProfileError as exc:
        raise profile_error(exc) from exc
    except JobInputError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, {'code': 'PROFILE_PREFLIGHT_INCOMPLETE',
                                 'message': 'Profilen kan inte förkontrolleras mot sparad körningsindata.'}) from exc


@router.get('/api/engine/profile-attestation')
async def profile_attestation(request: Request):
    """Authenticated server-to-server, owner scoped, allowlisted read-only proof."""
    from hashlib import sha256
    from pathlib import Path
    import json
    from .profile_encoding import decode_profile
    from .flora_jobs import digest
    owner = verified_owner(request)
    dataset = request.query_params.get('dataset_id')
    try:
        profile, ph, _, context = selected_profile(owner, dataset)
        contract = request_contract(owner, dataset, profile, ph)
        binding = binding_for(owner)
        raw = Path(binding['dataset_profiles'][dataset]).read_bytes()
        if digest(decode_profile(json.loads(raw))) != ph:
            raise BusinessProfileError('PROFILE_BINDING_MISMATCH', 'Profilen ändrades under läskontrollen.', 503)
        return dict(schema_version='bb-profile-attestation/1.0', profile_file_sha256=sha256(raw).hexdigest(),
                    profile_hash=ph, profile_id=context['profile_id'], business_id=context['business_id'],
                    dataset_id=dataset, period=contract['period'], data_use=context['data_use'],
                    motor_commit=os.environ.get('RENDER_GIT_COMMIT'), contract_version=contract['version'])
    except BusinessProfileError as exc:
        raise profile_error(exc) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(503, {'code':'PROFILE_CONFIGURATION_UNAVAILABLE'}) from exc
