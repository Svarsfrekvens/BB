"""Joint shifts/breaks/task-start repair, uniform skill pool with handovers.
No business/person/date literals: case.json supplies them. Not a production engine.
"""
import argparse, hashlib, json, time
try:
    import resource
except ImportError:
    resource=None
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model
import ortools
from datetime import datetime
from .common import merge, days, runs

from .person_constraints import add_person_constraints, export_reassignments
from .workload_objectives import add_weekly_peak, export_weekly_workload

def build(case, objective_mode="coverage_then_temporary"):
    cfg=case['config'];H=case['horizon'];step=cfg['shift_step'];K=len(case['staff'])
    start_date=datetime.fromisoformat(case['origin'])
    assert H==28*1440 and start_date.weekday()==0 and start_date.hour==start_date.minute==0 and cfg['week_break']=='MONDAY 00:00', 'This implementation requires a Monday-aligned 28-day period; adapt calendar before other period layouts.'
    assert H%1440==0 and all(p['all_task_skills'] for p in case['staff']), 'Heterogeneous eligibility needs a different encoding; never pool silently.'
    assert all(n['count'] is not None and n['count']>=1 for n in case['needs'])
    model=cp_model.CpModel();fixed=case['fixed_segments'];staff={p['id']:p for p in case['staff']}
    fixed_supply=[0]*H;gross_intervals=[];absence=[];absence_d=[];breakvars=[]
    fixed_net=defaultdict(int)
    for person in staff:
        spans=merge([(r['start'],r['end']) for r in fixed if r['person']==person and r['type']=='AKTIVT_ARBETE'])
        # Overtime is real on-duty presence even when the input scenario excludes it from
        # customer-capacity reuse and ordinary net. Count only its non-Ar union.
        overtime=merge([(r['start'],r['end']) for r in fixed if r['person']==person and r.get('code') in ('Kl','Öv')])
        extra=[0]*H
        for a,b in overtime:
            for t in range(max(0,a),min(H,b)):extra[t]=1
        for a,b in spans:
            for t in range(max(0,a),min(H,b)):extra[t]=0
        for a,b,value in runs(extra):
            if value:gross_intervals.append(model.NewFixedSizeIntervalVar(a,b-a,''))
        for a,b in spans:
            if b<=0 or a>=H:continue
            lo,hi=max(0,a),min(H,b)
            fixed_net[person]+=hi-lo
            for t in range(lo,hi):fixed_supply[t]+=1
            gross_intervals.append(model.NewFixedSizeIntervalVar(lo,hi-lo,''))
            if b-a>cfg['break_threshold']:
                # Minimum count satisfying active chunks within the explicit profile limit; all
                # locations are jointly decided with tasks and variable shifts.
                count=(b-a-cfg['max_continuous_active']+cfg['max_continuous_active']+cfg['break_length']-1)//(cfg['max_continuous_active']+cfg['break_length'])
                previous=None
                unit=next((u for u in case['reassignable_temporary_units'] if u['original_person']==person and u['start']<=a and b<=u['end']),None)
                for index in range(count):
                    bslo=max(0,a+cfg['min_work_before_break']);bshi=min(H-cfg['break_length'],b-cfg['min_work_after_break']-cfg['break_length'])
                    assert bslo<=bshi,('fixed break has no location',person,a,b)
                    bs=model.NewIntVar((bslo+step-1)//step,bshi//step,'fixed_break')
                    if previous is None:model.Add(bs*step-a<=cfg['max_continuous_active'])
                    else:
                        model.Add(bs*step>=previous*step+cfg['break_length'])
                        model.Add(bs*step-(previous*step+cfg['break_length'])<=cfg['max_continuous_active'])
                    if index==count-1:model.Add(b-(bs*step+cfg['break_length'])<=cfg['max_continuous_active'])
                    previous=bs
                    absence.append(model.NewFixedSizeIntervalVar(bs*step,cfg['break_length'],''));absence_d.append(1)
                    breakvars.append(dict(person=person,start=bs,chain_start=a,chain_end=b,frozen_chain=True,unit_id=None if unit is None else unit['id'],ordinal=index))
                    fixed_net[person]-=cfg['break_length']
    variables=[];possible=[0]*H
    for c in case['candidates']:
        lo,hi=c['lo']//step,c['hi']//step
        pr=model.NewBoolVar('shift_'+c['id']);s=model.NewIntVar(lo,hi,'start');e=model.NewIntVar(lo,hi,'end')
        length=model.NewIntVar(0,c['max_length']//step,'length');br=model.NewBoolVar('break');bs=model.NewIntVar(lo,hi,'break_start')
        model.Add(e-s==length);model.Add(length>=c['min_length']//step).OnlyEnforceIf(pr)
        model.Add(length==0).OnlyEnforceIf(pr.Not());model.Add(s==lo).OnlyEnforceIf(pr.Not())
        model.Add(length*step>cfg['break_threshold']).OnlyEnforceIf(br);model.Add(length*step<=cfg['break_threshold']).OnlyEnforceIf(br.Not())
        model.Add(bs*step>=s*step+cfg['min_work_before_break']).OnlyEnforceIf(br)
        model.Add(bs*step<=s*step+cfg['max_continuous_active']).OnlyEnforceIf(br)
        model.Add(bs*step+cfg['break_length']<=e*step-cfg['min_work_after_break']).OnlyEnforceIf(br)
        model.Add(e*step-(bs*step+cfg['break_length'])<=cfg['max_continuous_active']).OnlyEnforceIf(br)
        model.Add(bs==lo).OnlyEnforceIf(br.Not())
        net=length*step-cfg['break_length']*br
        variables.append(dict(c=c,pr=pr,s=s,e=e,br=br,bs=bs,net=net))
        gross_intervals.append(model.NewOptionalIntervalVar(s*step,length*step,e*step,pr,''))
        daylo=c['day']*1440;dayhi=daylo+1440
        absence.append(model.NewIntervalVar(daylo,s*step-daylo,s*step,''));absence_d.append(1)
        absence.append(model.NewIntervalVar(e*step,dayhi-e*step,dayhi,''));absence_d.append(1)
        absence.append(model.NewOptionalFixedSizeIntervalVar(bs*step,cfg['break_length'],br,''));absence_d.append(1)
        for t in range(daylo,dayhi):possible[t]+=1
    model.AddCumulative(gross_intervals,[1]*len(gross_intervals),cfg['max_staff_on_duty'])
    model._fixed_breaks=breakvars
    add_person_constraints(case,model,variables)
    from ..planning_activities import add_to_model
    activity_intervals = add_to_model(case, model, breakvars)
    absence.extend(activity_intervals); absence_d.extend([1]*len(activity_intervals))
    background=[K-fixed_supply[t]-possible[t] for t in range(H)]
    assert min(background)>=0
    for a,b,value in runs(background):
        if value:absence.append(model.NewFixedSizeIntervalVar(a,b-a,''));absence_d.append(value)
    # Shared tasks consume the same employee pool concurrently, but a shopping
    # trip removes its executors from that pool. Use one absence profile per day.
    def expr_bounds(expr):
        lo=hi=expr.offset
        for var,coeff in zip(expr.vars,expr.coeffs):
            dom=list(model.Proto().variables[var].domain)
            x,y=dom[0],dom[-1]
            lo+=coeff*(x if coeff>=0 else y);hi+=coeff*(y if coeff>=0 else x)
        return lo,hi
    absence_by_day=[[] for _ in range(H//1440)]
    for interval,demand in zip(absence,absence_d):
        proto=model.Proto().constraints[interval.Index()].interval
        lo=expr_bounds(proto.start)[0];hi=expr_bounds(proto.end)[1]
        for day in range(max(0,lo//1440),min(H//1440,(hi-1)//1440+1)):
            absence_by_day[day].append((interval,demand))
    tasks=[];shopping_by_day=[[] for _ in range(H//1440)]
    for n in case['needs']:
        st=model.NewIntVarFromDomain(cp_model.Domain.FromIntervals(n['domains']),'task_'+n['id'])
        pr=model.NewBoolVar('placed_'+n['id'])
        interval=model.NewOptionalFixedSizeIntervalVar(st,n['duration'],pr,'task_occupancy')
        record=dict(n=n,st=st,pr=pr,parts=[],hosts=[],interval=interval)
        if case.get('lock_covered_ids') is not None:model.Add(pr==int(n['id'] in set(case['lock_covered_ids'])))
        tasks.append(record)
        if n['exclusive']:shopping_by_day[n['original']//1440].append((interval,n['count']))
    for day,profile in enumerate(absence_by_day):
        common=profile+shopping_by_day[day]
        intervals=[x[0] for x in common];demands=[x[1] for x in common]
        model.AddCumulative(intervals,demands,K)
        for t in tasks:
            if t['n']['exclusive'] or t['n']['original']//1440!=day:continue
            model.AddCumulative(intervals+[t['interval']],demands+[t['n']['count']],K)
    # Hints from previous independent proposal, accepted only within this case's domains.
    prior=case.get('search_hint') or case.get('references',{}).get('astra_previous') or {'segments':[],'breaks':[],'placements':[]};prior_rows={r['id']:r for r in prior['segments']};prior_recipients={r['unit_id']:r['new_person'] for r in prior.get('temporary_unit_reassignments',[])}
    for v in variables:
        r=prior_rows.get(v['c']['id'])
        if r is None:model.AddHint(v['pr'],0);continue
        model.AddHint(v['pr'],1);model.AddHint(v['s'],r['start']//step);model.AddHint(v['e'],r['end']//step)
        br=next((b for b in prior['breaks'] if b['person']==r['person'] and r['start']<=b['start']<r['end']),None)
        model.AddHint(v['br'],int(br is not None));model.AddHint(v['bs'],br['start']//step if br else v['c']['lo']//step)
    pt={t['id']:t['start'] for t in prior['placements']}
    records={p['id']:p for p in prior['placements']}
    for b in breakvars:
        person=prior_recipients.get(b['unit_id'],b['person'])
        previous=sorted((r for r in prior['breaks'] if r['person']==person and r.get('chain_start')==b['chain_start'] and r.get('chain_end')==b['chain_end']),key=lambda r:r['start'])
        if b['ordinal']<len(previous):model.AddHint(b['start'],previous[b['ordinal']]['start']//step)
    for t in tasks:
        value=pt.get(t['n']['id']);valid=value is not None and any(a<=value<=b for a,b in t['n']['domains'])
        model.AddHint(t['pr'],int(valid))
        if valid:model.AddHint(t['st'],value)
        previous=records.get(t['n']['id'],{})
        if valid:
            oldparts=previous.get('fragments',[])
            for (var,dur),part in zip(t['parts'],oldparts):
                if dur==part['duration']:model.AddHint(var,part['start'])
            if 'normal' in t:
                model.AddHint(t['normal'],int(not previous.get('shared_host')))
                for h,host in t['hosts']:model.AddHint(h,int(previous.get('shared_host')==host))
    count=sum(t['pr']*t['n'].get('weight',1) for t in tasks)
    minutes=sum(t['pr']*t['n']['duration']*t['n']['count'] for t in tasks)
    temp=model._fixed_temporary_objective+sum(v['net'] for v in variables if not staff[v['c']['person']]['ordinary'])
    total=sum(v['net'] for v in variables)
    assert not cfg.get('capacity_without_ssg'), 'This workload experiment preserves the existing ordinary per-person targets.'
    peak=add_weekly_peak(case,model,variables,breakvars)
    objectives=[(count,'max','covered_source_rows'),(minutes,'max','covered_workflow_minutes')]
    if objective_mode=='coverage_then_workload_then_temporary':objectives.append((peak,'min','highest_active_net_week_all_staff'))
    objectives.append((temp,'min','temporary_minutes'))
    return model,variables,tasks,breakvars,objectives

def solve(case, output=None, seconds=60, workers=1, seed=41, det=30, objective_mode="coverage_then_temporary", progress=None):
    started=time.monotonic();model,vv,tasks,fb,objectives=build(case, objective_mode);built=time.monotonic()-started
    assert not model.Validate(),model.Validate()
    allvars=[model.GetIntVarFromProtoIndex(i) for i in range(len(model.Proto().variables))]
    logs=[];last=None
    for expr,direction,name in objectives:
        if direction=='max':model.Maximize(expr)
        else:model.Minimize(expr)
        solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.max_deterministic_time=det
        solver.parameters.num_search_workers=workers;solver.parameters.random_seed=seed
        s=time.monotonic();status=solver.Solve(model)
        entry=dict(stage=name,status=solver.StatusName(status),seconds=time.monotonic()-s,deterministic_time=solver.ResponseProto().deterministic_time,
                   bound=solver.BestObjectiveBound(),objective=solver.ObjectiveValue() if status in (cp_model.FEASIBLE,cp_model.OPTIMAL) else None)
        logs.append(entry)
        if progress is not None:progress(dict(entry))
        if status not in (cp_model.FEASIBLE,cp_model.OPTIMAL):break
        last=solver;value=solver.Value(expr)
        # Freeze every achieved higher-priority level, including improvements found
        # while working on a later objective. Never trade those away for temp time.
        for previous,previous_direction,previous_name in objectives:
            attained=solver.Value(previous)
            model.Add(previous>=attained if previous_direction=='max' else previous<=attained)
            if previous_name==name:break
        model.ClearHints()
        for var in allvars:model.AddHint(var,solver.Value(var))
    result=dict(status='NO_CANDIDATE' if last is None else 'CONDITIONAL_PROPOSAL_NOT_FULLY_VERIFIED',stages=logs,
                build_seconds=built,total_seconds=time.monotonic()-started,peak_rss_kib=None if resource is None else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                parameters=dict(ortools=ortools.__version__,seed=seed,workers=workers,seconds_per_stage=seconds,deterministic_per_stage=det),
                model=dict(variables=len(model.Proto().variables),constraints=len(model.Proto().constraints),candidate_person_days=len(vv),needs=len(tasks)))
    if last is not None:
        result['workload_objectives']=export_weekly_workload(model,last)
        segments,reassignments=export_reassignments(case,model,last)
        result['temporary_unit_reassignments']=reassignments
        step=case['config']['shift_step'];breaks=[]
        for v in vv:
            if last.Value(v['pr']):
                segments.append(dict(id=v['c']['id'],person=v['c']['person'],start=last.Value(v['s'])*step,end=last.Value(v['e'])*step,type='AKTIVT_ARBETE',code='Ar',locked_reason=None))
                if last.Value(v['br']):breaks.append(dict(person=v['c']['person'],start=last.Value(v['bs'])*step,end=last.Value(v['bs'])*step+case['config']['break_length'],frozen_chain=False))
        recipients={r['unit_id']:r['new_person'] for r in reassignments}
        for b in fb:
            breaks.append(dict(person=recipients.get(b['unit_id'],b['person']),start=last.Value(b['start'])*step,end=last.Value(b['start'])*step+case['config']['break_length'],frozen_chain=True,chain_start=b['chain_start'],chain_end=b['chain_end']))
        placements=[]
        for t in tasks:
            if not last.Value(t['pr']):continue
            placements.append(dict(id=t['n']['id'],start=last.Value(t['st']),
                fragments=[dict(start=last.Value(st),duration=dur) for st,dur in t['parts']],
                shared_host=next((host for h,host in t['hosts'] if last.Value(h)),None)))
        result.update(segments=segments,breaks=breaks,placements=placements)
        if case.get("planning_activities"):
            from ..planning_activities import model_result
            result["planning_activities"] = model_result(model, last)
        signature_rows = [segments, breaks, result['placements']]
        if case.get("planning_activities"):
            signature_rows.append(result["planning_activities"])
        sig=json.dumps(signature_rows,sort_keys=True).encode();result['signature']=hashlib.sha256(sig).hexdigest()
    if output is not None:Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result

