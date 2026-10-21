"""Experimental whole-occasion reassignment. No source files edited.
Preserves slots; adds explicit identity, SSG, calendar and rest constraints.
"""
from collections import defaultdict
from ortools.sat.python import cp_model
from .daily_rest import constrain as constrain_daily_rest

def add_person_constraints(case,model,variables):
 H=case['horizon'];cfg=case['config'];profile=cfg['duty_profile'];staff={p['id']:p for p in case['staff']};units=case['reassignable_temporary_units'];movable={id for u in units for id in u['segment_ids']}
 fixed=[r for r in case['fixed_segments'] if r['id'] not in movable];choices=[];ordinary=[p for p in staff if staff[p]['ordinary']]
 for u in units:
  options=[]
  hinted={a['unit_id']:a['new_person'] for a in (case.get('search_hint') or {}).get('temporary_unit_reassignments',[])}.get(u['id'],u['original_person'])
  for person in [u['original_person']]+ordinary:
   allowed=staff[person]['all_task_skills'] and staff[person]['day']=='JA' and staff[person]['evening']=='JA' and (not any(r['code']=='Jo' for r in u['rows']) or staff[person]['sleeping_oncall']=='JA')
   if person != u['original_person']:
    # Do not create a newly reassigned >24h duty occasion. Preserve the
    # inherited one separately; no exemption is invented for a recipient.
    if u['end']-u['start'] > profile['max_reassigned_minutes']: allowed=False
    if profile['long_jour_min_minutes'] <= u['end']-u['start'] <= profile['max_reassigned_minutes']:
     night=[]
     for row in u['rows']:
      if row['code']!='Jo': continue
      for day in range(u['start']//1440-1,u['end']//1440+1):
       a=max(row['start'],day*1440+profile['night_start_minute']);b=min(row['end'],(day+1)*1440+profile['night_end_minute'])
       if b>a:night.append((a,b))
     merged=[]
     for a,b in sorted(night):
      if merged and a<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],b)
      else:merged.append([a,b])
     if max((b-a for a,b in merged),default=0)<profile['night_jour_min_minutes']:allowed=False
   if not allowed:continue
   pr=model.NewBoolVar('recipient_'+u['id']+'_'+person);options.append((person,pr));model.AddHint(pr,int(person==hinted))
  model.AddExactlyOne([pr for _,pr in options]);choices.append(dict(unit=u,options=options))
 breaks=model._fixed_breaks
 whole=model._whole_duty_choices
 unit_breaks={u['id']:sum(cfg['break_length'] for b in breaks if b['unit_id']==u['id']) for u in units}
 immutable_breaks={p:sum(cfg['break_length'] for b in breaks if b['person']==p and b['unit_id'] is None) for p in staff}
 for person,p in staff.items():
  rows=[r for r in fixed if r['person']==person];vv=[v for v in variables if v['c']['person']==person]
  optional=[(ch['unit'],pr) for ch in choices for pp,pr in ch['options'] if pp==person]
  # Net ordinary time excludes Jo, outcomes and P1. Break deductions follow
  # assigned unit recipients; fixed/nonmovable deductions are person-specific.
  fixed_ar=sum(max(0,min(H,r['end'])-max(0,r['start'])) for r in rows if r['code']=='Ar')
  net=fixed_ar-immutable_breaks[person]+sum((u['ar_p2_minutes']-unit_breaks[u['id']])*pr for u,pr in optional)+sum(v['net'] for v in vv)+sum(
   sum(r['end']-r['start'] for r in ch['c']['parts'] if r['code']=='Ar')*ch['pr']
   for ch in whole if ch['c']['person']==person)
  if p['ordinary']:model.Add(net==p['target_net'])
  fixed_days={d for d in range(-H//1440,H//1440) if any(r['start']<(d+1)*1440 and r['end']>d*1440 for r in rows)}
  occupied={}
  for day in range(-H//1440,H//1440):
   if day in fixed_days:occupied[day]=1;continue
   active=[pr for u,pr in optional if u['start']<(day+1)*1440 and u['end']>day*1440]
   active += [v['pr'] for v in vv if v['c']['day']==day]
   active += [ch['pr'] for ch in whole if ch['c']['person']==person and ch['c']['start']<(day+1)*1440 and ch['c']['end']>day*1440]
   if not active:occupied[day]=0
   else:
    b=model.NewBoolVar('occupied_'+person+'_'+str(day));model.AddMaxEquality(b,active);occupied[day]=b
  mode=cfg['calendar_mode']
  assert mode in ['rolling','fixed']
  if mode=='rolling':
   for end in range(1,H//1440+1):model.Add(sum(occupied[d] for d in range(end-H//1440,end))<=H//1440-cfg['min_free_days'])
  else:model.Add(sum(occupied[d] for d in range(H//1440))<=H//1440-cfg['min_free_days'])
  # Source-cell hulls are explicit model assumptions, not verified whole-pass IDs.
  # Actual known historical Kl/Öv participates in calendar and rest grouping.
  # St is excluded from capacity; no active Ar or Jo is invented in its gap.
  groups=defaultdict(list)
  for r in rows:
   if r['code'] in ['Ar','Jo','Kl','Öv']:groups[r.get('whole_duty_id') or r['id'].rsplit('-',1)[0]].append(r)
  events=[]
  for id,rr in groups.items():events.append(dict(start=min(r['start'] for r in rr),end=max(r['end'] for r in rr),present=1,label=id,rest_after=max(cfg['min_daily_rest'],max(r['end'] for r in rr)-min(r['start'] for r in rr)) if any(r['code']=='Jo' for r in rr) and max(r['end'] for r in rr)-min(r['start'] for r in rr)>profile['compensation_trigger_minutes'] else cfg['min_daily_rest']))
  events += [dict(start=u['start'],end=u['end'],present=pr,label=u['id'],rest_after=max(cfg['min_daily_rest'],u['end']-u['start']) if any(r['code']=='Jo' for r in u['rows']) and u['end']-u['start']>profile['compensation_trigger_minutes'] else cfg['min_daily_rest']) for u,pr in optional]
  events += [dict(start=ch['c']['start'],end=ch['c']['end'],present=ch['pr'],label=ch['c']['id'],
                  rest_after=max(cfg['min_daily_rest'],ch['c']['end']-ch['c']['start']),combined_jour=True)
             for ch in whole if ch['c']['person']==person]
  combined={key for key,rr in groups.items() if {'Ar','Jo'}<={r['code'] for r in rr}}
  combined.update(u['id'] for u,pr in optional if {'Ar','Jo'}<={r['code'] for r in u['rows']})
  for event in events:event['combined_jour']=event.get('combined_jour',event['label'] in combined)
  # Original P2 duties have no minimum-length exemption. Frozen history and
  # incoming duties retain their known times, matching the independent check.
  for event in events:
   if 0<=event['start']<H:
    minimum=model.Add(event['end']-event['start']>=cfg['min_shift'])
    if not isinstance(event['present'],int):minimum.OnlyEnforceIf(event['present'])
  events += [dict(start=v['s']*cfg['shift_step'],end=v['e']*cfg['shift_step'],present=v['pr'],label=v['c']['id']) for v in vv]
  constrain_daily_rest(case,model,person,events)
  # A selected 20/24h plan constrains complete duties, including retained units.
  # Historical incoming duties are preserved. No automatic trimming or splitting.
  limit=cfg.get('max_whole_duty_minutes')
  if limit is not None:
   for event in events:
    if isinstance(event['start'],int) and not 0<=event['start']<H:continue
    maximum=model.Add(event['end']-event['start']<=limit)
    if not isinstance(event['present'],int):maximum.OnlyEnforceIf(event['present'])
  for i,left in enumerate(events):
   for right in events[i+1:]:
    # P1 itself is historical. New P2 work obeys rest against its known edges.
    if isinstance(left['end'],int) and isinstance(right['end'],int) and left['end']<=0 and right['end']<=0:continue
    literals=[e['present'] for e in [left,right] if not isinstance(e['present'],int)]
    before=model.NewBoolVar('occasion_order')
    model.Add(left['end']+left.get('rest_after',cfg['min_daily_rest'])<=right['start']).OnlyEnforceIf(literals+[before])
    model.Add(right['end']+right.get('rest_after',cfg['min_daily_rest'])<=left['start']).OnlyEnforceIf(literals+[before.Not()])
  # Confirmed absence is an explicit source lock, not inferred availability.
  for lock in case.get('confirmed_absence_locks',[]):
   if lock['person']!=person:continue
   for event in events:
    if isinstance(event['start'],int) and isinstance(event['end'],int):
     if max(event['start'],lock['start'])>=min(event['end'],lock['end']):continue
     if isinstance(event['present'],int):model.Add(0==1)
     else:model.Add(event['present']==0)
    else:
     before_absence=model.NewBoolVar('before_confirmed_absence')
     lit=[] if isinstance(event['present'],int) else [event['present']]
     model.Add(event['end']<=lock['start']).OnlyEnforceIf(lit+[before_absence])
     model.Add(event['start']>=lock['end']).OnlyEnforceIf(lit+[before_absence.Not()])
  # No new split tours through an assigned source occasion on the same date.
  for v in vv:
   for u,pr in optional:
    if u['start']<(v['c']['day']+1)*1440 and u['end']>v['c']['day']*1440:model.Add(v['pr']+pr<=1)
  for week in range(H//10080):
   lo=week*10080;hi=lo+10080;rest=model.NewIntVar(lo,hi-cfg['min_weekly_rest'],'weekly_rest_'+person)
   for event in events:
    if isinstance(event['start'],int) and isinstance(event['end'],int) and (event['end']<=lo or event['start']>=hi):continue
    before=model.NewBoolVar('rest_order');lit=[] if isinstance(event['present'],int) else [event['present']]
    model.Add(rest+cfg['min_weekly_rest']<=event['start']).OnlyEnforceIf(lit+[before])
    model.Add(rest>=event['end']).OnlyEnforceIf(lit+[before.Not()])
  # Exact rolling 28-day Jo cap; extrema occur at endpoint changes in the
  # piecewise-linear clipped duration, including starts/end shifted by H.
  fixed_jo=[(r['start'],r['end']) for r in rows if r['code']=='Jo']
  optional_jo=[(r['start'],r['end'],pr) for u,pr in optional for r in u['rows'] if r['code']=='Jo']
  optional_jo += [(r['start'],r['end'],ch['pr']) for ch in whole if ch['c']['person']==person for r in ch['c']['parts'] if r['code']=='Jo']
  cap_end=max([H]+[b for a,b in fixed_jo]+[b for a,b,pr in optional_jo])
  endpoints={0,H,cap_end}
  for a,b in fixed_jo+[(a,b) for a,b,_ in optional_jo]:
   endpoints.update(t for t in [a,b,a+H,b+H] if 0<=t<=cap_end)
  overlap=lambda a,b,t:max(0,min(b,t)-max(a,t-H))
  for t in endpoints:model.Add(sum(overlap(a,b,t) for a,b in fixed_jo)+sum(overlap(a,b,t)*pr for a,b,pr in optional_jo)<=cfg['oncall_cap_28d'])
 model._reassignment_choices=choices
 locked_temp=sum(max(0,min(H,r['end'])-max(0,r['start'])) for r in fixed if r['code']=='Ar' and not staff[r['person']]['ordinary'])
 model._fixed_temporary_objective=locked_temp-sum(immutable_breaks[p] for p in staff if not staff[p]['ordinary'])+sum((ch['unit']['ar_p2_minutes']-unit_breaks[ch['unit']['id']])*pr for ch in choices for person,pr in ch['options'] if not staff[person]['ordinary'])

def export_reassignments(case,model,solver):
 mapping={};records=[]
 for ch in model._reassignment_choices:
  person=next(person for person,pr in ch['options'] if solver.Value(pr))
  u=ch['unit'];records.append(dict(unit_id=u['id'],original_person=u['original_person'],new_person=person,ar_p2_minutes=u['ar_p2_minutes'],segment_ids=u['segment_ids']))
  mapping.update({id:person for id in u['segment_ids']})
 rows=[dict(r,person=mapping.get(r['id'],r['person']),original_person=r['person']) for r in case['fixed_segments']]
 return rows,records
