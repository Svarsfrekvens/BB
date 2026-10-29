"""Single synthetic export check. Production source is imported, never edited.

Only storage and the solve dispatch are replaced in memory. The latter calls the
existing solver-free fixture adapter. run_worker supplies actual provenance.
"""
from pathlib import Path
import contextlib, hashlib, json, os, socket, sqlite3, subprocess, sys
from copy import deepcopy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT/'motor'), str(ROOT/'motor/tests')]
from bb import flora_jobs as jobs
from bb import business_profiles
from test_typed_windows_contract import flora_fixture, flora_result
from bb.availability_import import source_identity
import unittest
from ortools.sat.python import cp_model

COMMIT = 'synthetic-local-need-window-patch'  # Fixture build marker, not a live deployment.
counts = {}
def blocked(name):
    counts[name] = 0
    def fail(*args, **kwargs):
        counts[name] += 1
        raise AssertionError('Forbidden: '+name)
    return fail

class MemoryResultSink:
    """No database or JobStore is created. Capture production serialization only."""
    def __init__(self, row):
        self.row = row
        self.captured = None
        self.captures = 0
    @contextlib.contextmanager
    def connect(self):
        yield self
    def execute(self, query, params):
        if query.startswith('SELECT * FROM jobs WHERE id='):
            assert params == (self.row['id'], 'synthetic-lease')
            return self
        if query.startswith("UPDATE jobs SET status='succeeded'"):
            finished, result, identity, lease = params
            assert identity == self.row['id'] and lease == 'synthetic-lease'
            self.captured = result
            self.captures += 1
            self.row.update(status='succeeded', finished_at=finished, result_json=result)
            return self
        raise AssertionError('Unexpected storage operation')
    def fetchone(self):
        return self.row
    def failure(self, *args):
        raise AssertionError('Worker failed: '+repr(args))

def export_one(mode, duration, start, identity):
    body, profile = flora_fixture(mode, duration)
    body['input']['vc_answers'] = []
    # Second period need remains unplaced; a history need must not enter the contract.
    extra=deepcopy(body['input']['customer_needs'][0]);extra.update(need_id='unplaced-need',window_semantics='EXECUTION_WINDOW',duration_minutes=10)
    body['input']['customer_needs'].append(extra)
    decision=deepcopy(profile['need_decisions']['source-need']);decision['engine_id']='unplaced-engine'
    profile['need_decisions']['unplaced-need']=decision
    history=deepcopy(extra);history.update(need_id='history-need',date='2027-01-03')
    body['input']['customer_needs'].append(history)
    profile['source_identity']=source_identity(body['input'])
    profile['source_file_sha256']=body['input']['metadata']['source_file_sha256']
    before = deepcopy((body, profile))
    request = jobs.normalize_request(body)
    registry = {'schema_version': business_profiles.REGISTRY_SCHEMA, 'workspaces': {
        'org:synthetic-window': {'business_id':'synthetic-window', 'data_use':'development',
            'profile_path':'/synthetic/profile.json'}}}
    with patch.dict(os.environ, {'BB_ENGINE_PROFILE_REGISTRY':'/synthetic/registry.json'}), \
            patch.object(business_profiles, '_read', side_effect=lambda path, label: deepcopy(registry if 'registry' in path else profile)):
        selected, profile_hash, scope, context = business_profiles.profile_for('org:synthetic-window', request)
    # Same server-generated context assignment as engine_api.create_job; no POST.
    request['engine_context'] = context
    row = dict(id=identity, status='running', input_hash=jobs.digest(request['input']),
        profile_hash=profile_hash, request_json=jobs.canonical(request), profile_json=jobs.canonical(selected),
        method_hash=jobs.method_fingerprint(), build_commit=COMMIT,
        created_at='2027-01-04T00:00:00+00:00', started_at='2027-01-04T00:00:00+00:00',
        finished_at=None, result_json=None, error_json=None)
    sink = MemoryResultSink(row)
    adapter_calls = []
    def deterministic_adapter(selected_profile, case, normalized_request):
        assert selected_profile == profile
        adapter_calls.append(mode)
        # Existing adapter: full source-imported schedule, independent validator,
        # and real _normalize/export. Never calls a solver.
        return flora_result(case, start)[1]
    public = jobs.JobStore.public
    with patch.object(jobs, 'JobStore', return_value=sink), \
            patch('bb.engine_methods.solve', side_effect=deterministic_adapter), \
            patch.dict(os.environ, {'RENDER_GIT_COMMIT': COMMIT}), \
            patch.object(jobs.time, 'monotonic', return_value=0), \
            patch.object(jobs, 'now', return_value='2027-01-04T00:00:00+00:00'):
        jobs.run_worker('/synthetic/no-database', identity, 'synthetic-lease')
    assert sink.captures == 1 and adapter_calls == [mode]
    assert (body, profile) == before
    raw = sink.captured.encode()
    result = json.loads(raw)
    assert result['validation']['overall'] == 'UNKNOWN'
    assert not result['validation']['violations']
    assert result['review_required'] is True and result['business_schedule_approved'] is False
    assert result['provenance']['build_commit'] == COMMIT
    assert result['provenance']['profile_hash'] == jobs.digest(profile)
    assert result['input_hash'] == jobs.digest(body['input'])
    assert 'placement_domain_contract' not in result
    directory = OUT / mode.lower()
    directory.mkdir(exist_ok=True)
    (directory/'result.raw.json').write_bytes(raw)
    (directory/'job.raw.json').write_text(jobs.canonical(public(sink.row)))
    (directory/'input.json').write_text(jobs.canonical(body['input']))
    (directory/'profile.fixture.json').write_text(jobs.canonical(profile))
    return {'mode':mode, 'directory':directory.name, 'raw_result_sha256':hashlib.sha256(raw).hexdigest(),
        'raw_job_sha256':hashlib.sha256((directory/'job.raw.json').read_bytes()).hexdigest(),
        'profile_hash':profile_hash, 'input_hash':result['input_hash'], 'scope':scope,
        'adapter_calls':1, 'memory_result_captures':1,
        'validation':'UNKNOWN', 'placement_domain_contract':'ABSENT_NOT_REQUIRED_FOR_SOURCE_BOUNDED_PLACEMENT'}

