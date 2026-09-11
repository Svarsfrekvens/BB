"""CP-SAT solver. Hard rules are constraints, never penalty terms.

Lexikografisk optimering: (1) minimera obemannat kundbehov,
(2) minimera personalkostnad, (3) minimera kontinuitet/spridning.
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
                     rest_days_target, f01_known_span, f01_window_known,
                     candidate_as_shift, jour_eligible, night_eligible, occasion_profile_id,
                     shift_profiles, required_rest_after_minutes)
from .generate import generated_template_stats, planning_mode, shift_templates_for_solve
from .precheck import (
    enumerate_person_shift_slots, explain_with_precheck, feasibility_precheck,
    has_critical_precheck, planning_diagnostics,
)
from .replan import collect_locked_shifts
from .perf import peak_memory_mb, schedule_kpis
from .validate import validate


def _as_bool(model, x, name):
    if isinstance(x, int):
        v = model.new_bool_var(name)
        model.add(v == (1 if x else 0))
        return v
    return x


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


def solve(data, seconds=30):
    from ortools.sat.python import cp_model
    check_input(data)
    seconds = min(300, max(1, float(seconds)))
    wp, rules = data['workplace'], data['rules']
    lo,hi = instant(wp['start'],'00:00'),instant(add_days(wp['end'],1),'00:00')
    period_days=list(days(wp['start'],wp['end']))
    employees=[e for e in data['employees'] if e['status']=='active']
    t0=perf_counter()
    t_gen=perf_counter()
    template_list=shift_templates_for_solve(data)
    generate_ms=int(round((perf_counter()-t_gen)*1000))
    templates={t['id']:t for t in template_list}
    occ=occurrences(data)
    reserve=int(rules.get('withinPassMinutesPerShift') or 0)
    mode=planning_mode(data)
    tpl_stats=generated_template_stats(template_list)
    locked_shifts=collect_locked_shifts(data)

    t_pre=perf_counter()
    diagnoses=feasibility_precheck(data)
    pre_ms=int(round((perf_counter()-t_pre)*1000))
    enum=enumerate_person_shift_slots(data, template_list)
    generated_n=tpl_stats.get('total') or sum(1 for t in templates.values() if t.get('generated'))

    def diagnostics(status, solve_ms=0, nvars=0, ncons=0, validate_ms=0, kpis=None, phases=None):
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
        if phases:
            by={p['name']:int(round(float(p.get('seconds') or 0)*1000)) for p in phases}
            extra['coveragePhaseMs']=by.get('coverage',0)
            extra['costPhaseMs']=by.get('cost',0)
            extra['qualityPhaseMs']=by.get('quality',0)
        if kpis:
            extra.update(kpis)
        return planning_diagnostics(data, extra)

    def empty_infeasible(message, status='INFEASIBLE'):
        explanation=explain_with_precheck(status, diagnoses, message, locked=bool(locked_shifts))
        diag=diagnostics(status)
        schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus=status,explanation=explanation,feasibilityNotes=[],preCheck=diagnoses,seconds=pre_ms/1000,objective=None,bound=None)
        return dict(schedule=schedule,validation=None,modelScope=dict(candidateShifts=0,occurrences=len(occ),startStep=rules['flexibilityStep'],**diag),diagnostics=dict(performance=diag))

    if has_critical_precheck(diagnoses):
        return empty_infeasible('Ingen lösning uppfyller alla hårda villkor.')

    def shrink_work(intervals, take):
        if take<=0: return list(intervals)
        left,out=take,[]
        for a,b in intervals:
            if left<=0:
                out.append((a,b)); continue
            cut=min(left,b-a)
            if a+cut<b: out.append((a+cut,b))
            left-=cut
        return out

    weekend_notes=[]
    from datetime import date as _date
    for day in period_days:
        if _date.fromisoformat(day).isoweekday() not in (6,7): continue
        need=[o for o in occ if o['date']==day]
        if not need: continue
        eligible=[e for e in employees if weekend_allowed(e,day)]
        if not eligible:
            weekend_notes.append(f'{day}: helgbehov finns men ingen medarbetare får arbeta enligt helgmönstret.')
            continue
        for o in need:
            if not any(set(o['task']['skills'])<=skills_on_day(e,day) for e in eligible):
                weekend_notes.append(f'{day}: {o["task"]["name"]} saknar helgbehörig kompetens.')

    jour_floor=int(rules.get('jourFloor') or 0)
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
        candidates.append(dict(shift=s,a=a,b=b,work=work,x=x,generated=bool(t.get('generated'))))
    if len(candidates)>10000:
        raise ValueError('För många passalternativ. Begränsa personal, passmallar eller period.')

    def min_period(c):
        return sum(intersect(a,b,lo,hi) for a,b in c['work'])

    utilisations=[]
    workday_flags={}
    night_series_flags={}
    for e in employees:
        rows=sorted((c for c in candidates if c['shift']['employeeId']==e['id']),key=lambda c:c['a'])
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
                if shifts_mergeable(candidate_as_shift(a), candidate_as_shift(b)):
                    continue
                bridges=[c for c in items[i+1:j] if a['b']<=c['a'] and c['b']<=b['a']
                         and shifts_mergeable(candidate_as_shift(a), candidate_as_shift(c))
                         and shifts_mergeable(candidate_as_shift(c), candidate_as_shift(b))]
                if bridges:
                    model.add(ax+bx<=1+sum(lit(c['x'], f'br:{e["id"]}:{i}:{j}:{t}') for t,c in enumerate(bridges)))
                else:
                    model.add(ax+bx<=1)
        for i in range(n_items):
            chain=[items[i]]
            for k in range(i+1, n_items):
                nxt=items[k]
                if overlap(chain[-1]['a'], chain[-1]['b'], nxt['a'], nxt['b']):
                    continue
                if not shifts_mergeable(candidate_as_shift(chain[-1]), candidate_as_shift(nxt)):
                    if nxt['a']>=chain[-1]['b']:
                        break
                    continue
                chain.append(nxt)
                types={c['shift'].get('type') for c in chain}
                if 'jour' not in types or not (types-{'jour'}):
                    continue
                rest_after=required_rest_after_minutes([candidate_as_shift(c) for c in chain], rules)
                if rest_after<=0:
                    continue
                xs_chain=[lit(c['x'], f'compc:{e["id"]}:{i}:{len(chain)}:{t}') for t,c in enumerate(chain)]
                for t in range(k+1, n_items):
                    later=items[t]
                    if later['a']>=chain[-1]['b']+rest_after:
                        break
                    if shifts_mergeable(candidate_as_shift(chain[-1]), candidate_as_shift(later)):
                        continue
                    lx=lit(later['x'], f'compl:{e["id"]}:{i}:{len(chain)}:{t}')
                    model.add(sum(xs_chain)+lx<=len(chain))
        cap=floor(ssg_cap_minutes(e,period_days,rules,wp)+1e-7)
        used=sum(min_period(c)*c['x'] for c in rows)+sum(min_period(c) for c in fixed)
        model.add(used<=cap)
        if cap>0:
            util=model.new_int_var(0,1000,'util:'+e['id'])
            used_var=model.new_int_var(0,cap,'paid_minutes:'+e['id'])
            model.add(used_var==used)
            model.add_division_equality(util,used_var*1000,cap)
            utilisations.append(util)
        for week in {monday(day) for day in period_days}:
            wa,wb=instant(week,'00:00'),instant(add_days(week,7),'00:00')
            model.add(sum(sum(intersect(a,b,wa,wb) for a,b in c['work'])*c['x'] for c in rows+fixed)<=floor(rules['maxWeeklyHours']*60))
        flags=[]
        flag_days=list(days(add_days(wp['start'],-27),add_days(wp['end'],27)))
        flags=_schedule_workday_flags(model, rows+fixed, flag_days, 'wd:'+e['id'])
        legal=rules.get('hardMaxConsecutiveDays')
        if legal:
            w=int(legal)+1
            for i in range(len(flags)-w+1):
                model.add(sum(flags[i:i+w])<=int(legal))
        person_cap=hard_constraints(e).get('maxConsecutiveDays')
        if person_cap:
            w=int(person_cap)+1
            for i in range(len(flags)-w+1):
                model.add(sum(flags[i:i+w])<=int(person_cap))
        workday_flags[e['id']]=(flags,flag_days)
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
            for w in range(1, lim+2):
                for i in range(len(ncounts)-w+1):
                    model.add(sum(ncounts[i:i+w])<=lim)
        night_series_flags[e['id']]=(nflags, night_span_days)
        min_off=hard_constraints(e).get('minConsecutiveOffDays')
        if min_off:
            need=int(min_off)
            period_flags=flags[27:27+len(period_days)]
            if need<=len(period_flags):
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
            for w in range(1, lim+2):
                for i in range(len(jcounts)-w+1):
                    model.add(sum(jcounts[i:i+w])<=lim)
        for start_day in sorted({c['shift']['date'] for c in jour_rows}):
            limit=add_days(start_day,27)
            model.add(sum((c['b']-c['a'])*c['x'] for c in jour_rows if start_day<=c['shift']['date']<=limit)<=48*60)
        per_manad={}
        for c in jour_rows:
            per_manad.setdefault(c['shift']['date'][:7],[]).append(c)
        for grupp in per_manad.values():
            model.add(sum((c['b']-c['a'])*c['x'] for c in grupp)<=50*60)

    # Awake-night floor counts on-duty, eligible people. Rest constraints prevent
    # a person from being counted through two simultaneous candidate shifts.
    for a,b in night_intervals(wp['start'],wp['end']):
        a,b=max(a,lo),min(b,hi)
        if a>=b or not rules['nightFloor']: continue
        valid_ids={e['id'] for e in employees if night_eligible(e)}
        coverage=[(u,v,c['x']) for c in candidates+duty_anchor if c['shift']['employeeId'] in valid_ids for u,v in c['work']]
        edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
        for edge in edges[:-1]:
            model.add(sum(x for u,v,x in coverage if u<=edge<v)>=rules['nightFloor'])

    if jour_floor:
        valid_ids={e['id'] for e in employees if jour_eligible(e)}
        for a,b in jour_intervals(wp['start'],wp['end'],rules):
            a,b=max(a,lo),min(b,hi)
            if a>=b: continue
            coverage=[(c['a'],c['b'],c['x']) for c in candidates+duty_anchor if c['shift'].get('type')=='jour' and c['shift']['employeeId'] in valid_ids]
            edges=sorted({a,b}|{t for u,v,_ in coverage for t in (u,v) if a<t<b})
            for edge in edges[:-1]:
                model.add(sum(x for u,v,x in coverage if u<=edge<v)>=jour_floor)

    task_vars=[]
    # Ge CP-SAT en omedelbart giltig startpunkt: inga valda pass och allt
    # kundbehov öppet redovisat som obemannat. Utan denna startpunkt kunde den
    # stora Galaxen-modellen använda hela tidsgränsen i presolve/sökning och
    # svara UNKNOWN trots att den mjuka täckningsmodellen alltid har en lösning.
    # Motorn förbättrar därefter startpunkten genom att välja pass och bemanna.
    shift_hints=[]
    support_hints=[]
    per_employee={e['id']:[] for e in employees}
    customer_links={}
    supports_count=0
    gaps=[]
    for o in occ:
        # Start times are real integer minutes. Duration is never rounded.
        starts=list(range(o['earliest']-lo,o['latest']-lo+1,rules['flexibilityStep']))
        start=model.new_int_var_from_domain(cp_model.Domain.from_values(starts),'start:'+o['id'])
        duration=o['task']['minutes']
        end=model.new_int_var(starts[0]+duration,starts[-1]+duration,'end:'+o['id'])
        model.add(end==start+duration)
        assigns=[]
        for e in employees:
            if not set(o['task']['skills'])<=skills_on_day(e, o['date']): continue
            krav = o['task'].get('requiredEmployeeId')
            if krav and e['id'] != krav: continue
            if o['task']['customerId'] in set(hard_constraints(e).get('forbiddenCustomerIds') or []): continue
            candidates_for_e=[c for c in candidates+duty_anchor if c['shift']['employeeId']==e['id']]
            options=[]
            for c in candidates_for_e:
                for a,b in shrink_work(c['work'], reserve):
                    if b-a<duration or b<o['earliest']+duration or a>o['latest']: continue
                    z=model.new_bool_var('support:'+str(supports_count));supports_count+=1
                    support_hints.append(z)
                    if supports_count>120000:
                        raise ValueError('För många möjliga insatstilldelningar. Förkorta perioden.')
                    model.add(z<=c['x'])
                    model.add(start>=a-lo).only_enforce_if(z)
                    model.add(end<=b-lo).only_enforce_if(z)
                    options.append(z)
            if not options: continue
            selected=model.new_bool_var('assign:'+o['id']+':'+e['id'])
            support_hints.append(selected)
            model.add(sum(options)==selected)
            interval=model.new_optional_interval_var(start,duration,end,selected,'task:'+o['id']+':'+e['id'])
            per_employee[e['id']].append(interval)
            assigns.append((e['id'],selected))
            customer_links.setdefault((o['task']['customerId'],e['id']),[]).append(selected)
        # Coverage is a strongly weighted goal, never a silent relaxation of the
        # hard rules: an unstaffed intervention is reported back explicitly.
        gap=model.new_int_var(0,o['count'],'uncovered:'+o['id'])
        model.add(sum(x for _,x in assigns)+gap==o['count'])
        gaps.append((o,gap))
        task_vars.append((o,start,end,assigns))
    for intervals in per_employee.values():
        model.add_no_overlap(intervals)

    wages={e['id']:e['hourlyCost'] if e['hourlyCost'] is not None else data['economy']['hourlyCost'] for e in employees}
    cost=sum(round(min_period(c)/60*wages[c['shift']['employeeId']]*100)*c['x'] for c in candidates)
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
        flags, flag_days=packed
        period_idx=[i for i,d in enumerate(flag_days) if wp['start']<=d<=wp['end']]
        period_flags=[flags[i] for i in period_idx]
        max_work=28-rest_target
        for i in range(len(flags)-27):
            start_w, end_w = flag_days[i], flag_days[i+27]
            if end_w < wp['start'] or start_w > wp['end']:
                continue
            if not f01_window_known(start_w, end_w, known_from, known_to):
                continue
            model.add(sum(flags[i:i+28])<=max_work)
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
    for c in candidates:
        model.add_hint(c['x'],0)
    for x in support_hints:
        model.add_hint(x,0)
    for o,start,end,_ in task_vars:
        first=o['earliest']-lo
        model.add_hint(start,first)
        model.add_hint(end,first+o['task']['minutes'])
    for o,gap in gaps:
        model.add_hint(gap,o['count'])
    proto=model.Proto()
    nvars=len(proto.variables)
    ncons=len(proto.constraints)
    t_cov=max(1.0,seconds*0.45)
    t_cost=max(1.0,seconds*0.35)
    t_qual=max(1.0,max(seconds,t_cov+t_cost+1)-t_cov-t_cost)
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=8
    solver.parameters.random_seed=41
    phases=[]
    last=None

    def snapshot(sv,code,phase):
        cost_val=int(sv.value(cost_var))
        cont_val=continuity_ore*sum(sv.value(x) for x in links)
        spread_val=spread_ore*(sv.value(spread) if utilisations else 0)
        return dict(
            code=code,
            phase=phase,
            seconds=sv.wall_time,
            objective=sv.objective_value,
            bound=sv.best_objective_bound,
            shifts=[c['shift'] for c in candidates if sv.value(c['x'])],
            assignments=[dict(occurrenceId=o['id'],employeeId=e,start=sv.value(start)+lo,end=sv.value(end)+lo) for o,start,end,assigns in task_vars for e,x in assigns if sv.value(x)],
            uncovered=[dict(occurrenceId=o['id'],name=o['task']['name'],date=o['date'],minutes=o['task']['minutes'],count=sv.value(gap)) for o,gap in gaps if sv.value(gap)],
            uncoveredMinutes=int(sv.value(unc_var)),
            costOre=cost_val,
            continuityOre=int(cont_val),
            spreadOre=int(spread_val),
            qualityOre=int(sv.value(qual_var)),
            proven=code=='OPTIMAL',
        )

    def run_phase(name,objective,limit,lock=None):
        nonlocal last
        if lock is not None:
            lock()
        model.minimize(objective)
        solver.parameters.max_time_in_seconds=limit
        st=solver.solve(model)
        code=solver.status_name(st)
        phases.append(dict(name=name,status=code,seconds=solver.wall_time))
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            last=snapshot(solver,code,name)
            return last
        return None

    t_solve=perf_counter()
    run_phase('coverage',unc_var,t_cov)
    if last:
        best_unc=last['uncoveredMinutes']
        run_phase('cost',cost_var,t_cost,lambda: model.add(unc_var<=best_unc))
    if last:
        best_cost=last['costOre']
        run_phase('quality',qual_var,t_qual,lambda: model.add(cost_var<=best_cost))
    solve_ms=int(round((perf_counter()-t_solve)*1000))
    code=(last or {}).get('code') or solver.status_name(cp_model.UNKNOWN)
    if last and all(p['status']=='OPTIMAL' for p in phases):
        code='OPTIMAL'
    elif last:
        code='FEASIBLE'
    explanations={
        'OPTIMAL':'Bevisat lexikografiskt optimal: maximal kundtäckning, därefter lägsta kostnad, därefter kvalitet, inom valda passmallar och tidssteg. Granska förslaget innan du godkänner.',
        'FEASIBLE':'En giltig lösning hittades med lexikografisk prioritering (täckning före kostnad före kvalitet). Bästa möjliga lösning är inte bevisad inom tidsgränsen.',
        'INFEASIBLE':'Ingen lösning uppfyller alla hårda villkor inom valda passmallar och tidssteg. Kontrollera behov, kompetens, tillgänglighet och passmallar. Inga regler har lättats.',
        'UNKNOWN':'Sökningen avbröts vid tidsgränsen utan en hittad lösning. Detta bevisar inte att problemet är olösbart.',
        'MODEL_INVALID':'Optimeringsmodellen är ogiltig. Inget schemaförslag kan användas.'}
    explanation=explain_with_precheck(code, diagnoses, explanations.get(code,'Okänd beräkningsstatus.'), locked=bool(locked_shifts))
    if weekend_notes:
        explanation=explanation+' Helgförvarning: '+'; '.join(weekend_notes)
    schedule=dict(id=str(uuid4()),status='draft',basedOnRevision=data['inputRevision'],shifts=[],assignments=[],uncovered=[],solverStatus=code,explanation=explanation,feasibilityNotes=weekend_notes,preCheck=diagnoses,seconds=sum(p['seconds'] for p in phases) if phases else solver.wall_time,objective=None,bound=None)
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
            coverageProven=any(p['name']=='coverage' and p['status']=='OPTIMAL' for p in phases),
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
    diag=diagnostics(schedule['solverStatus'], solve_ms, nvars, ncons, validate_ms, kpis, phases)
    scope=dict(candidateShifts=len(candidates),occurrences=len(occ),startStep=rules['flexibilityStep'],**diag)
    return dict(schedule=schedule,validation=result,modelScope=scope,diagnostics=dict(performance=diag))
