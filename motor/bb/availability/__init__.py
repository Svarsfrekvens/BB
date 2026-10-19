"""Shared per-need eligibility/partial-coverage strategy, selected by server profile.

Input domains are reviewed facts. Each invocation searches a fresh model and
exports a separately validated proposal; source vacancy is demand, not staff.
"""
from copy import deepcopy
from datetime import datetime, timezone
from time import perf_counter
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model

from .model import build_model, _result_duties
from .guards import add_compensation, add_source_jo_coverage, validate_source_jo
from .history import merged_intervals, overlap, utc_minute
from .validator import validate
from ..availability_import import check_case
from ..rule_policy import shared_principles

METHOD = 'reviewed-availability/1.0'
FEASIBLE = {'FEASIBLE', 'OPTIMAL'}


def _stamp(value, zone):
    return datetime.fromtimestamp(value*60, timezone.utc).astimezone(zone).isoformat(timespec='minutes')


def solve_case(case, *, seconds=75, workers=2, objective_mode='coverage_then_temporary'):
    check_case(case)
    if objective_mode != 'coverage_then_temporary':
        raise ValueError('Denna tillgänglighetsprofil stöder behovstäckning före vikarietid; annan viktning ignoreras inte.')
    if type(seconds) not in (int, float) or not 1 <= seconds <= 300 or type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('Ogiltig sökbudget eller antal solvertrådar.')
    began = perf_counter()
    model, ctx = build_model(case, diagnostic_only=False)
    add_compensation(model, ctx)
    add_source_jo_coverage(model, ctx)
    invalid = model.Validate()
    if invalid:
        raise ValueError('Tillgänglighetsmodellen kunde inte valideras.')
    build_seconds = perf_counter()-began
    search_began = perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 1
    status = solver.StatusName(solver.Solve(model))
    phases = [dict(phase=1, objective='MAX_FULLY_COVERED_NEEDS', status=status,
        search_seconds=solver.WallTime(), objective_value=solver.ObjectiveValue() if status in FEASIBLE else None,
        best_bound=solver.BestObjectiveBound())]
    winner = solver
    coverage_optimal = status == 'OPTIMAL'
    phase2_status = 'NOT_RUN_COVERAGE_NOT_PROVED_OPTIMAL'
    if coverage_optimal:
        if seconds-(perf_counter()-search_began) > 0.01:
            model.Add(ctx['coverage_total'] == round(solver.ObjectiveValue()))
            model.Minimize(ctx['phase2_time_objective'])
            second = cp_model.CpSolver()
            second.parameters.max_time_in_seconds = seconds-(perf_counter()-search_began)
            second.parameters.num_search_workers = workers
            second.parameters.random_seed = 1
            phase2_status = second.StatusName(second.Solve(model))
            phases.append(dict(phase=2, objective='MIN_TEMPORARY_AR_PLUS_UNFILLED_NEED_PERSON_MINUTES',
                status=phase2_status, search_seconds=second.WallTime(),
                objective_value=second.ObjectiveValue() if phase2_status in FEASIBLE else None))
            if phase2_status in FEASIBLE:
                winner, status = second, phase2_status
            else:
                status = 'FEASIBLE'
        else:
            phase2_status, status = 'NOT_RUN_SEARCH_DEADLINE', 'FEASIBLE'
    feasible = status in FEASIBLE
    duties = _result_duties(ctx, winner) if feasible else []
    assigned = [dict(need_id=s['need_id'], employee_id=s['employee_id'], candidate_id=s['candidate_id'],
        start=winner.Value(s['start']), end=winner.Value(s['start'])+s['duration'], frozen=s.get('frozen', False))
        for s in ctx['supports'] if feasible and winner.Value(s['presence'])]
    covered = {nid for nid, n in ctx['needs'].items() if feasible and winner.Value(n['coverage'])}
    origin = case['period']['history_lo']
    zone = ZoneInfo(case['period']['timezone'])
    weeks, days = {}, {}
    if feasible:
        for pid, value in ctx['week_phases'].items():
            stamp = datetime.fromtimestamp((origin+winner.Value(value))*60, zone)
            weeks[pid] = dict(weekday=stamp.weekday(), clock=stamp.strftime('%H:%M'),
                              phase_minutes=winner.Value(value), status='MODEL_SELECTED_FIXED_PER_PERSON')
        for pid, value in ctx['daily_rest_phases'].items():
            stamp = datetime.fromtimestamp((origin+winner.Value(value))*60, zone)
            days[pid] = dict(clock=stamp.strftime('%H:%M'), phase_minutes=winner.Value(value),
                             origin_minute=origin, status='REVIEWED_TEST_SCENARIO_SELECTION')
    raw = dict(solver_status=status, covered_needs=len(covered) if feasible else None,
        input_needs=len(case['needs']), selected_duties=duties, assignments=assigned,
        selected_candidate_ids=[d['id'] for d in duties], week_anchors=weeks, daily_rest_anchors=days,
        daily_rest_24h_scope=ctx['daily_rest_24h_scope'],
        historical_certificates=ctx['historical_certificates'], unknown_controls=ctx['unknown_controls'],
        contract_profile_scope=ctx.get('contract_profile_scope'), phases=phases,
        build_seconds=build_seconds, search_seconds=perf_counter()-search_began,
        coverage_optimal_within_model=coverage_optimal, phase2_status=phase2_status,
        business_schedule_approved=False,
        unassigned=[dict(need_id=n['id'], blockers=n.get('blockers', []),
            reason='NO_VERIFIED_PERFORMER' if not n.get('eligible_employee_ids') else 'NOT_COVERED_IN_RETURNED_SOLUTION')
            for n in case['needs'] if feasible and n['id'] not in covered])
    validation = validate_case(case, raw)
    return normalize(case, raw, validation)