with contextlib.ExitStack() as stack:
    for target in ['sqlite3.connect','subprocess.Popen','socket.socket.connect',
        'bb.flora_jobs.get_manager','bb.engine_api.get_manager','bb.flora_jobs.JobStore.__init__',
        'bb.flora_jobs.JobStore.submit','bb.flora.solve_case','bb.flora._solve',
        'bb.availability.solve_case']:
        stack.enter_context(patch(target, side_effect=blocked(target)))
    for method in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
        if hasattr(cp_model.CpSolver,method):
            stack.enter_context(patch.object(cp_model.CpSolver,method,side_effect=blocked('CpSolver.'+method)))
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_joint_window_export','test_source_basis','test_source_profile_binding','test_profile_encoding','test_typed_windows_contract','test_flora_import.ImportTest',
        'test_availability_engine.AvailabilityMethodTests.test_source_changes_require_explicit_review_even_with_same_file_hash',
        'test_availability_engine.AvailabilityMethodTests.test_a_new_source_hash_cannot_rebind_stale_effective_need_times',
        'test_availability_engine.AvailabilityMethodTests.test_routing_metadata_and_row_order_do_not_change_source_identity'])
    tested=unittest.TextTestRunner(verbosity=2).run(suite)
    from run_typed_windows_checks import probes
    legacy_probes=probes()
    # Same routing/status/idempotency probes with explicit window evidence.
    from test_business_engine import business_sample
    def typed_sample(*args):
        body,profile=business_sample(*args)
        for n in body['input']['customer_needs']:n['window_semantics']='EXECUTION_WINDOW'
        return body,profile
    with patch('run_typed_windows_checks.business_sample',side_effect=typed_sample):typed_probes=probes()
    if not tested.wasSuccessful():raise SystemExit(1)
    results = [export_one('START_WINDOW',60,560,'a'*32),
               export_one('EXECUTION_WINDOW',10,550,'b'*32)]
    assert not any(counts.values())
    report = {'fixture_build_marker':COMMIT, 'base_commit':'d60b518922040771016a6335f8d1310a6fbe249a', 'tests':{'run':tested.testsRun,'failures':len(tested.failures),'errors':len(tested.errors)},'legacy_probes':legacy_probes,'typed_probes':typed_probes,'exports':results,'forbidden_calls':counts,
        'real_jobs_created':0,'database_connections':0,'actual_solver_calls':0,
        'transport':'no network; worker storage is an in-memory result sink'}
    (OUT/'motor-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
