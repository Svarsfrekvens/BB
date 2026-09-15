"""CP-SAT solver. Hard rules are constraints, never penalty terms.

Sökordning: (0) feasibility med uncovered==0, (1) minimera obemannat
om 100 % inte hittats/bevisats, (2) minimera personalkostnad,
(3) minimera kontinuitet/spridning.
Hårda regler lättas aldrig. Täckning får inte sänkas för att spara kostnad.
"""
from math import floor
from time import perf_counter
from uuid import uuid4
from .domain import (check_input, occurrences, span, paid, overlap, intersect,
                     instant, add_days, days, night_intervals, jour_intervals, is_night, monday,
                     ssg_cap_minutes, skills_on_day, hard_constraints, weekend_allowed,
                     shift_allowed, rolling_week_windows, soft_constraints,
                     work_day_date, shifts_mergeable, occasion_work_day_date,
                     occasion_work_day_dates, rest_days_target, f01_known_span, f01_window_known,
                     candidate_as_shift, jour_eligible, night_eligible,
                     required_rest_after_minutes, occasion_exceeds_max_span,
                     iter_mergeable_chains, is_fixed_choice, remaining_capacity,
                     longest_rest_minutes, active_employees)
from .assign import (
    index_candidates_by_employee, index_candidates_by_employee_day,
    prune_unusable_generated_templates, support_options_for_occurrence,
)
from .generate import generated_template_stats, planning_day_bounds, planning_mode, shift_templates_for_solve
from .jour_capacity import analyze_jour_capacity
from .precheck import (
    enumerate_person_shift_slots, explain_with_precheck, feasibility_precheck,
    has_critical_precheck, planning_diagnostics,
)
from .limits import effective_max_candidate_shifts, effective_max_support_combinations
from .perf import peak_memory_mb, planning_summary, schedule_kpis
from .replan import collect_locked_shifts
from .validate import validate

# Sökbudget. Inte periodspecifika undantag. Totaltak i solve() är oförändrat (1–300 s).
ZERO_GAP_PHASE0_MAX_S = 90.0
ZERO_GAP_PHASE0B_MAX_S = 45.0
COVERAGE_SHARE = 0.40
COVERAGE_REL_GAP = 0.10
COVERAGE_ABS_GAP = 30


def coverage_ready_for_cost(last):
    """Cost/quality först när täckningen är bevisad eller gapet är litet."""
    if not last:
        return False
    if last.get('code') == 'OPTIMAL':
        return True
    if int(last.get('uncoveredMinutes') or 0) == 0:
        return True
    inc = int(last.get('uncoveredMinutes') or 0)
    try:
        bnd = float(last.get('bound'))
    except (TypeError, ValueError):
        return False
    if bnd < 0:
        return False
    abs_gap = inc - bnd
    rel = abs_gap / inc if inc else 0.0
    return abs_gap <= COVERAGE_ABS_GAP and rel <= COVERAGE_REL_GAP


def _as_bool(model, x, name):
    if isinstance(x, int):
        v = model.new_bool_var(name)
        model.add(v == (1 if x else 0))
        return v
    return x


def _chain_shifts(chain):
    return [candidate_as_shift(c) for c in chain]


def forbid_overlong_occasions(model, items, rules, lit, prefix='span'):
    """Samma COMPOSITE_LENGTH som validatorn: span > shiftProfiles.*.maxSpanHours.

    Förbjuder varje ko-selektbar mergeable kombination, inte bara den greedy
    kedjan längs mallordning. Enbart låsta pass lämnas till historik.
    """
    seq = sorted(items, key=lambda c: (c['a'], c['b'], id(c)))
    index = {id(c): i for i, c in enumerate(seq)}
    for chain in iter_mergeable_chains(seq):
        if not occasion_exceeds_max_span(_chain_shifts(chain), rules):
            continue
        if all(is_fixed_choice(c['x']) for c in chain):
            continue
        tag = '-'.join(str(index[id(c)]) for c in chain)
        xs = [lit(c['x'], f'{prefix}x:{tag}:{t}') for t, c in enumerate(chain)]
        model.add(sum(xs) <= len(chain) - 1)


def forbid_compensatory_rest(model, items, rules, lit, prefix='comp'):
    """Samma tjänstgöringstillfällen som COMPOSITE_LENGTH / validatorn."""
    seq = sorted(items, key=lambda c: (c['a'], c['b'], id(c)))
    index = {id(c): i for i, c in enumerate(seq)}
    n = len(seq)
    for chain in iter_mergeable_chains(seq):
        types = {c['shift'].get('type') for c in chain}
        if 'jour' not in types or not (types - {'jour'}):
            continue
        rest_after = required_rest_after_minutes(_chain_shifts(chain), rules)
        if rest_after <= 0:
            continue
        last_i = index[id(chain[-1])]
        chain_end = chain[-1]['b']
        tag = '-'.join(str(index[id(c)]) for c in chain)
        xs_chain = [lit(c['x'], f'{prefix}c:{tag}:{t}') for t, c in enumerate(chain)]
        for t in range(last_i + 1, n):
            later = seq[t]
            if later['a'] >= chain_end + rest_after:
                break
            if shifts_mergeable(candidate_as_shift(chain[-1]), candidate_as_shift(later)):
                continue
            if all(is_fixed_choice(c['x']) for c in chain) and is_fixed_choice(later['x']):
                continue
            lx = lit(later['x'], f'{prefix}l:{tag}:{t}')
            model.add(sum(xs_chain) + lx <= len(chain))


def _schedule_workday_flags(model, items, flag_days, prefix):
    """En workDayDate per tjänstgöringstillfälle. Inte kalenderöverlapp av betald tid."""
    contrib = {}
    sorted_items = sorted(items, key=lambda c: c['a'])
    comps = []
    for c in sorted_items:
        row = dict(c['shift'], a=c['a'], b=c['b'], x=c['x'])
        if comps and shifts_mergeable(comps[-1][-1], row):
            comps[-1].append(row)
        else:
            comps.append([row])
    nseg = 0
    for ci, comp in enumerate(comps):
        xs = [_as_bool(model, c['x'], f'{prefix}:sel:{ci}:{t}') for t, c in enumerate(comp)]
        k = len(comp)
        if k == 1:
            d = work_day_date(comp[0]['a'], comp[0]['b'], comp[0].get('date'))
            contrib.setdefault(d, []).append(xs[0])
            continue
        for i in range(k):
            for j in range(i, k):
                nseg += 1
                seg = model.new_bool_var(f'{prefix}:seg:{ci}:{i}:{j}')
                inner = xs[i:j + 1]
                for x in inner:
                    model.add(seg <= x)
                if i > 0:
                    model.add(seg + xs[i - 1] <= 1)
                if j + 1 < k:
                    model.add(seg + xs[j + 1] <= 1)
                leftovers = [x.Not() for x in inner]
                if i > 0:
                    leftovers.append(xs[i - 1])
                if j + 1 < k:
                    leftovers.append(xs[j + 1])
                model.add_bool_or([seg] + leftovers)
                d = occasion_work_day_date(comp[i:j + 1])
                contrib.setdefault(d, []).append(seg)
    flags = []
    for day in flag_days:
        flag = model.new_bool_var(f'{prefix}:wd:{day}')
        lits = contrib.get(day) or []
        if lits:
            model.add_max_equality(flag, lits)
        else:
            model.add(flag == 0)
        flags.append(flag)
    return flags