def validate_case(case, result):
    raw = result.get('raw_solution', result)
    checked = validate(case, raw)
    jour = validate_source_jo(case, raw)
    def item(row):
        return dict(rule_id=row['rule'], message=row.get('detail', row['rule']), detail=deepcopy(row))
    violations = [item(r) for r in checked['violations']['new']]
    if jour['all_windows_covered'] is False:
        violations.append(dict(rule_id='source_oncall_coverage', message='Planerad källjour är inte fullständigt bemannad.'))
    unknowns = [item(r) for r in checked['unknown_controls']]
    permission_gaps = {}
    for need in case['needs']:
        for blocker in need.get('blockers', []):
            permission_gaps.setdefault(blocker, []).append(need['id'])
    unknowns.extend(dict(rule_id='performer_permissions:'+key,
        message=f'{len(ids)} behov saknar verifierat utförarbeslut för {key}. De behålls som behov och tilldelas inte personal.',
        need_ids=ids) for key, ids in sorted(permission_gaps.items()))
    if raw['solver_status'] in FEASIBLE and raw['unassigned']:
        unknowns.append(dict(rule_id='unassigned_needs',
            message=f"{len(raw['unassigned'])} av {len(case['needs'])} behov är oplacerade i detta förslag. Alla finns kvar i redovisningen."))
    unknowns.extend([
        dict(rule_id='paid_time', message='Raster ingår inte i detta beslutade testscenario. Betald nettotid och kostnadseffekt är inte verifierade.'),
        dict(rule_id='contract_accounting', message='Bevarad original-Ar är inte fullständig avräkning av SSG och frånvaro.')])
    rules = [dict(rule_id=r['rule'], status=r['status'], message=r['rule'], detail=deepcopy(r))
             for r in checked['rules'] if r['status'] in {'PASS', 'FAIL', 'UNKNOWN'}]
    rules.extend(dict(rule_id=r['rule_id'], status='UNKNOWN', message=r['message']) for r in unknowns
                 if r['rule_id'] not in {x['rule_id'] for x in rules})
    rules.append(dict(rule_id='source_oncall_coverage', status='PASS' if jour['all_windows_covered'] else 'FAIL' if jour['all_windows_covered'] is False else 'UNKNOWN',
                      message='Källans planerade jourbehov kontrollerat separat, inklusive ursprungliga vakansrader.'))
    return dict(overall='FAIL' if violations else 'UNKNOWN',
        checked_status='PASS' if not violations and raw['solver_status'] in FEASIBLE else 'FAIL' if violations else 'UNKNOWN',
        validator='independent-availability-certificate/1.0', rules=rules, violations=violations,
        unknowns=unknowns, historical=[item(r) for r in checked['violations']['historical']],
        details=checked, certificates={'availability-check.json': checked, 'source-jour.json': jour})


