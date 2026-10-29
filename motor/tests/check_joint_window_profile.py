"""Read-only preflight of an explicitly supplied private profile/input snapshot.

No source rows, credentials or profile contents are written to the report.
This is not live-service verification or a business calculation.
"""
import contextlib
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from ortools.sat.python import cp_model
from bb.api import app
from bb.flora_import import prepare_case
from bb.flora_jobs import digest

private, output = map(Path, sys.argv[1:3])
load = lambda name: json.loads((private/name).read_text())
raw, profile = load('exact-input.json'), load('selected-profile-bound.json')
original = digest([raw, profile])
business = profile['business_id']
registry = {'schema_version': 'bb-business-profiles/1.0', 'workspaces': {
    'org:'+business: {'business_id': business, 'data_use': profile['data_use'],
                     'profile_path': '/snapshot/profile.json',
                     'dataset_profiles': {raw['metadata']['dataset_id']: '/snapshot/profile.json'}}}}
counts = {}
def forbidden(name):
    counts[name] = 0
    def fail(*args, **kwargs):
        counts[name] += 1
        raise AssertionError('Forbidden: '+name)
    return fail
with contextlib.ExitStack() as stack:
    for target in ['sqlite3.connect','subprocess.Popen','socket.socket.connect','bb.engine_api.get_manager',
                   'bb.flora_jobs.get_manager','bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit',
                   'bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve','bb.availability.solve_case']:
        stack.enter_context(patch(target, side_effect=forbidden(target)))
    for name in ['solve','Solve','SearchForAllSolutions','SolveWithSolutionCallback']:
        if hasattr(cp_model.CpSolver, name):
            stack.enter_context(patch.object(cp_model.CpSolver, name, side_effect=forbidden('CpSolver.'+name)))
    # Pure import inspects existing domains; never invokes prepare/solve for an accepted job.
    case = prepare_case(raw, profile)
    needs = case['source_needs']
    stack.enter_context(patch.dict(os.environ, {'BB_API_TOKEN':'snapshot-test-token',
        'BB_ENGINE_PROFILE_REGISTRY':'/snapshot/registry.json','BB_ENGINE_REMOTE_ENABLED':'1'}))
    stack.enter_context(patch('bb.business_profiles._read', side_effect=lambda path,label:
        deepcopy(registry if path == '/snapshot/registry.json' else profile)))
    with TestClient(app) as client:
        response = client.post('/api/engine/jobs', json={'input':raw}, headers={
            'Authorization':'Bearer snapshot-test-token','X-BB-Job-Owner':'org:'+business})
    detail = response.json()['detail']
    assert response.status_code == 422 and detail['code'] == 'INPUT_REVIEW_REQUIRED'
    assert 'NEED_WINDOW_CONTRACT_REQUIRED' in detail['message']
    assert original == digest([raw, profile])
    assert not any(counts.values())
    report = dict(scope='LOCAL_SNAPSHOT_NOT_LIVE', profile_hash=digest(profile),
        source_identity=profile['source_identity'], source_file_sha256=profile['source_file_sha256'],
        period_needs=len(needs), unique_need_ids=len({n['id'] for n in needs}),
        missing_semantics=sum(n.get('window_semantics') is None for n in needs),
        flex_needs=sum(n['flex'] for n in needs),
        domains_outside_source_execution_window=sum(any(a<n['original'] or b+n['duration']>n['original_window_end'] for a,b in n['domains']) for n in needs),
        source_basis_segments=len(case['integration']['source_basis']['segments']),
        preflight_status=response.status_code, error=detail, stop_before_manager=True,
        snapshot_unchanged=True, forbidden_calls=counts)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['forbidden_calls','error']},ensure_ascii=False))