def solve(data, seconds=30, build_only=False, lex_stop=None, coverage_trace=None, sat_params=None, occurrence_encoding=None, lns_free_keys=None, lns_incumbent_shifts=None):
    from ortools.sat.python import cp_model

    class _CoverageTrace(cp_model.CpSolverSolutionCallback):
        def __init__(self, unc, rows):
            super().__init__()
            self._unc = unc
            self._rows = rows
            self._t0 = perf_counter()

        def on_solution_callback(self):
            self._rows.append(dict(
                event='incumbent',
                t=round(perf_counter() - self._t0, 3),
                incumbent=int(self.Value(self._unc)),
                bound=int(self.BestObjectiveBound()),
                conflicts=int(self.NumConflicts()),
                branches=int(self.NumBranches()),
            ))
    check_input(data)
    seconds = min(300, max(1, float(seconds)))
    encoding = occurrence_encoding or 'support_z'
    if encoding not in ('support_z', 'start_choice'):
        raise ValueError('Ogiltig occurrence_encoding.')
    wp, rules = data['workplace'], data['rules']
    lo,hi = instant(wp['start'],'00:00'),instant(add_days(wp['end'],1),'00:00')
    period_days=list(days(wp['start'],wp['end']))
    # vacantShifts/openShifts är Före-information och skapar inte kandidater.
    employees=active_employees(data)
    t0=perf_counter()
    t_gen=perf_counter()
    raw_templates=shift_templates_for_solve(data)
    t_idx=perf_counter()
    enum_raw=enumerate_person_shift_slots(data, raw_templates)
    shift_vars_before=sum(1 for s in enum_raw['slots'] if s['eligible'])
    template_list, tpl_prune=prune_unusable_generated_templates(data, raw_templates)
    index_ms=int(round((perf_counter()-t_idx)*1000))
    generate_ms=int(round((perf_counter()-t_gen)*1000))
    templates={t['id']:t for t in template_list}
    occ=occurrences(data)
    occ_by_date={}
    for o in occ:
        occ_by_date.setdefault(o['date'], []).append(o)
    reserve=int(rules.get('withinPassMinutesPerShift') or 0)
    mode=planning_mode(data)
    tpl_stats=generated_template_stats(template_list)
    locked_shifts=collect_locked_shifts(data)

    t_pre=perf_counter()
    jour_payload=analyze_jour_capacity(data) if int(rules.get('jourFloor') or 0) else None
    diagnoses=feasibility_precheck(data, jour_payload=jour_payload)
    pre_ms=int(round((perf_counter()-t_pre)*1000))
    enum=dict(before=0, after=0, slots=[], templates=template_list)
    generated_n=tpl_stats.get('total') or sum(1 for t in templates.values() if t.get('generated'))
    shift_vars_after=0

    def diagnostics(status, solve_ms=0, nvars=0, ncons=0, validate_ms=0, kpis=None, phases=None, extra_perf=None):
        extra=dict(
            generatedShiftTemplates=generated_n,
            templateStats=tpl_stats,
            before=enum['before'],
            after=enum['after'],
            solverVariables=nvars,
            solverConstraints=ncons,
            preCheckTimeMs=pre_ms,
            generateTimeMs=generate_ms,
            solveTimeMs=solve_ms,
            validateTimeMs=validate_ms,
            totalTimeMs=int(round((perf_counter()-t0)*1000)),
            memoryPeakMb=peak_memory_mb(),
            solverStatus=status,
            lockedShifts=len(locked_shifts),
        )
        if extra_perf:
            extra.update(extra_perf)
        if phases:
            by={p['name']:int(round(float(p.get('actualMs') if p.get('actualMs') is not None else (p.get('seconds') or 0)*1000))) for p in phases}
            extra['zeroGapPhaseMs']=by.get('zeroGap',0)
            extra['zeroGapBPhaseMs']=by.get('zeroGapB',0)
            extra['coveragePhaseMs']=by.get('coverage',0)
            extra['costPhaseMs']=by.get('cost',0)
            extra['qualityPhaseMs']=by.get('quality',0)
            extra['actualCoverageSolveMs']=by.get('coverage',0)+by.get('zeroGap',0)+by.get('zeroGapB',0)
            extra['actualCostSolveMs']=by.get('cost',0)
            extra['actualQualitySolveMs']=by.get('quality',0)
        if kpis:
            extra.update(kpis)
        return planning_diagnostics(data, extra)

    def empty_infeasible(message, status='INFEASIBLE'):
        explanation=explain_with_precheck(status, diagnoses, message, locked=bool(locked_shifts))
        diag=diagnostics(status)
        schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus=status,explanation=explanation,feasibilityNotes=[],preCheck=diagnoses,seconds=pre_ms/1000,objective=None,bound=None)
        if jour_payload is not None:
            schedule['resourceDiagnostics']=dict(jour=jour_payload)
        out=dict(schedule=schedule,validation=None,modelScope=dict(candidateShifts=0,occurrences=len(occ),startStep=rules['flexibilityStep'],**diag),diagnostics=dict(performance=diag))
        if jour_payload is not None:
            out['resourceDiagnostics']=dict(jour=jour_payload)
        out['summary']=planning_summary(data, schedule, None, diag)
        return out

    if has_critical_precheck(diagnoses):
        return empty_infeasible('Ingen lösning uppfyller alla hårda villkor.')

    enum=enumerate_person_shift_slots(data, template_list)
    shift_vars_after=sum(1 for s in enum['slots'] if s['eligible'])

    weekend_notes=[]
    from datetime import date as _date
    for day, need in occ_by_date.items():
        if _date.fromisoformat(day).isoweekday() not in (6,7): continue
        eligible=[e for e in employees if weekend_allowed(e,day)]
        if not eligible:
            weekend_notes.append(f'{day}: helgbehov finns men ingen medarbetare får arbeta enligt helgmönstret.')
            continue
        for o in need:
            if not any(set(o['task']['skills'])<=skills_on_day(e,day) for e in eligible):
                weekend_notes.append(f'{day}: {o["task"]["name"]} saknar helgbehörig kompetens.')

    jour_floor=int(rules.get('jourFloor') or 0)
    t_model=perf_counter()
    model=cp_model.CpModel()
    candidates=[]
    boundaries=[]
    for s in data['boundaryShifts']:
        a,b=span(s)
        boundaries.append(dict(shift=s,a=a,b=b,work=paid(s),x=1))
    locked_fixed=[]
    for s in locked_shifts:
        a,b=span(s)
        locked_fixed.append(dict(shift=s,a=a,b=b,work=paid(s),x=1))
    duty_anchor=boundaries+locked_fixed
    by_emp={e['id']:e for e in employees}
    cand_by_emp={e['id']:[] for e in employees}
    for slot in enum['slots']:
        if not slot['eligible']:
            continue
        t=slot['template']
        e=by_emp[slot['employeeId']]
        day=slot['day']
        s=dict(id=f"{e['id']}:{day}:{t['id']}",employeeId=e['id'],date=day,start=t['start'],end=t['end'],type=t['type'],skills=t.get('skills') or [],breaks=t.get('breaks') or [])
        if t.get('dutyProfile'):
            s['dutyProfile']=t['dutyProfile']
        a,b=slot['a'],slot['b']
        work=paid(s)
        x=model.new_bool_var('shift:'+s['id'])
        row=dict(shift=s,a=a,b=b,work=work,x=x,generated=bool(t.get('generated')))
        candidates.append(row)
        cand_by_emp[e['id']].append(row)
    if len(candidates)>effective_max_candidate_shifts(data):
        raise ValueError('För många passalternativ. Begränsa personal, passmallar eller period.')

    def min_period(c):
        return sum(intersect(a,b,lo,hi) for a,b in c['work'])

    t_cons=perf_counter()
    utilisations=[]
    workday_flags={}
    night_series_flags={}
    for e in employees:
        rows=sorted(cand_by_emp.get(e['id']) or [], key=lambda c:c['a'])
        fixed=[b for b in duty_anchor if b['shift']['employeeId']==e['id']]
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                if overlap(a['a'],a['b'],b['a'],b['b']):
                    model.add(a['x']+b['x']<=1)
        items=sorted(rows+fixed, key=lambda c: (c['a'], c['b']))
        rest_need=int(round(rules['minRestHours']*60))
        n_items=len(items)

        def lit(x, name):
            return _as_bool(model, x, name)

        for i in range(n_items):
            a=items[i]
            ax=lit(a['x'], f'restfix:{e["id"]}:{i}')
            for j in range(i+1, n_items):
                b=items[j]
                if overlap(a['a'],a['b'],b['a'],b['b']):
                    continue
                gap=b['a']-a['b']
                if gap>=rest_need:
                    break
                bx=lit(b['x'], f'restfix:{e["id"]}:{i}:{j}')
                if is_fixed_choice(a['x']) and is_fixed_choice(b['x']):
                    continue
                if shifts_mergeable(candidate_as_shift(a), candidate_as_shift(b)):
                    continue
                bridges=[c for c in items[i+1:j] if a['b']<=c['a'] and c['b']<=b['a']
                         and shifts_mergeable(candidate_as_shift(a), candidate_as_shift(c))
                         and shifts_mergeable(candidate_as_shift(c), candidate_as_shift(b))]
                if bridges:
                    model.add(ax+bx<=1+sum(lit(c['x'], f'br:{e["id"]}:{i}:{j}:{t}') for t,c in enumerate(bridges)))
                else:
                    model.add(ax+bx<=1)
        forbid_overlong_occasions(model, items, rules, lit, prefix=f'span:{e["id"]}')
        forbid_compensatory_rest(model, items, rules, lit, prefix=f'comp:{e["id"]}')
        temporary=e.get('resourceType')=='temporary'
        hard=hard_constraints(e)
        fixed_used=sum(min_period(c) for c in fixed)
        decision_used=sum(min_period(c)*c['x'] for c in rows)
        if temporary:
            max_paid=hard.get('maxPaidMinutes')
            if max_paid is not None:
                model.add(decision_used<=remaining_capacity(int(max_paid), fixed_used))
            cap=0
        else:
            cap=floor(ssg_cap_minutes(e,period_days,rules,wp)+1e-7)
            model.add(decision_used<=remaining_capacity(cap, fixed_used))
        used=decision_used+min(fixed_used, max(0, cap))
        if cap>0:
            util=model.new_int_var(0,1000,'util:'+e['id'])
            used_var=model.new_int_var(0,cap,'paid_minutes:'+e['id'])
            model.add(used_var==used)
            model.add_division_equality(util,used_var*1000,cap)
            utilisations.append(util)
        for week in {monday(day) for day in period_days}:
            wa,wb=instant(week,'00:00'),instant(add_days(week,7),'00:00')
            def week_paid(c):
                return sum(intersect(a,b,wa,wb) for a,b in c['work'])
            fixed_w=sum(week_paid(c) for c in fixed)
            model.add(sum(week_paid(c)*c['x'] for c in rows)<=remaining_capacity(floor(rules['maxWeeklyHours']*60), fixed_w))
        flags=[]
        flag_days=list(days(add_days(wp['start'],-27),add_days(wp['end'],27)))
        flags=_schedule_workday_flags(model, rows+fixed, flag_days, 'wd:'+e['id'])
        forced_days=occasion_work_day_dates([candidate_as_shift(c) for c in fixed]) if fixed else set()
        forced=[1 if d in forced_days else 0 for d in flag_days]
        legal=rules.get('hardMaxConsecutiveDays')
        if legal:
            w=int(legal)+1
            for i in range(len(flags)-w+1):
                model.add(sum(flags[i:i+w])<=max(int(legal), sum(forced[i:i+w])))
        person_cap=hard_constraints(e).get('maxConsecutiveDays')
        if person_cap:
            w=int(person_cap)+1
            for i in range(len(flags)-w+1):
                model.add(sum(flags[i:i+w])<=max(int(person_cap), sum(forced[i:i+w])))
        workday_flags[e['id']]=(flags,flag_days,forced)
        night_lim=hard_constraints(e).get('maxNightConsecutive')
        nflags=[]
        night_span_days=list(days(add_days(wp['start'],-7),add_days(wp['end'],7)))
        ncounts=[]
        for day in night_span_days:
            covering=[c['x'] for c in rows+fixed if c['shift'].get('type')=='night' and c['shift'].get('date')==day]
            nf=model.new_bool_var('nightday:'+e['id']+day)
            if covering:
                model.add_max_equality(nf,covering)
                nc=model.new_int_var(0,len(covering),'nightcnt:'+e['id']+day)
                model.add(nc==sum(covering))
            else:
                model.add(nf==0)
                nc=0
            nflags.append(nf)
            ncounts.append(nc)
        if night_lim:
            lim=int(night_lim)
            locked_n=[1 if any(is_fixed_choice(c['x']) and c['x']==1 and c['shift'].get('type')=='night' and c['shift'].get('date')==day for c in rows+fixed) else 0 for day in night_span_days]
            for w in range(1, lim+2):
                for i in range(len(ncounts)-w+1):
                    model.add(sum(ncounts[i:i+w])<=max(lim, sum(locked_n[i:i+w])))
        night_series_flags[e['id']]=(nflags, night_span_days)
        min_off=hard_constraints(e).get('minConsecutiveOffDays')
        if min_off:
            need=int(min_off)
            period_flags=flags[27:27+len(period_days)]
            forced_period=forced[27:27+len(period_days)]
            if need<=len(period_flags) and any(sum(forced_period[i:i+need])==0 for i in range(len(period_flags)-need+1)):
                windows=[]
                for i in range(len(period_flags)-need+1):
                    w=model.new_bool_var(f'minoff:{e["id"]}:{i}')
                    for j in range(need):
                        model.add(period_flags[i+j]==0).only_enforce_if(w)
                    windows.append(w)
                if windows:
                    model.add(sum(windows)>=1)
        jour_lim=hard_constraints(e).get('maxJourConsecutive')
        weekly=float(rules.get('minWeeklyRestHours') or 36)
        if weekly>0:
            need=int(round(weekly*60))
            duty=rows+fixed
            for day,wa,wb in rolling_week_windows(wp['start'],wp['end']):
                a,b=instant(day,'00:00'),instant(add_days(day,1),'00:00')
                covering=[c['x'] for c in duty if overlap(c['a'],c['b'],a,b)]
                if not covering:
                    continue
                work=model.new_bool_var(f'wrest_day:{e["id"]}:{day}')
                model.add_max_equality(work,covering)
                slots=[]
                t=wa
                step=3*60
                while t+need<=wb:
                    overlapping=[c for c in duty if overlap(c['a'],c['b'],t,t+need)]
                    if any(isinstance(c['x'],int) and c['x']==1 for c in overlapping):
                        t+=step
                        continue
                    free=model.new_bool_var(f'wrest:{e["id"]}:{day}:{t}')
                    for c in overlapping:
                        if not isinstance(c['x'],int):
                            model.add(c['x']==0).only_enforce_if(free)
                    slots.append(free)
                    t+=step
                if slots:
                    model.add(sum(slots)>=1).only_enforce_if(work)
                else:
                    locked_duties=[(c['a'],c['b']) for c in duty if is_fixed_choice(c['x']) and c['x']==1]
                    inherited=longest_rest_minutes(locked_duties, wa, wb)<need if locked_duties else False
                    if not inherited:
                        model.add(work==0)
        jour_rows=[c for c in rows+fixed if c['shift'].get('type')=='jour']
        if jour_lim:
            jcounts=[]
            jour_days=list(days(add_days(wp['start'],-7),add_days(wp['end'],7)))
            for day in jour_days:
                covering=[c['x'] for c in jour_rows if c['shift'].get('date')==day]
                if covering:
                    jc=model.new_int_var(0,len(covering),'jourcnt:'+e['id']+day)
                    model.add(jc==sum(covering))
                else:
                    jc=0
                jcounts.append(jc)
            lim=int(jour_lim)
            locked_j=[1 if any(is_fixed_choice(c['x']) and c['x']==1 and c['shift'].get('date')==day for c in jour_rows) else 0 for day in jour_days]
            for w in range(1, lim+2):
                for i in range(len(jcounts)-w+1):
                    model.add(sum(jcounts[i:i+w])<=max(lim, sum(locked_j[i:i+w])))
        for start_day in sorted({c['shift']['date'] for c in jour_rows}):
            limit=add_days(start_day,27)
            window=[c for c in jour_rows if start_day<=c['shift']['date']<=limit]
            fixed_j=sum((c['b']-c['a']) for c in window if is_fixed_choice(c['x']) and c['x']==1)
            model.add(sum((c['b']-c['a'])*c['x'] for c in window if not is_fixed_choice(c['x']))<=remaining_capacity(48*60, fixed_j))
        per_manad={}
        for c in jour_rows:
            per_manad.setdefault(c['shift']['date'][:7],[]).append(c)
        for grupp in per_manad.values():
            fixed_m=sum((c['b']-c['a']) for c in grupp if is_fixed_choice(c['x']) and c['x']==1)
            model.add(sum((c['b']-c['a'])*c['x'] for c in grupp if not is_fixed_choice(c['x']))<=remaining_capacity(50*60, fixed_m))

    constraint_ms=int(round((perf_counter()-t_cons)*1000))

    # Awake-night floor counts on-duty, eligible people. Rest constraints prevent
    # a person from being counted through two simultaneous candidate shifts.
    floor_lo, floor_hi = lo, hi
    if data.get('_rhClipFloors'):
        ps, pe = planning_day_bounds(data)
        floor_lo, floor_hi = instant(ps, '00:00'), instant(add_days(pe, 1), '00:00')
    for a,b in night_intervals(wp['start'],wp['end']):
        a,b=max(a,floor_lo),min(b,floor_hi)
        if a>=b or not rules['nightFloor']: continue
        valid_ids={e['id'] for e in employees if night_eligible(e)}
        coverage=[(u,v,c['x']) for c in candidates+duty_anchor if c['shift']['employeeId'] in valid_ids for u,v in c['work']]
        edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
        for edge in edges[:-1]:
            model.add(sum(x for u,v,x in coverage if u<=edge<v)>=rules['nightFloor'])

    if jour_floor:
        valid_ids={e['id'] for e in employees if jour_eligible(e)}
        for a,b in jour_intervals(wp['start'],wp['end'],rules):
            a,b=max(a,floor_lo),min(b,floor_hi)
            if a>=b: continue
            coverage=[(c['a'],c['b'],c['x']) for c in candidates+duty_anchor if c['shift'].get('type')=='jour' and c['shift']['employeeId'] in valid_ids]
            edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
            for edge in edges[:-1]:
                model.add(sum(x for u,v,x in coverage if u<=edge<v)>=jour_floor)

    task_vars=[]
    # Ge CP-SAT en omedelbart giltig startpunkt via gap-hints. All-zero-pass
    # hintas inte när nightFloor/jourFloor gör den punkten ogiltig – det gav
    # tidigare UNKNOWN utan att tidsbudgeten användes.
    per_employee={e['id']:[] for e in employees}
    customer_links={}
    supports_count=0
    support_before=support_after=0
    assign_vars=0
    hint_bools=[]
    t_support=perf_counter()
    t_idx2=perf_counter()
    by_emp_cand=index_candidates_by_employee(candidates+duty_anchor)
    by_emp_day=index_candidates_by_employee_day(candidates+duty_anchor)
    index_ms += int(round((perf_counter()-t_idx2)*1000))
    gaps=[]
    start_choice_vars=0
    t_assign=perf_counter()
    for o in occ:
        starts=list(range(o['earliest']-lo,o['latest']-lo+1,rules['flexibilityStep']))
        start=model.new_int_var_from_domain(cp_model.Domain.from_values(starts),'start:'+o['id'])
        duration=o['task']['minutes']
        end=model.new_int_var(starts[0]+duration,starts[-1]+duration,'end:'+o['id'])
        model.add(end==start+duration)
        packed=support_options_for_occurrence(o, employees, by_emp_cand, data, reserve, by_emp_day)
        support_before+=packed['before']
        support_after+=packed['after']
        start_bools=None
        if encoding=='start_choice':
            start_bools=[]
            for t in starts:
                sb=model.new_bool_var(f'startchoice:{o["id"]}:{t}')
                start_bools.append((t, sb))
                start_choice_vars+=1
            model.add(sum(sb for _,sb in start_bools)==1)
            model.add(start==sum(t*sb for t,sb in start_bools))
        assigns=[]
        for e, pairs in packed['per_emp']:
            selected=model.new_bool_var('assign:'+o['id']+':'+e['id'])
            assign_vars+=1
            hint_bools.append(selected)
            if encoding=='start_choice':
                for t, sb in start_bools:
                    xs=[c['x'] for c,a,b in pairs if t+lo>=a and t+lo+duration<=b]
                    if xs:
                        model.add(sum(xs)>=selected).only_enforce_if(sb)
                    else:
                        model.add(selected==0).only_enforce_if(sb)
            else:
                options=[]
                for c,a,b in pairs:
                    z=model.new_bool_var('support:'+str(supports_count));supports_count+=1
                    if supports_count>effective_max_support_combinations(data):
                        raise ValueError('För många möjliga insatstilldelningar. Förkorta perioden.')
                    model.add(z<=c['x'])
                    model.add(start>=a-lo).only_enforce_if(z)
                    model.add(end<=b-lo).only_enforce_if(z)
                    options.append(z)
                    hint_bools.append(z)
                if not options:
                    continue
                model.add(sum(options)==selected)
            interval=model.new_optional_interval_var(start,duration,end,selected,'task:'+o['id']+':'+e['id'])
            per_employee[e['id']].append(interval)
            assigns.append((e['id'],selected))
            customer_links.setdefault((o['task']['customerId'],e['id']),[]).append(selected)
        gap=model.new_int_var(0,o['count'],'uncovered:'+o['id'])
        model.add(sum(x for _,x in assigns)+gap==o['count'])
        gaps.append((o,gap))
        task_vars.append((o,start,end,assigns))
    assignment_ms=int(round((perf_counter()-t_assign)*1000))
    support_build_ms=int(round((perf_counter()-t_support)*1000))
    for intervals in per_employee.values():
        model.add_no_overlap(intervals)

    wages={e['id']:e['hourlyCost'] if e['hourlyCost'] is not None else data['economy']['hourlyCost'] for e in employees}
    emp_by_id={e['id']:e for e in data['employees']}
    def billed(c):
        emp=emp_by_id.get(c['shift']['employeeId']) or {}
        if emp.get('resourceType')=='temporary':
            return intersect(c['a'], c['b'], lo, hi)
        return min_period(c)
    cost=sum(round(billed(c)/60*wages[c['shift']['employeeId']]*100)*c['x'] for c in candidates)
    links=[]
    for (customer,employee),xs in customer_links.items():
        used=model.new_bool_var('continuity:'+customer+':'+employee)
        model.add_max_equality(used,xs); links.append(used)
    spread=0
    if utilisations:
        mx=model.new_int_var(0,1000,'max_util');mn=model.new_int_var(0,1000,'min_util')
        model.add_max_equality(mx,utilisations);model.add_min_equality(mn,utilisations)
        spread=mx-mn
    ow=data.get('objectiveWeights') or {}
    continuity_ore=int(round(float(ow.get('continuitySek',50))*100))
    spread_ore=int(round(float(ow.get('spreadSekPerPermille',2.5))*100))
    prefer_ore=int(round(float(ow.get('preferredMissSek',1))*100))
    c6_ore=int(round(float(ow.get('consecutive6Sek',20))*100))
    c7_ore=int(round(float(ow.get('consecutive7Sek',80))*100))
    n3_ore=int(round(float(ow.get('nightSeries3Sek',30))*100))
    n4_ore=int(round(float(ow.get('nightSeries4Sek',90))*100))
    pair_ore=int(round(float(ow.get('missingPairOffSek',25))*100))
    minoff_ore=int(round(float(ow.get('missingMinOffSek',40))*100))
    quality_extra=0
    rest_target=rest_days_target(rules)
    known_from, known_to = f01_known_span(data)
    for e in employees:
        packed=workday_flags.get(e['id'])
        if not packed:
            continue
        flags, flag_days, forced=packed
        period_idx=[i for i,d in enumerate(flag_days) if wp['start']<=d<=wp['end']]
        period_flags=[flags[i] for i in period_idx]
        max_work=28-rest_target
        for i in range(len(flags)-27):
            start_w, end_w = flag_days[i], flag_days[i+27]
            if end_w < wp['start'] or start_w > wp['end']:
                continue
            if not f01_window_known(start_w, end_w, known_from, known_to):
                continue
            locked_n=sum(forced[i:i+28])
            model.add(sum(flags[i:i+28])<=max(max_work, locked_n))
        for i in range(len(flags)-5):
            if not any(wp['start']<=flag_days[i+j]<=wp['end'] for j in range(6)):
                continue
            six=model.new_bool_var(f'c6:{e["id"]}:{i}')
            s=sum(flags[i:i+6])
            model.add(s>=6).only_enforce_if(six)
            model.add(s<=5).only_enforce_if(six.Not())
            quality_extra += c6_ore*six
        for i in range(len(flags)-6):
            if not any(wp['start']<=flag_days[i+j]<=wp['end'] for j in range(7)):
                continue
            sev=model.new_bool_var(f'c7:{e["id"]}:{i}')
            s=sum(flags[i:i+7])
            model.add(s>=7).only_enforce_if(sev)
            model.add(s<=6).only_enforce_if(sev.Not())
            quality_extra += c7_ore*sev
        if pair_ore and len(period_flags)>=2:
            pairs=[]
            for i in range(len(period_flags)-1):
                p=model.new_bool_var(f'pair:{e["id"]}:{i}')
                model.add(period_flags[i]==0).only_enforce_if(p)
                model.add(period_flags[i+1]==0).only_enforce_if(p)
                pairs.append(p)
            if pairs:
                has_pair=model.new_bool_var(f'haspair:{e["id"]}')
                model.add_max_equality(has_pair, pairs)
                quality_extra += pair_ore*(1-has_pair)
        need=int(soft_constraints(e).get('minConsecutiveOffDays') or 0)
        if need>=1 and len(period_flags)>=need:
            wins=[]
            for i in range(len(period_flags)-need+1):
                w=model.new_bool_var(f'softminoff:{e["id"]}:{i}')
                for j in range(need):
                    model.add(period_flags[i+j]==0).only_enforce_if(w)
                wins.append(w)
            if wins:
                ok=model.new_bool_var(f'softminoffok:{e["id"]}')
                model.add_max_equality(ok, wins)
                quality_extra += minoff_ore*(1-ok)
        packed_n=night_series_flags.get(e['id'])
        if packed_n and (n3_ore or n4_ore):
            nflags, ndays=packed_n
            for i in range(len(nflags)-2):
                if not any(wp['start']<=ndays[i+j]<=wp['end'] for j in range(3)):
                    continue
                three=model.new_bool_var(f'n3:{e["id"]}:{i}')
                s=sum(nflags[i:i+3])
                model.add(s>=3).only_enforce_if(three)
                model.add(s<=2).only_enforce_if(three.Not())
                quality_extra += n3_ore*three
            for i in range(len(nflags)-3):
                if not any(wp['start']<=ndays[i+j]<=wp['end'] for j in range(4)):
                    continue
                four=model.new_bool_var(f'n4:{e["id"]}:{i}')
                s=sum(nflags[i:i+4])
                model.add(s>=4).only_enforce_if(four)
                model.add(s<=3).only_enforce_if(four.Not())
                quality_extra += n4_ore*four
    prefer_miss=0
    for e in employees:
        prefs=((e.get('constraints') or {}).get('soft') or {}).get('preferredCustomerIds') or []
        types=((e.get('constraints') or {}).get('soft') or {}).get('preferredTypes') or []
        for cid in prefs:
            xs=customer_links.get((cid,e['id'])) or []
            if not xs: continue
            used=model.new_bool_var('prefer:'+e['id']+':'+cid)
            model.add_max_equality(used,xs)
            prefer_miss += 1-used
        if types:
            typed=[c['x'] for c in candidates if c['shift']['employeeId']==e['id'] and c['shift'].get('type') in types]
            other=[c['x'] for c in candidates if c['shift']['employeeId']==e['id'] and c['shift'].get('type') not in types]
            if typed and other:
                prefer_miss += sum(other)
        reqs=hard_constraints(e).get('requiredCustomerIds') or []
        for cid in reqs:
            xs=customer_links.get((cid,e['id'])) or []
            if xs:
                model.add(sum(xs)>=1)
            else:
                weekend_notes.append(f"{e['code']}: måste arbeta med kund {cid} men saknar giltig tilldelning.")
    if mode=='generateFromNeeds':
        preferred=int(rules.get('preferredMinShiftMinutes') or 4*60)
        for c in candidates:
            if c['shift'].get('type')=='jour':
                continue
            short=preferred-(c['b']-c['a'])
            if short>0:
                quality_extra += int(short)*c['x']
    uncovered_minutes=sum(o['task']['minutes']*gap for o,gap in gaps)
    max_unc=max(1,sum(o['task']['minutes']*o['count'] for o,_ in gaps))
    unc_var=model.new_int_var(0,max_unc,'uncovered_minutes')
    model.add(unc_var==uncovered_minutes)
    cost_var=model.new_int_var(0,10**12,'cost_ore')
    model.add(cost_var==cost)
    qual_var=model.new_int_var(0,10**12,'quality_ore')
    model.add(qual_var==continuity_ore*sum(links)+spread_ore*spread+prefer_ore*prefer_miss+quality_extra)
    for o,start,end,_ in task_vars:
        first=o['earliest']-lo
        model.add_hint(start,first)
        model.add_hint(end,first+o['task']['minutes'])
    lns_freeze=dict(freeShiftVars=0, frozenShiftOne=0, frozenShiftZero=0)
    if lns_free_keys is not None:
        free=set(lns_free_keys)
        inc=set()
        for s in (lns_incumbent_shifts or []):
            inc.add((s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'), s.get('type') or ''))
            if s.get('id'):
                inc.add(s['id'])
        for c in candidates:
            s=c['shift']
            key=(s.get('employeeId'), s.get('date'))
            tup=(s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'), s.get('type') or '')
            if key in free:
                lns_freeze['freeShiftVars']+=1
                if s.get('id') in inc or tup in inc:
                    model.add_hint(c['x'], 1)
                continue
            if s.get('id') in inc or tup in inc:
                model.add(c['x']==1)
                lns_freeze['frozenShiftOne']+=1
            else:
                model.add(c['x']==0)
                lns_freeze['frozenShiftZero']+=1
    elif lns_incumbent_shifts:
        inc=set()
        for s in lns_incumbent_shifts:
            inc.add((s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'), s.get('type') or ''))
            if s.get('id'):
                inc.add(s['id'])
        for c in candidates:
            s=c['shift']
            tup=(s.get('employeeId'), s.get('date'), s.get('start'), s.get('end'), s.get('type') or '')
            if s.get('id') in inc or tup in inc:
                model.add_hint(c['x'], 1)
    proto=model.Proto()
    nvars=len(proto.variables)
    ncons=len(proto.constraints)
    model_build_ms=int(round((perf_counter()-t_model)*1000))
    if build_only:
        extra_perf=dict(
            modelBuildTotalMs=model_build_ms,
            assignmentVariables=assign_vars,
            supportCombinationsBeforePruning=support_before,
            supportCombinationsAfterPruning=support_after,
            totalVariables=nvars,
            totalConstraints=ncons,
            solverMs=0,
            requestedSolveBudgetMs=0,
            buildOnly=True,
            occurrenceEncoding=encoding,
            startChoiceVariables=start_choice_vars,
            supportVariablesCreated=supports_count,
            lnsFreeze=lns_freeze,
        )
        diag=diagnostics('NOT_RUN', 0, nvars, ncons, 0, None, None, extra_perf)
        return dict(
            schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus='NOT_RUN',explanation='Modell byggd utan Solve().'),
            validation=None,
            modelScope=dict(candidateShifts=len(candidates),occurrences=len(occ),startStep=rules['flexibilityStep'],**diag),
            diagnostics=dict(performance=diag),
            summary=None,
        )
    requested_ms=int(round(seconds*1000))
    remaining_before=[]
    timeout_reason=None
    solver_deadline=perf_counter()+seconds
    phases=[]
    last=None
    last_solver=None
    coverage_locked=False
    cost_locked=False
    coverage_incumbent=False
    cost_incumbent=False
    hints_per_phase=[]
    coverage_slice=max(1.0, seconds*COVERAGE_SHARE)
    phase0_budget=min(ZERO_GAP_PHASE0_MAX_S, coverage_slice)

    def snapshot(sv,code,phase):
        cost_val=int(sv.value(cost_var))
        cont_val=continuity_ore*sum(sv.value(x) for x in links)
        spread_val=spread_ore*(sv.value(spread) if utilisations else 0)
        try:
            obj=sv.objective_value
        except Exception:
            obj=sv.value(unc_var)
        try:
            bnd=sv.best_objective_bound
        except Exception:
            bnd=None
        return dict(
            code=code,
            phase=phase,
            seconds=sv.wall_time,
            objective=obj,
            bound=bnd,
            shifts=[c['shift'] for c in candidates if sv.value(c['x'])],
            assignments=[dict(occurrenceId=o['id'],employeeId=e,start=sv.value(start)+lo,end=sv.value(end)+lo) for o,start,end,assigns in task_vars for e,x in assigns if sv.value(x)],
            uncovered=[dict(occurrenceId=o['id'],name=o['task']['name'],date=o['date'],minutes=o['task']['minutes'],count=sv.value(gap)) for o,gap in gaps if sv.value(gap)],
            uncoveredMinutes=int(sv.value(unc_var)),
            costOre=cost_val,
            continuityOre=int(cont_val),
            spreadOre=int(spread_val),
            qualityOre=int(sv.value(qual_var)),
            proven=code=='OPTIMAL',
            solver=sv,
        )

    def apply_incumbent_hints(sv, target=None, only_ones=False):
        """Skift-booler. Support/start-hints har gett MODEL_INVALID i nästa fas."""
        dest=target if target is not None else model
        n=0
        for c in candidates:
            if isinstance(c['x'], int):
                continue
            val=int(sv.value(c['x']))
            if val not in (0, 1):
                continue
            if only_ones and val!=1:
                continue
            var=c['x']
            if dest is not model:
                var=dest.get_bool_var_from_proto_index(c['x'].index)
            dest.add_hint(var, val)
            n+=1
        return n

    def zero_gap_clone(shift_ones=None):
        """Separat modell: originalet får aldrig kvarvarande unc==0 vid fallback."""
        sat=model.clone()
        sat.add(sat.get_int_var_from_proto_index(unc_var.index)==0)
        n=0
        for _,gap in gaps:
            sat.add_hint(sat.get_int_var_from_proto_index(gap.index), 0)
            n+=1
        if shift_ones:
            for idx in shift_ones:
                sat.add_hint(sat.get_bool_var_from_proto_index(idx), 1)
                n+=1
        return sat, n

    def run_phase(name,objective=None,lock=None,mdl=None,limit_s=None,hinted_already=0):
        nonlocal last, last_solver, timeout_reason
        left=solver_deadline-perf_counter()
        remaining_before.append(dict(phase=name, remainingBudgetBeforePhaseMs=max(0,int(round(left*1000)))))
        if left<0.5:
            timeout_reason='budget_exhausted_before_phase'
            phases.append(dict(name=name,status='SKIPPED',seconds=0,actualMs=0,limitMs=0,remainingBeforeMs=max(0,int(round(left*1000)))))
            hints_per_phase.append(dict(phase=name, hintVariablesApplied=hinted_already))
            return None
        if limit_s is not None:
            planned=limit_s
        elif name=='coverage':
            planned=max(1.0, coverage_slice)
        elif name=='cost':
            if last and last.get('uncoveredMinutes')==0:
                planned=min(left, 12.0)
            else:
                planned=min(left, max(8.0, seconds*0.35))
        else:
            planned=min(left, 8.0 if (last and last.get('uncoveredMinutes')==0) else 12.0)
        limit=max(1.0, min(planned, left))
        if lock is not None:
            lock()
        use=mdl if mdl is not None else model
        if objective is not None:
            use.minimize(objective)
        sv=cp_model.CpSolver()
        sv.parameters.num_search_workers=8
        sv.parameters.random_seed=41
        sv.parameters.max_time_in_seconds=limit
        if sat_params:
            for key, val in sat_params.items():
                setattr(sv.parameters, key, val)
        cb=None
        t_ph=perf_counter()
        if name=='coverage' and coverage_trace is not None:
            cb=_CoverageTrace(unc_var, coverage_trace)
            sv.parameters.log_search_progress=True
            def _log(line):
                low=(line or '').lower()
                if any(k in low for k in ('bound', 'obj', 'conflict', 'presolv', 'solution', 'branch')):
                    coverage_trace.append(dict(
                        event='log',
                        t=round(perf_counter()-t_ph, 3),
                        line=(line or '')[:500],
                    ))
            sv.log_callback=_log
        st=sv.solve(use, cb) if cb is not None else sv.solve(use)
        actual_ms=int(round((perf_counter()-t_ph)*1000))
        code=sv.status_name(st)
        if name=='coverage' and coverage_trace is not None:
            try:
                bnd=float(sv.best_objective_bound)
            except Exception:
                bnd=None
            try:
                inc=int(sv.value(unc_var)) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
            except Exception:
                inc=None
            coverage_trace.append(dict(
                event='phase_end',
                t=round(actual_ms/1000, 3),
                status=code,
                incumbent=inc,
                bound=bnd,
                conflicts=int(getattr(sv, 'num_conflicts', 0) or 0),
                branches=int(getattr(sv, 'num_branches', 0) or 0),
                wall=float(sv.wall_time) if hasattr(sv, 'wall_time') else actual_ms/1000,
            ))
        try:
            wall=float(sv.wall_time)
        except Exception:
            wall=actual_ms/1000
        phases.append(dict(name=name,status=code,seconds=wall,actualMs=actual_ms,limitMs=int(round(limit*1000)),remainingBeforeMs=max(0,int(round(left*1000)))))
        last_solver=sv
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            last=snapshot(sv,code,name)
            hinted=hinted_already
            if name in ('coverage','zeroGap','zeroGapB') and use is model:
                hinted=apply_incumbent_hints(sv)
            hints_per_phase.append(dict(phase=name, hintVariablesApplied=hinted))
            return last
        hints_per_phase.append(dict(phase=name, hintVariablesApplied=hinted_already))
        if last is None:
            if actual_ms+50<limit*1000*0.4:
                timeout_reason=timeout_reason or 'early_unknown'
            else:
                timeout_reason=timeout_reason or 'time_limit'
        return None

    t_solve=perf_counter()
    sat0, gap0_hints=zero_gap_clone()
    zero=run_phase('zeroGap', objective=None, mdl=sat0, limit_s=phase0_budget, hinted_already=gap0_hints)
    used_coverage=sum(p.get('actualMs') or 0 for p in phases if p['name'] in ('zeroGap','coverage','zeroGapB'))/1000
    if zero and last and last.get('uncoveredMinutes')==0:
        model.add(unc_var==0)
        apply_incumbent_hints(last_solver, only_ones=True)
    else:
        last=None
        last_solver=None
        remain_cov=max(1.0, solver_deadline-perf_counter())
        run_phase('coverage', unc_var, limit_s=remain_cov)
        used_coverage=sum(p.get('actualMs') or 0 for p in phases if p['name'] in ('zeroGap','coverage','zeroGapB'))/1000
        if last and last.get('uncoveredMinutes') and last.get('uncoveredMinutes')>0 and lex_stop!='coverage':
            bound=last.get('bound')
            bound0=(bound is None) or (float(bound)<=1e-9)
            if bound0:
                ones=[c['x'].index for c in candidates if not isinstance(c['x'], int) and int(last_solver.value(c['x']))==1]
                satb, n_hints=zero_gap_clone(shift_ones=ones)
                remain=solver_deadline-perf_counter()
                lim_b=min(ZERO_GAP_PHASE0B_MAX_S, max(1.0, remain), max(8.0, coverage_slice-used_coverage))
                prev=last
                found=run_phase('zeroGapB', objective=None, mdl=satb, limit_s=lim_b, hinted_already=n_hints)
                if found and last and last.get('uncoveredMinutes')==0:
                    model.add(unc_var==0)
                    apply_incumbent_hints(last_solver, only_ones=True)
                else:
                    last=prev
                    phases[-1]['keptPreviousIncumbent']=True if phases and phases[-1]['name']=='zeroGapB' else False
    if last and lex_stop!='coverage' and coverage_ready_for_cost(last):
        coverage_incumbent=True
        best_unc=last['uncoveredMinutes']
        def _lock_cov():
            nonlocal coverage_locked
            model.add(unc_var<=best_unc)
            model.add(unc_var>=best_unc)
            coverage_locked=True
        run_phase('cost', cost_var, _lock_cov)
    if last and lex_stop!='coverage' and coverage_ready_for_cost(last):
        cost_incumbent=True
        best_cost=last['costOre']
        def _lock_cost():
            nonlocal cost_locked
            model.add(cost_var<=best_cost)
            model.add(cost_var>=best_cost)
            cost_locked=True
        run_phase('quality', qual_var, _lock_cost)
    solve_ms=int(round((perf_counter()-t_solve)*1000))
    fallback_status=phases[-1]['status'] if phases else 'UNKNOWN'
    code=(last or {}).get('code') or fallback_status
    if last and all(p['status']=='OPTIMAL' for p in phases if p['status']!='SKIPPED'):
        code='OPTIMAL'
    elif last:
        code='FEASIBLE'
    if timeout_reason=='budget_exhausted_before_phase' and not last:
        timeout_reason='budget_exhausted_before_phase'
    explanations={
        'OPTIMAL':'Bevisat lexikografiskt optimal: maximal kundtäckning, därefter lägsta kostnad, därefter kvalitet, inom valda passmallar och tidssteg. Granska förslaget innan du godkänner.',
        'FEASIBLE':'En giltig lösning hittades med lexikografisk prioritering (täckning före kostnad före kvalitet). Bästa möjliga lösning är inte bevisad inom tidsgränsen.',
        'INFEASIBLE':'Ingen lösning uppfyller alla hårda villkor inom valda passmallar och tidssteg. Kontrollera behov, kompetens, tillgänglighet och passmallar. Inga regler har lättats.',
        'UNKNOWN':'Sökningen avbröts vid tidsgränsen utan en hittad lösning. Detta bevisar inte att problemet är olösbart.',
        'MODEL_INVALID':'Optimeringsmodellen är ogiltig. Inget schemaförslag kan användas.'}
    explanation=explain_with_precheck(code, diagnoses, explanations.get(code,'Okänd beräkningsstatus.'), locked=bool(locked_shifts))
    if timeout_reason=='budget_exhausted_before_phase':
        explanation='Global tidsbudget var redan förbrukad när en solverfas skulle starta. '+explanation
    elif timeout_reason=='early_unknown':
        explanation=explanation+' CP-SAT återvände UNKNOWN långt före den avsedda fasbudgeten.'
    if weekend_notes:
        explanation=explanation+' Helgförvarning: '+'; '.join(weekend_notes)
    pruned_pct=round(100.0*(support_before-support_after)/support_before, 2) if support_before else 0.0
    extra_perf=dict(
        requestedSolveBudgetMs=requested_ms,
        remainingBudgetBeforeEachPhaseMs=remaining_before,
        totalSolverMs=solve_ms,
        timeoutReason=timeout_reason,
        deadlineReason=timeout_reason,
        solverBudgetStartsAfterModelBuild=True,
        supportCombinationsBeforePruning=support_before,
        supportCombinationsAfterPruning=support_after,
        supportPrunedPercent=pruned_pct,
        assignmentVariables=assign_vars,
        totalVariables=nvars,
        totalConstraints=ncons,
        generationMs=generate_ms,
        precheckMs=pre_ms,
        supportBuildMs=support_build_ms,
        assignmentBuildMs=assignment_ms,
        indexBuildMs=index_ms,
        constraintBuildMs=constraint_ms,
        modelBuildTotalMs=model_build_ms,
        generatedShiftTemplatesBeforePruning=tpl_prune.get('generatedShiftTemplatesBeforePruning', generated_n),
        generatedShiftTemplatesAfterPruning=tpl_prune.get('generatedShiftTemplatesAfterPruning', generated_n),
        generatedShiftPrunedPercent=tpl_prune.get('generatedShiftPrunedPercent', 0),
        shiftVariablesBeforePruning=shift_vars_before,
        shiftVariablesAfterPruning=shift_vars_after,
        coverageTargetLocked=coverage_locked,
        costTargetLocked=cost_locked,
        coverageIncumbentAvailable=coverage_incumbent,
        costIncumbentAvailable=cost_incumbent,
        hintVariablesAppliedPerPhase=hints_per_phase,
        occurrenceEncoding=encoding,
        startChoiceVariables=start_choice_vars,
        supportVariablesCreated=supports_count,
        lnsFreeze=lns_freeze,
        solverMs=solve_ms,
        validationMs=0,
        totalMs=0,
    )
    schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus=code,explanation=explanation,feasibilityNotes=weekend_notes,preCheck=diagnoses,seconds=sum((p.get('actualMs') or 0)/1000 for p in phases),objective=None,bound=None)
    if jour_payload is not None:
        schedule['resourceDiagnostics']=dict(jour=jour_payload)
    result=None
    validate_ms=0
    kpis=None
    if last:
        seen={s['id'] for s in last['shifts']}
        schedule['shifts']=[s for s in locked_shifts if s['id'] not in seen]+list(last['shifts'])
        schedule['assignments']=last['assignments']
        schedule['uncovered']=last['uncovered']
        schedule['uncoveredMinutes']=last['uncoveredMinutes']
        schedule['objective']=last['objective']
        schedule['bound']=last['bound']
        schedule['objectiveBreakdown']=dict(costOre=last['costOre'],continuityOre=last['continuityOre'],spreadOre=last['spreadOre'],uncoveredMinutes=last['uncoveredMinutes'])
        schedule['lexicographic']=dict(
            uncoveredMinutes=last['uncoveredMinutes'],
            costOre=last['costOre'],
            qualityOre=last['qualityOre'],
            coverageProven=int(last['uncoveredMinutes'] or 0)==0,
            phases=phases,
        )
        t_val=perf_counter()
        result=validate(data,schedule)
        validate_ms=int(round((perf_counter()-t_val)*1000))
        blocking=[e for e in result['errors'] if e['rule']!='BOUNDARY_INCOMPLETE']
        if blocking:
            schedule.update(solverStatus='MODEL_INVALID',shifts=[],assignments=[],explanation='Förslaget stoppades av den fristående kontrollen: '+blocking[0]['message'])
        else:
            kpis=schedule_kpis(data, schedule)
    extra_perf['validationMs']=validate_ms
    extra_perf['totalMs']=int(round((perf_counter()-t0)*1000))
    diag=diagnostics(schedule['solverStatus'], solve_ms, nvars, ncons, validate_ms, kpis, phases, extra_perf)
    scope=dict(candidateShifts=len(candidates),occurrences=len(occ),startStep=rules['flexibilityStep'],**diag)
    summary=planning_summary(data, schedule, result, diag)
    out=dict(schedule=schedule,validation=result,modelScope=scope,diagnostics=dict(performance=diag),summary=summary,lnsFreeze=lns_freeze)
    if jour_payload is not None:
        out['resourceDiagnostics']=dict(jour=jour_payload)
    return out
