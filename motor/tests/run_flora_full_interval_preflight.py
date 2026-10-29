"""Read private snapshots, select the local server profile and preflight all needs.

No HTTP submission, database, manager, solver or schedule. Output is private
per-need source-contract evidence, not an engine result or a job request.
"""
import argparse
import contextlib
import json
import hashlib
import os
from pathlib import Path
import sys
from copy import deepcopy
from unittest.mock import patch
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(repo/'motor')]
    source = Path(args.private)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    private = out/'private'
    private.mkdir(exist_ok=True, mode=0o700)
    raw = json.loads((source/'exact-input.json').read_text())
    original_profile = json.loads((source/'selected-profile-bound.json').read_text())
    basis = json.loads((source/'positive-source-basis.json').read_text())
    before = deepcopy((raw, original_profile))
    from bb import flora_jobs as jobs, need_windows
    from bb.business_profiles import profile_for
    from bb.engine_methods import prepare
    from ortools.sat.python import cp_model
    calls = {}
    def blocked(name):
        calls[name] = 0
        def fail(*a, **kw):
            calls[name] += 1
            raise AssertionError('Forbidden '+name)
        return fail
    owner = 'org:'+original_profile['business_id']
    registry = {'schema_version':'bb-business-profiles/1.0', 'workspaces':{owner:{
        'business_id':original_profile['business_id'], 'data_use':original_profile['data_use'],
        'profile_path':'/snapshot/profile', 'dataset_profiles':{'FLORA-RADATA':'/snapshot/profile'}}}}
    def read(path, label):
        if path == '/snapshot/registry': return deepcopy(registry)
        if path == '/snapshot/profile': return deepcopy(original_profile)
        raise AssertionError('Unexpected profile path')
    with contextlib.ExitStack() as stack:
        for name in ['sqlite3.connect','subprocess.Popen','socket.socket.connect',
                     'bb.flora_jobs.JobStore.__init__','bb.flora_jobs.JobStore.submit',
                     'bb.flora_jobs.get_manager','bb.engine_api.get_manager',
                     'bb.engine_methods.solve','bb.flora.solve_case','bb.flora._solve',
                     'bb.availability.solve_case']:
            stack.enter_context(patch(name, side_effect=blocked(name)))
        for name in ['solve','Solve','SolveWithSolutionCallback','SearchForAllSolutions']:
            if hasattr(cp_model.CpSolver,name):
                stack.enter_context(patch.object(cp_model.CpSolver,name,side_effect=blocked('CpSolver.'+name)))
        stack.enter_context(patch.dict(os.environ, {'BB_ENGINE_PROFILE_REGISTRY':'/snapshot/registry'}))
        stack.enter_context(patch('bb.business_profiles._read', side_effect=read))
        request = jobs.normalize_request({'input':raw})
        profile, profile_hash, scope, context = profile_for(owner, request)
        case = prepare(profile, request)
        by_id = case['integration']['need_id_map']
        expected = {n['need_id']:n for n in raw['customer_needs']
                    if '2026-05-11' <= n['date'][:10] <= '2026-06-07'}
        assert len(case['needs']) == len(case['source_needs']) == len(expected) == 1451
        assert {by_id[n['id']] for n in case['needs']} == set(expected)
        assert case['integration']['source_basis'] == basis
        assert len(basis['segments']) == len({s['segment_id'] for s in basis['segments']}) == 292
        stamp = lambda t: (datetime.fromisoformat(case['origin'])+timedelta(minutes=t)).replace(
            tzinfo=ZoneInfo('Europe/Stockholm')).isoformat(timespec='minutes')
        contract = need_windows.export(case['source_needs'], lambda n: by_id[n['id']], stamp, required=True)
        rows = []
        for n in case['needs']:
            nid = by_id[n['id']]
            first = n['source_window_start']; last = n['source_window_end']-n['duration']
            assert n['domains'] == [[first,last]] and first <= last
            assert n['duration'] == expected[nid]['duration_minutes']
            count = expected[nid]['personnel_count_candidate']
            if count is None:
                count = 2 if expected[nid]['source_two_person_flag'] else 1
            assert n['count'] == count
            assert n['timing_authorization']['policy'] in ('MOVABLE_WITHIN_SOURCE_WINDOW','UNIQUE_SOURCE_START')
            assert not n['timing_authorization'].get('unresolved_dependency')
            rows.append(dict(need_id=nid, status='PASS', source_ref=expected[nid]['source_ref'],
                earliest_start=stamp(first), latest_start=stamp(last), latest_end=stamp(n['source_window_end']),
                duration_minutes=n['duration'], personnel_count=n['count'],
                interval_is_complete_time_condition=n['timing_authorization'].get('event_condition_resolution')=='SOURCE_EXECUTION_INTERVAL_IS_COMPLETE'))
        assert sum(r['interval_is_complete_time_condition'] for r in rows) == 132
        assert (raw, original_profile) == before
        assert not any(calls.values())
    evidence = dict(kind='SOLVER_FREE_PREFLIGHT_NOT_SCHEDULE', outcome='PASS',
        needs=rows, need_window_contract=contract['need_window_contract'])
    target = private/'all-1451-preflight.json'
    target.write_text(jobs.canonical(evidence)+'\n'); target.chmod(0o600)
    report = dict(status='PASS', period_needs=1451, passed=1451, failed=0, unknown_preflight=0,
        complete_interval_resolution=132, separate_event_requirements=0,
        source_basis_unchanged=True, source_segments=292, original_texts_input_and_profile_unchanged=True,
        source_basis_sha256=jobs.digest(basis), effective_profile_hash=profile_hash,
        input_hash=jobs.digest(request['input']), source_file_sha256=raw['metadata']['source_file_sha256'],
        private_need_ledger_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        forbidden_calls=calls, http_submissions=0, real_jobs=0, solver_calls=0,
        profile_selection='Actual profile_for using read-only local snapshot registry; no live configuration verified',
        optimization_verified=False, schedule_approved=False, runtime_verified=False)
    (out/'full-preflight-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