def normalize(case, raw, validation):
    """Keep raw Ar separate from unknown paid net; never manufacture savings."""
    integration = case['integration']
    period, lo, hi = integration['period'], case['period']['lo'], case['period']['hi']
    zone = ZoneInfo(period['timezone'])
    feasible = raw['solver_status'] in FEASIBLE
    people = {e['id']: e for e in case['employees']}
    needs = {n['id']: n for n in case['needs']}
    source = case['source_schedule_segments']
    after_duties = case['frozen_duties']+raw['selected_duties'] if feasible else []
    def length(intervals):
        return sum(overlap(a, b, lo, hi) for a, b in merged_intervals(intervals))
    before, after = {}, {}
    for pid in people:
        before[pid] = dict(net_minutes=None, gross_minutes=length([(r['start'], r['end']) for r in source if r.get('person_id') == pid and r['source_code'] == 'Ar']),
            jour_minutes=length([(r['start'], r['end']) for r in source if r.get('person_id') == pid and r['source_code'] == 'Jo']),
            break_minutes=None, free_days=None)
        if feasible:
            after[pid] = dict(net_minutes=None, gross_minutes=length([v for d in after_duties if d['employee_id'] == pid for v in d.get('work', [])]),
                jour_minutes=length([v for d in after_duties if d['employee_id'] == pid for v in d.get('jour', [])]),
                break_minutes=None, free_days=None)
    covered = {a['need_id'] for a in raw['assignments']}
    def totals(stats, is_after):
        known = bool(stats)
        def total(key, staffing=None):
            return sum(v[key] for pid, v in stats.items() if staffing is None or people[pid]['staffing_type'] == staffing) if known else None
        covered_minutes = sum(needs[n]['duration']*needs[n]['count'] for n in covered) if known and is_after else None
        all_minutes = sum(n['duration']*n['count'] for n in needs.values())
        return dict(ordinary_net_minutes=None, temporary_net_minutes=None,
            ordinary_gross_minutes=total('gross_minutes', 'ORDINARY_SOURCE'),
            temporary_gross_minutes=total('gross_minutes', 'TEMPORARY_VERIFIED'), jour_minutes=total('jour_minutes'),
            break_minutes=None, overtime_minutes=None, extra_minutes=None,
            vacant_minutes=None if is_after else sum(overlap(r['start'], r['end'], lo, hi) for r in source if r.get('is_vacant')),
            fully_covered_needs=len(covered) if known and is_after else None, total_needs=len(needs),
            covered_need_minutes=covered_minutes, uncovered_need_minutes=all_minutes-covered_minutes if covered_minutes is not None else None)
    segments = []
    for duty in after_duties:
        for key, code in [('work', 'Ar'), ('jour', 'Jo')]:
            for index, (a, b) in enumerate(duty.get(key, [])):
                segments.append(dict(segment_id=f"{duty['id']}:{code}:{index}", person_id=duty['employee_id'],
                    start=_stamp(a, zone), end=_stamp(b, zone), code=code,
                    staffing_type='ordinary' if people[duty['employee_id']]['staffing_type'] == 'ORDINARY_SOURCE' else 'temporary',
                    source_ref=deepcopy(duty.get('source_refs', [])), minutes_in_period=overlap(a, b, lo, hi)))
    interventions = [dict(need_id=a['need_id'], person_id=a['employee_id'], start=_stamp(a['start'], zone), end=_stamp(a['end'], zone),
        customer_id=needs[a['need_id']].get('customer_id'), source_ref=needs[a['need_id']].get('source_ref')) for a in raw['assignments']]
    policy = shared_principles()
    policy.update(profile_id=integration['profile_id'], business_id=integration['business_id'],
                  effective_profile_values=deepcopy(case['rules']), other_business_decisions_inherited=False)
    return dict(schema_version='bb-engine-run/1.0', review_required=True, business_schedule_approved=False,
        method=METHOD, solver_status=raw['solver_status'], period=period,
        before=totals(before, False), after=totals(after, True),
        persons=[dict(person_id=pid, alias=p.get('alias'), before=before[pid], after=after.get(pid),
            weekly_net_minutes=None, minimum_rolling_free_days=None) for pid, p in people.items()],
        schedule=dict(segments=segments, breaks=[], interventions=interventions), validation=validation,
        solver=dict(status=raw['solver_status'], wall_seconds=raw['search_seconds'], build_seconds=raw['build_seconds'],
            phases=raw['phases'], coverage_optimal_within_model=raw['coverage_optimal_within_model'],
            phase2_status=raw['phase2_status']), raw_solution=raw,
        unassigned_need_ids=[n['need_id'] for n in raw['unassigned']], unassigned_needs=deepcopy(raw['unassigned']),
        unknown_need_ids=[] if feasible else list(needs),
        assumptions=[dict(id='reviewed_input_only', message='Utvecklingsprofil för exakt granskad indataversion. Nya uppgifter behöver stämmas av före körning.'),
            dict(id='breaks', message='Raster har utelämnats enligt testbeslutet. Ar-tid är känd; betald nettotid är okänd.'),
            dict(id='partial_coverage', message='Alla behov finns i nämnaren. Utan verifierad utförarkoppling får behovet ingen tilldelning.'),
            dict(id='decisions', message='Bekräftade rättningar och scenarioändringar redovisas separat från originalet.')],
        time_accounting=dict(basis='SOURCE_AR_BREAKS_OMITTED_SCENARIO', paid_time_verified=False,
            after_breaks='OMITTED_SCENARIO', ordinary_Ar_preserved=all(before[pid]['gross_minutes'] == after[pid]['gross_minutes'] for pid,p in people.items() if p['staffing_type']=='ORDINARY_SOURCE') if feasible else None),
        source_basis=dict(kind='VERIFIED_UPLOADED_ORIGINAL', verification='EXACT_SERVER_REVIEWED_INPUT',
            source_identity=integration['source_identity'], source_file_sha256=integration['source_file_sha256'],
            segments=[dict(segment_id=r['segment_id'], person_id=r.get('person_id'),
                start=r['start'], end=r['end'], code=r['source_code']) for r in source]),
        cost_effect=dict(temporary_paid_cost_change=None, currency=None, parameters={}, missing_person_ids=[],
            status='UNKNOWN_PAID_TIME_NOT_VERIFIED', explanation='Rastavräkning saknas; Ar-tid får inte bli verifierad betald nettotid eller kostnadsbesparing.'),
        rule_policy=policy, provenance=dict(source_identity=integration['source_identity'], source_file_sha256=integration['source_file_sha256'],
            profile_source=integration['profile_source'], decisions=integration['decisions'], old_solver_result_reused=False))
