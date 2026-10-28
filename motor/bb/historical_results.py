"""Historical artefact receipts, never jobs. No solver, queue, or workspace writes.

The operator-installed manifest is the trust root; the HTTP caller supplies only
its artefact key. Files and profiles never come from client paths or self-attested
hashes. The separate registrar credential is NOT the app gateway credential.
"""
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from hashlib import sha256

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .business_profiles import binding_for, selected_profile, scope_for, BusinessProfileError
from .engine_api import verified_owner
from .flora_api import json_body
from .flora_jobs import canonical, digest, now

router = APIRouter()
SCHEMA = 'bb-historical-result/1.0'
MANIFEST_SCHEMA = 'bb-historical-artifacts/1.0'
ID = re.compile(r'hist_[a-f0-9]{32}')
SHA = re.compile(r'[a-f0-9]{64}')
MAX_FILE = 32 * 1024 * 1024


def reject(status=422):
    # Never expose private profile errors, file paths, rows or credentials.
    raise HTTPException(status, 'Historiskt resultat kunde inte kopplas till behörig verksamhet och betrott underlag.')


def authenticated_owner(request, register=False):
    token = os.environ.get('BB_API_TOKEN', '')
    if not token or not hmac.compare_digest(request.headers.get('authorization', ''), 'Bearer ' + token):
        reject(401)
    owner = verified_owner(request)
    if register:
        registrar = os.environ.get('BB_HISTORICAL_REGISTRAR_TOKEN', '')
        if not registrar or hmac.compare_digest(registrar, token):
            reject(503)
        if not hmac.compare_digest(request.headers.get('x-bb-historical-registrar', ''), registrar):
            reject(403)
    return owner


def read_bytes(filename):
    p = Path(filename)
    if not p.is_absolute():
        reject(503)
    with p.open('rb') as f:
        data = f.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        reject(413)
    return data


def checked_file(spec):
    if not isinstance(spec, dict) or set(spec) != {'path', 'sha256'} or not SHA.fullmatch(spec['sha256']):
        reject(503)
    data = read_bytes(spec['path'])
    if sha256(data).hexdigest() != spec['sha256']:
        reject()
    return data


def artefact(owner, artifact_id):
    manifest = json.loads(read_bytes(os.environ.get('BB_HISTORICAL_ARTIFACTS', '')))
    if manifest.get('schema_version') != MANIFEST_SCHEMA:
        reject(503)
    entry = manifest['artifacts'].get(artifact_id)
    if not isinstance(entry, dict) or entry.get('owner') != owner:
        reject(404)
    if entry.get('review', {}).get('reviewed_by') in (None, '') or entry.get('review', {}).get('evidence') in (None, ''):
        reject(503)
    binding = binding_for(owner)
    if binding['data_use'] != 'development' or entry['business_id'] != binding['business_id']:
        reject(403)
    # Selection metadata is separate; the original historical input is never rebound.
    source = checked_file(entry['source_file'])
    input_bytes = checked_file(entry['input_file'])
    result_bytes = checked_file(entry['result_file'])
    source_hash = sha256(source).hexdigest()
    raw = json.loads(input_bytes)
    result = json.loads(result_bytes)
    if (digest(raw) != entry['input_hash'] or raw['metadata'].get('dataset_id') != entry['dataset_id']
            or raw['metadata'].get('source_file_sha256') != source_hash):
        reject()
    profile, profile_hash, scope, context = selected_profile(owner, entry['dataset_id'])
    if (profile_hash != entry['profile_hash'] or context['profile_id'] != entry['profile_id']
            or profile.get('engine_strategy') not in (None, 'flora-reassignment/1.0')):
        reject()
    if (result.get('schema_version') != 'bb-engine-run/1.0' or result.get('review_required') is not True
            or result.get('business_schedule_approved') is not False
            or 'input_hash' in result or 'provenance' in result):
        reject()
    # Reuse reviewed Flora mapping and exporter. This checks source/period/profile
    # and exact rows/contracts; it neither solves nor upgrades independent validation.
    from .flora_import import prepare_case
    from .flora import _normalize
    case = prepare_case(raw, profile, entry.get('scenario', {}))
    expected = _normalize(case, result['raw_solution'], result['validation'])
    if result['period'] != entry['period'] or expected['period'] != entry['period']:
        reject()
    for field in ('period', 'persons', 'schedule', 'need_window_contract',
                  'placement_domain_contract', 'unassigned_need_ids'):
        if result.get(field) != expected[field]:
            reject()
    origin = entry['origin']
    if set(origin) != {'kind', 'computed_at', 'solver_commit', 'export_commit'} or origin['kind'] != 'historical-local':
        reject(503)
    for key in ('solver_commit', 'export_commit'):
        if origin[key] is not None and not re.fullmatch(r'[a-f0-9]{40}', origin[key]):
            reject(503)
    if origin['computed_at'] is not None:
        from datetime import datetime
        if not isinstance(origin['computed_at'], str) or datetime.fromisoformat(origin['computed_at']).tzinfo is None:
            reject(503)
    receipt = dict(schema_version=SCHEMA, origin=origin, review_required=True,
                   business_schedule_approved=False, binding=dict(
                       business_id=binding['business_id'], data_use='development', dataset_id=entry['dataset_id'],
                       source_file_sha256=source_hash, input_hash=entry['input_hash'],
                       profile_id=entry['profile_id'], profile_hash=profile_hash,
                       result_sha256=sha256(result_bytes).hexdigest(), period=entry['period']))
    return scope, receipt, result_bytes


