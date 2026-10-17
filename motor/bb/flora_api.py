"""Additive Flora proposal API; the pilot optimizer and its queue stay separate.

The containing app retains its existing token middleware on every /api route.
An organization owner is supplied only by a separately authenticated app server.
Local mode is loopback-only; an external Flora pilot must be explicitly enabled.
"""
from contextlib import asynccontextmanager
import json
import os
import re

from fastapi import APIRouter, HTTPException, Request

MAX_BODY = 6 * 1024 * 1024


@asynccontextmanager
async def lifespan(router):
    yield
    from .flora_jobs import close_managers
    close_managers()


router = APIRouter(lifespan=lifespan)


def capabilities():
    from .flora_jobs import load_profile, JobInputError
    try:
        profile, _ = load_profile()
        readable = profile.get('schema_version') == 'bb-analysis-input-profile/1.0'
    except JobInputError:
        readable = False
    return dict(jobs=True, profile_configured=readable,
                remote_enabled=os.environ.get('BB_FLORA_REMOTE_ENABLED') == '1')


async def json_body(request):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > MAX_BODY:
            raise HTTPException(413, 'För stort underlag.')
    try:
        return json.loads(content)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, 'Anropet innehåller inte giltig JSON.') from exc


def job_owner(request):
    local = request.client and request.client.host in ('127.0.0.1', '::1', 'testclient')
    token = os.environ.get('BB_API_TOKEN', '')
    if not local and os.environ.get('BB_FLORA_REMOTE_ENABLED') != '1':
        raise HTTPException(403, 'Floras beräkning är endast aktiverad i lokal testmiljö.')
    if token:
        owner = request.headers.get('x-bb-job-owner', '')
        if not re.fullmatch(r'[A-Za-z0-9_.:@-]{1,160}', owner):
            raise HTTPException(403, 'Serverns verifierade arbetsyta saknas.')
        return owner
    if local:
        return 'local'
    raise HTTPException(403, 'Beräkningstjänsten saknar skyddad anslutning.')


@router.post('/api/flora/jobs', status_code=202)
async def create_flora_job(request: Request):
    from .flora_jobs import (get_manager, load_profile, normalize_request,
                             JobInputError, IdempotencyConflict)
    owner = job_owner(request)
    try:
        body = normalize_request(await json_body(request))
        metadata = body['input']['metadata']
        if metadata.get('schema_version') == 'bb-input/1.0' or metadata.get('business_id') is not None:
            raise JobInputError('Verksamhetskopplat underlag ska skickas till /api/engine/jobs med en egen beslutsprofil.')
        client_key = request.headers.get('idempotency-key') or None
        if client_key and not re.fullmatch(r'[A-Za-z0-9_.:@-]{1,160}', client_key):
            raise JobInputError('Ogiltig körningsnyckel.')
        profile, profile_hash = load_profile()
        manager = get_manager()
        job, created = manager.store.submit(owner, body, profile, profile_hash, client_key)
        manager.wake()
        return {**job, 'deduplicated': not created}
    except IdempotencyConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except JobInputError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, 'Underlaget innehåller värden som inte kan skickas till beräkningen.') from exc


@router.get('/api/flora/jobs/{job_id}')
async def read_flora_job(job_id: str, request: Request):
    from .flora_jobs import get_manager, JobInputError
    owner = job_owner(request)
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    try:
        job = get_manager().store.get(job_id, owner)
    except JobInputError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not job:
        raise HTTPException(404, 'Körningen finns inte i den här arbetsytan.')
    return job
