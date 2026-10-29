"""Source-bound planning reservations, separate from customer needs and coverage.

v1 supports fixed, explicitly verified duties and explicit slots on fixed Ar.
No name-based meaning, implicit staff allocation, free-text competence grants,
source-cell duty inference, extra shifts, or silent partial model support.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
import re

from .flora_import import FloraImportError

VERSION = 'bb-planning-activities/1.0'
FRONTEND = 'c815a7fdd11b1b7c22326bbd5cde008284e59a72'
FIELDS = {'id','name','category','on','minutes','freq','occurrences','shift_override',
          'anchor','person_id','customer_id','slots','strength','competence','window_from','window_to'}
SLOT_FIELDS = {'id','date','start','window_from','window_to','minutes','person_id','customer_id'}
FREQUENCIES = {'per_shift','per_customer_week','per_customer_month','per_week','per_month'}
CLOCK = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def digest(value):
    return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


class ActivityReviewRequired(FloraImportError):
    code = 'ACTIVITY_REVIEW_REQUIRED'

    def __init__(self, issues):
        super().__init__('Aktiviteterna behöver kompletteras före körning; inga aktiverade aktiviteter har ignorerats.', issues)

    def detail(self):
        return dict(code=self.code, message=str(self), contract_version=VERSION, activities=self.issues)


def issue(activity, missing, reason):
    received = {k:deepcopy(v) for k,v in activity.items() if k in FIELDS} if isinstance(activity,dict) else {'value_type':type(activity).__name__}
    return dict(activity_id=received.get('id') if text(received.get('id')) else None,
                name=received.get('name') if text(received.get('name')) else None,
                missing_fields=list(dict.fromkeys(missing)), unsupported_reason=reason, received=received)


def activities(scenario):
    value = (scenario.get('workspace') or {}).get('activities', [])
    if not isinstance(value,list):
        raise ActivityReviewRequired([issue({},['activities'],'ACTIVITIES_MUST_BE_LIST')])
    return value


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def text(value):
    return isinstance(value,str) and bool(value.strip())


def validate_row(a, people, customers):
    missing=[]; reasons=[]
    if not isinstance(a,dict):return ['activity'],['ACTIVITY_MUST_BE_OBJECT']
    for k in ('id','name'):
        if not text(a.get(k)):missing.append(k)
    if a.get('category') not in ('kundnara','verksamhet'):missing.append('category')
    if a.get('on') is not True:missing.append('on')
    if not integer(a.get('minutes'),1):missing.append('minutes')
    if not isinstance(a.get('freq'),str) or a['freq'] not in FREQUENCIES:missing.append('freq')
    for k in ('occurrences','shift_override'):
        if a.get(k) is not None and not integer(a[k]):missing.append(k)
    for k,ids in [('person_id',people),('customer_id',customers)]:
        if a.get(k) is not None and (not isinstance(a[k],str) or a[k] not in ids):missing.append(k)
    if set(a)-FIELDS:reasons.append('UNKNOWN_ACTIVITY_FIELDS')
    if a.get('competence') is not None:reasons.append('COMPETENCE_MAPPING_REQUIRED')
    if a.get('strength') not in (None,'hard'):reasons.append('SOFT_OR_UNKNOWN_STRENGTH_NOT_IMPLEMENTED')
    if a.get('shift_override') is not None:reasons.append('SHIFT_COUNT_IS_NOT_DUTY_EVIDENCE')
    if a.get('freq') in ('per_month','per_customer_month'):
        if a.get('occurrences') is None:missing.append('occurrences')
        elif a.get('occurrences')==0:reasons.append('ACTIVE_MONTHLY_ZERO_EXTENT_REQUIRES_REVIEW')
    if a.get('anchor') not in (None,'shift_start','shift_end'):missing.append('anchor')
    if a.get('anchor') and a.get('freq')!='per_shift':reasons.append('ANCHOR_REQUIRES_PER_SHIFT')
    if not isinstance(a.get('slots',[]),list):missing.append('slots')
    slots=a.get('slots') if isinstance(a.get('slots'),list) else []
    if a.get('anchor') and slots:reasons.append('ANCHOR_AND_SLOTS_SCOPE_AMBIGUOUS')
    if a.get('window_from') is not None or a.get('window_to') is not None:
        reasons.append('TASK_WINDOW_REQUIRES_DATED_SLOT_NO_IMPLICIT_RECURRENCE')
    if not slots and not a.get('anchor'):
        missing.append('anchor_or_dated_slots' if a.get('freq')=='per_shift' else 'dated_slots_or_placement_domain')
    if not slots and a.get('freq') in ('per_customer_week','per_customer_month'):
        if not a.get('customer_id'):missing.append('customer_id_or_explicit_slot_customers')
        if not a.get('person_id'):missing.append('person_id_or_explicit_slot_persons')
    return missing,reasons


def prepare(raw, profile, scenario, case, strategy='flora'):
    rows=activities(scenario)
    if not rows:return
    people={p['person_id'] for p in raw['staff']}
    customers={c['customer_id'] for c in raw['customers']}
    errors=[]; seen=set(); active=[]; occurrences=[]; disabled=[]
    for a in rows:
        if isinstance(a,dict) and text(a.get('id')):
            if a['id'] in seen:
                errors.append(issue(a,[],'DUPLICATE_ACTIVITY_ID'));continue
            seen.add(a['id'])
        # Retain historical empty/default OFF rows. They never become reservations.
        if isinstance(a,dict) and a.get('on') is False:
            disabled.append(a.get('id'));continue
        missing,reasons=validate_row(a,people,customers)
        if strategy!='flora':reasons.append('ACTIVITY_STRATEGY_NOT_IMPLEMENTED')
        if missing or reasons:
            errors.append(issue(a,missing,';'.join(reasons) or 'INCOMPLETE_ACTIVITY'));continue
        try:
            compiled = compile_row(a,raw,case)
        except ActivityReviewRequired as exc:
            errors.extend(exc.issues);continue
        active.append(dict(activity_id=a['id'], name=a['name'], category=a['category'],
            minutes=a['minutes'], frequency=a['freq'], occurrences=a.get('occurrences'),
            shift_override=a.get('shift_override'), anchor=a.get('anchor'), person_id=a.get('person_id'),
            customer_id=a.get('customer_id'), slots=deepcopy(a.get('slots',[])), strength=a.get('strength'),
            competence=a.get('competence'), basis=dict(kind='EXPLICIT_SETTINGS_ACTIVITY',
            path='settings.activities', activity_sha256=digest(a)),
            occurrence_ids=[x['id'] for x in compiled], modeled_occurrences=len(compiled),
            total_minutes=sum(x['minutes'] for x in compiled),
            scope='VERIFIED_FIXED_DUTIES' if a.get('anchor') else 'EXPLICIT_SLOTS_ONLY',
            frequency_extent_status='ENUMERATED_VERIFIED_DUTIES' if a.get('anchor') else 'NOT_FULLY_PLACED_OR_VERIFIED',
            outside_claims=[] if a.get('anchor') else ['Unplaced frequency extent; slots do not replace or verify the frequency total.']))
        occurrences.extend(compiled)
    by_person=defaultdict(list)
    for x in occurrences:
        if len(x['domains'])==1 and x['domains'][0][0]==x['domains'][0][1]:
            a=x['domains'][0][0];b=a+x['minutes']
            for y,c,d in by_person[x['person_id']]:
                if max(a,c)<min(b,d):
                    for z in (x,y):
                        row=next(t for t in rows if isinstance(t,dict) and t.get('id')==z['activity_id'])
                        errors.append(issue(row,[],'EXACT_ACTIVITY_OVERLAP'))
            by_person[x['person_id']].append((x,a,b))
    if errors:
        # One response, one row per affected activity; all reasons retained.
        merged={}
        for i,e in enumerate(errors):
            key=e['activity_id'] or ('invalid',i)
            if key not in merged:merged[key]=e
            else:
                merged[key]['missing_fields']=list(dict.fromkeys(merged[key]['missing_fields']+e['missing_fields']))
                merged[key]['unsupported_reason']+=';'+e['unsupported_reason']
        raise ActivityReviewRequired(list(merged.values()))
    if not active:return  # OFF rows create no case/model/result activity records.
    case['planning_activities']=dict(version=VERSION, frontend_commit=FRONTEND,
        binding=dict(profile_id=profile['profile_id'],profile_hash=digest(profile),
            business_id=raw['metadata'].get('business_id'),data_use=raw['metadata'].get('data_use'),
            dataset_id=raw['metadata'].get('dataset_id'),source_file_sha256=raw['metadata'].get('source_file_sha256'),
            input_hash=digest(raw),settings_sha256=digest(rows),period=deepcopy(case['integration']['period'])),
        activities=active,occurrences=occurrences,disabled_activity_ids=disabled,
        outside_claims=['Customer-need coverage, direct customer-contact time and business approval are not established by planning activities.',
            'Untimed support and any unplaced frequency extent remain UNKNOWN.'])


def compile_row(a, raw, case):
    def fail(fields,reason):raise ActivityReviewRequired([issue(a,fields,reason)])
    H=case['horizon'];origin=datetime.fromisoformat(case['origin'])
    reassigned={sid for u in case['reassignable_temporary_units'] for sid in u['segment_ids']}
    fixed=[r for r in case['fixed_segments'] if r['id'] not in reassigned]
    fixed_ids={r['id'] for r in fixed}
    recorded_breaks=case['references']['import'].get('breaks',[])
    def supports(pid,left,right,duration):
        found=[]
        for r in fixed:
            if r['person']!=pid or r['code']!='Ar' or r['type']!='AKTIVT_ARBETE':continue
            lo=max(left,0,r['start']);hi=min(right,H-duration,r['end']-duration)
            domains=[[lo,hi]] if lo<=hi else []
            for br in recorded_breaks:
                if br['person']!=pid:continue
                pieces=[]
                for x,y in domains:
                    if x<=min(y,br['start']-duration):pieces.append([x,min(y,br['start']-duration)])
                    if max(x,br['end'])<=y:pieces.append([max(x,br['end']),y])
                domains=pieces
            for x,y in domains:
                found.append(dict(segment_id=r['id'],pass_id='reviewed:'+r['whole_duty_id'] if r.get('whole_duty_id') else 'segment:'+r['id'],
                    pass_id_basis='PROFILE_WHOLE_DUTY_ID' if r.get('whole_duty_id') else 'VERIFIED_FIXED_AR_SEGMENT_NOT_WHOLE_DUTY',
                    earliest=x,latest=y))
        return found
    def occurrence(key,pid,cid,minutes,domains,evidence,slot_id=None,pass_id=None):
        return dict(id='activity:'+digest([a['id'],key])[:24],activity_id=a['id'],slot_id=slot_id,
            person_id=pid,customer_id=cid,minutes=minutes,domains=domains,supports=evidence,
            pass_id=pass_id,basis=dict(kind='EXPLICIT_PASS_ANCHOR' if slot_id is None else 'EXPLICIT_DATED_SLOT',
                activity_sha256=digest(a),source_path='settings.activities'),
            customer_link_status='EXPLICIT_CUSTOMER_LINK' if cid else 'NO_CUSTOMER_LINK',
            direct_customer_minutes=None)
    result=[]
    if a.get('anchor'):
        pid=a.get('person_id')
        if any(pid is None or c['person']==pid for c in case['candidates']):
            fail(['verified_fixed_duties'],'VARIABLE_OR_NEW_DUTIES_NOT_SUPPORTED')
        # A missing candidate is not proof that a source duty may be omitted.
        from .flora_import import _time
        zone=case['integration']['period']['timezone']
        for row in raw['schedule_segments']:
            if row['source_code'] not in ('Ar','Jo') or (pid is not None and row['person_id']!=pid):continue
            left=int((_time(row['start'],zone)-origin).total_seconds()//60)
            right=int((_time(row['end'],zone)-origin).total_seconds()//60)
            if left<H and right>0 and row['segment_id'] not in fixed_ids:
                fail(['verified_fixed_duties'],'SOURCE_DUTY_NOT_FIXED_NO_SILENT_OMISSION')
        source=[r for r in case['fixed_segments'] if r['code'] in ('Ar','Jo') and r['start']<H and r['end']>0 and (pid is None or r['person']==pid)]
        if not source:fail(['verified_whole_duty_groups'],'NO_VERIFIED_DUTIES')
        if any(not r.get('whole_duty_id') or r['id'] not in fixed_ids for r in source):
            fail(['verified_whole_duty_groups'],'UNVERIFIED_OR_REASSIGNABLE_DUTY')
        groups=defaultdict(list)
        # Include complete reviewed groups, including their period edges.
        duty_ids={r['whole_duty_id'] for r in source}
        for r in fixed:
            if r.get('whole_duty_id') in duty_ids:groups[r['whole_duty_id']].append(r)
        for duty,rr in groups.items():
            left=min(r['start'] for r in rr);right=max(r['end'] for r in rr)
            if left<0 or right>H:fail(['complete_in_period_duty'],'DUTY_CROSSES_PERIOD')
            owner={r['person'] for r in rr}
            if len(owner)!=1:fail(['person_id'],'DUTY_PERSON_NOT_UNIQUE')
            person=next(iter(owner));start=left if a['anchor']=='shift_start' else right-a['minutes']
            ev=supports(person,start,start,a['minutes'])
            ev=[x for x in ev if x['pass_id']=='reviewed:'+duty]
            if not ev:fail(['active_anchor_domain'],'ANCHOR_NOT_COVERED_BY_FIXED_AR_OR_BLOCKED_BY_BREAK')
            result.append(occurrence(duty,person,a.get('customer_id'),a['minutes'],[[start,start]],ev,pass_id='reviewed:'+duty))
    else:
        errors=[];seen=set()
        people={p['person_id'] for p in raw['staff']};customers={c['customer_id'] for c in raw['customers']}
        for s in a['slots']:
            try:
                if not isinstance(s,dict) or not text(s.get('id')) or set(s)-SLOT_FIELDS:fail(['slot_id'],'INVALID_SLOT_FIELDS')
                if s['id'] in seen:fail(['slot_id'],'DUPLICATE_SLOT_ID')
                seen.add(s['id'])
                if not integer(s.get('minutes'),1):fail(['slot.minutes'],'SLOT_DURATION_UNKNOWN')
                if not isinstance(s.get('person_id'),str) or s['person_id'] not in people:fail(['slot.person_id'],'SLOT_PERSON_REQUIRED_NO_GUESS')
                if s.get('customer_id') is not None and (not isinstance(s['customer_id'],str) or s['customer_id'] not in customers):fail(['slot.customer_id'],'SLOT_CUSTOMER_UNKNOWN')
                for key in ('person_id','customer_id'):
                    if a.get(key) is not None and a[key]!=s.get(key):fail(['slot.'+key],'SLOT_TASK_BINDING_CONFLICT')
                day=datetime.strptime(s['date'],'%Y-%m-%d')
                if day.strftime('%Y-%m-%d')!=s['date']:raise ValueError()
                def minute(clock):
                    if not isinstance(clock,str) or not CLOCK.fullmatch(clock):fail(['slot.time'],'INVALID_SLOT_CLOCK')
                    return int((day-origin).total_seconds()//60)+int(clock[:2])*60+int(clock[3:])
                exact=s.get('start') is not None
                if exact and (s.get('window_from') is not None or s.get('window_to') is not None):fail(['slot.time'],'EXACT_AND_WINDOW_AMBIGUOUS')
                left=minute(s['start'] if exact else s.get('window_from'))
                right=left if exact else minute(s.get('window_to'))
                if not exact:
                    if right==left:fail(['slot.window_to'],'ZERO_WIDTH_WINDOW')
                    if right<left:right+=1440
                    right-=s['minutes']
                if left<0 or right+s['minutes']>H or left>right:fail(['slot.time'],'SLOT_OUTSIDE_PERIOD_OR_DURATION')
                ev=supports(s['person_id'],left,right,s['minutes'])
                if not ev:fail(['verified_active_pass'],'SLOT_NOT_COVERED_BY_FIXED_AR_OR_BLOCKED_BY_BREAK')
                domains=sorted({(e['earliest'],e['latest']) for e in ev})
                result.append(occurrence(s['id'],s['person_id'],s.get('customer_id'),s['minutes'],[list(x) for x in domains],ev,slot_id=s['id']))
            except ActivityReviewRequired as exc:errors.extend(exc.issues)
            except (ValueError,KeyError,TypeError):errors.append(issue(a,['slot.date'],'INVALID_SLOT_DATE'))
        if errors:raise ActivityReviewRequired(errors)
    return result


def add_to_model(case, model, breaks):
    """Mandatory reservations consume the existing pool, never add gross supply."""
    from ortools.sat.python import cp_model
    records=[];per_person=defaultdict(list)
    for r in case.get('planning_activities',{}).get('occurrences',[]):
        start=model.NewIntVarFromDomain(cp_model.Domain.FromIntervals(r['domains']),r['id'])
        interval=model.NewFixedSizeIntervalVar(start,r['minutes'],r['id']+':capacity')
        records.append(dict(row=r,start=start,interval=interval));per_person[r['person_id']].append(interval)
    for pid,intervals in per_person.items():
        for b in breaks:
            if b['person']==pid:
                intervals.append(model.NewFixedSizeIntervalVar(b['start']*case['config']['shift_step'],case['config']['break_length'],'activity_break_exclusion'))
        model.AddNoOverlap(intervals)
    model._planning_activities=records
    return [r['interval'] for r in records]


def model_result(model, solver):
    return [dict(id=x['row']['id'],person_id=x['row']['person_id'],start=solver.Value(x['start']),
                 end=solver.Value(x['start'])+x['row']['minutes']) for x in model._planning_activities]


def validate(case, solution, available):
    expected={r['id']:r for r in case.get('planning_activities',{}).get('occurrences',[])}
    rows=solution.get('planning_activities',[])
    errors=[];verified=[];used=defaultdict(list)
    def error(message,identity=None):errors.append(dict(rule='planning_activity',id=identity,message=message))
    if not isinstance(rows,list):error('Activity result must be a list');return errors,verified
    if any(not isinstance(r,dict) for r in rows):error('Invalid activity result');return errors,verified
    ids=[r.get('id') for r in rows]
    if any(not text(x) for x in ids):error('Activity occurrence identity is invalid');return errors,verified
    if len(set(ids))!=len(ids) or set(ids)!=set(expected):error('Activity occurrences missing, duplicated or added')
    for row in rows:
        identity=row.get('id');r=expected.get(identity)
        if r is None:continue
        pid=row.get('person_id');a=row.get('start');b=row.get('end')
        if (pid!=r['person_id'] or not integer(a) or not integer(b) or b-a!=r['minutes'] or b>case['horizon']
                or not any(x<=a<=y for x,y in r['domains'])):
            error('Activity person, duration or domain contradicts source',identity);continue
        if not all(available.get(pid,[])[a:b]) or len(available.get(pid,[])[a:b])!=b-a:
            error('Activity has no full active presence or overlaps a break',identity);continue
        ev=[s for s in r['supports'] if s['earliest']<=a<=s['latest'] and any(
            z['id']==s['segment_id'] and z['person']==pid and z['code']=='Ar' and z['start']<=a<b<=z['end']
            for z in solution.get('segments',[]))]
        if not ev:error('Activity lost its source-bound supporting pass',identity);continue
        if any(max(a,x)<min(b,y) for x,y in used[pid]):error('Planning activities overlap for the same person',identity)
        used[pid].append((a,b))
        verified.append({**deepcopy(r),'start':a,'end':b,'supports':deepcopy(ev)})
    return errors,verified


def export(case, validation, stamp):
    contract=case.get('planning_activities')
    if not contract:return {}
    rows=[]
    for row in validation.get('certificates',{}).get('planning_activities',[]):
        out={k:deepcopy(v) for k,v in row.items() if k not in ('domains','supports','start','end')}
        out.update(start=stamp(row['start']),end=stamp(row['end']),
                   placement_domain=[dict(earliest=stamp(a),latest=stamp(b)) for a,b in row['domains']],
                   pass_evidence=[{**s,'earliest':stamp(s['earliest']),'latest':stamp(s['latest'])} for s in row['supports']])
        rows.append(out)
    result={k:deepcopy(v) for k,v in contract.items() if k!='occurrences'}
    result.update(placements=rows,expected_occurrences=len(contract['occurrences']),placed_occurrences=len(rows),
        total_minutes=sum(x['minutes'] for x in rows),direct_customer_minutes=None,
        included_in_customer_need_coverage=False,review_required=True,business_schedule_approved=False)
    return {'planning_activity_contract':result}