def database():
    filename = os.environ.get('BB_HISTORICAL_DB', '')
    if not filename or not Path(filename).is_absolute():
        reject(503)
    if Path(filename).resolve() == Path(os.environ.get('BB_JOB_DB', 'jobs.sqlite3')).resolve():
        reject(503)
    return filename


def register(scope, receipt, result_bytes):
    # All artefact checks completed BEFORE opening/creating the separate database.
    identity = digest(receipt)
    filename = database()
    # Private rows must not depend on an operator's default umask. Existing file
    # permissions are not changed here; installation requires a private directory.
    fd = os.open(filename, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    with sqlite3.connect(filename, timeout=10) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS historical_results (
            registration_id TEXT PRIMARY KEY, scope TEXT NOT NULL,
            result_hash TEXT NOT NULL, identity TEXT NOT NULL,
            receipt_json TEXT NOT NULL, result_bytes BLOB NOT NULL,
            UNIQUE(scope, result_hash))''')
        con.execute('BEGIN IMMEDIATE')
        old = con.execute('SELECT identity,receipt_json FROM historical_results WHERE scope=? AND result_hash=?',
                          (scope, receipt['binding']['result_sha256'])).fetchone()
        if old:
            if old[0] != identity:
                reject(409)
            return json.loads(old[1]), False
        record = {**receipt, 'registration_id': 'hist_' + uuid.uuid4().hex, 'registered_at': now()}
        con.execute('INSERT INTO historical_results VALUES(?,?,?,?,?,?)', (
            record['registration_id'], scope, receipt['binding']['result_sha256'], identity,
            canonical(record), result_bytes))
        return record, True


def read_record(owner, registration_id):
    binding = binding_for(owner)
    if binding['data_use'] != 'development':
        reject(403)
    scope = scope_for(owner, binding)
    # Read-only SQLite URI: a GET never creates storage or a job.
    uri = Path(database()).resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as con:
        row = con.execute('SELECT receipt_json,result_bytes,identity FROM historical_results WHERE registration_id=? AND scope=?',
                          (registration_id, scope)).fetchone()
    if row is None:
        reject(404)
    receipt, content, identity = json.loads(row[0]), row[1], row[2]
    basis = {k: v for k, v in receipt.items() if k not in ('registration_id', 'registered_at')}
    if (digest(basis) != identity or receipt['registration_id'] != registration_id
            or receipt['binding']['business_id'] != binding['business_id']
            or sha256(content).hexdigest() != receipt['binding']['result_sha256']):
        reject(503)
    # UTF-8 string preserves original bytes through JSON escaping; clients hash
    # the encoded string before parsing. No lossy JSON reserialization hash.
    return {**receipt, 'result_json': content.decode('utf-8')}


@router.post('/api/engine/historical-results')
async def register_historical(request: Request):
    owner = authenticated_owner(request, register=True)
    try:
        body = await json_body(request, max_body=2048)
        if (not isinstance(body, dict) or set(body) != {'artifact_id'}
                or not isinstance(body['artifact_id'], str)
                or not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', body['artifact_id'])):
            reject()
        scope, receipt, data = artefact(owner, body['artifact_id'])
        record, created = register(scope, receipt, data)
        return JSONResponse(record, status_code=201 if created else 200)
    except BusinessProfileError:
        reject(403)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error):
        reject()


@router.get('/api/engine/historical-results/{registration_id}')
async def read_historical(registration_id: str, request: Request):
    owner = authenticated_owner(request)
    if not ID.fullmatch(registration_id):
        reject(404)
    try:
        return read_record(owner, registration_id)
    except BusinessProfileError:
        reject(403)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, sqlite3.Error):
        reject(503)
