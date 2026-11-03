"""Bounded within-window placement refinement for one Vintergatan C candidate."""
import argparse,json,collections,re,copy,hashlib
from ortools.sat.python import cp_model
from vg_compute_c import groups_from
from vg_validate_candidate import validate,stable

parser=argparse.ArgumentParser()
parser.add_argument('--warm-start',required=True)
parser.add_argument('--candidate',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--seconds-per-day',type=float,default=8)
args=parser.parse_args()
src=json.load(open(args.warm_start))
x=json.load(open(args.candidate))
needs={n['id']:n for n in x['needs']}
old={(a['need_id'],a['slot']):a for a in src['assignments'] if a['need_id'] in needs}
duties={d['id']:d for d in x['duties']}
groups=groups_from(x)
by_day=collections.defaultdict(list)
for i,g in enumerate(groups):by_day[g['start']//1440].append(i)
new={}
summary=collections.Counter()
for day,idxs in sorted(by_day.items()):
 model=cp_model.CpModel()
 options=collections.defaultdict(list);intervals=collections.defaultdict(list);on_temp=collections.defaultdict(list);by_need_person=collections.defaultdict(list)
 for did,d in duties.items():
  if d['start'] >= (day+1)*1440 or d['end'] <= day*1440:continue
  if d['person_id'].startswith('VIK-'):
   v=model.new_bool_var('use_'+did);on_temp[did].append(v)
  else:v=None
  for a in x['assignments']:
   if a['kind']=='ADMIN' and a['duty_id']==did:intervals[did].append(model.new_fixed_size_interval_var(a['start'],a['end']-a['start'],'admin_'+a['need_id']))
  parts=[];last=d['start']
  for a,b in d['breaks']:
   parts.append((last,a));last=b
  parts.append((last,d['end']))
  for i in idxs:
   g=groups[i];dur=g['end']-g['start'];orig=[old[(r['need_id'],r['slot'])] for r in g['rows']]
   med=any(re.search(r'läk|medic|insulin|deleger|sond',str(needs[r['need_id']]['activity']),re.I) for r in g['rows'])
   original_pid=orig[0]['person_id']
   if med and original_pid and d['person_id']!=original_pid and not d['person_id'].startswith('VIK-'):continue
   low=max((needs[r['need_id']]['earliest']//60-(r['start']-g['start'])) for r in g['rows'])
   high=min((needs[r['need_id']]['latest_end']//60-(r['end']-g['start'])) for r in g['rows'])
   for pa,pb in parts:
    L=max(low,pa);U=min(high,pb-dur)
    if L>U:continue
    b=model.new_bool_var('x_%d_%s_%d'%(i,did,pa))
    st=model.new_int_var(L,U,'start_%d_%s_%d'%(i,did,pa))
    it=model.new_optional_fixed_size_interval_var(st,dur,b,'it_%d_%s_%d'%(i,did,pa))
    intervals[did].append(it);options[i].append((b,st,did))
    if v is not None:model.add(b<=v)
    for r in g['rows']:by_need_person[(r['need_id'],d['person_id'])].append(b)
 for i in idxs:
  if not options[i]:raise RuntimeError('no assignment options day %d group index %d'%(day,i))
  model.add(sum(b for b,_,_ in options[i])==1)
 for did,ints in intervals.items():model.add_no_overlap(ints)
 for bs in by_need_person.values():
  if len(bs)>1:model.add(sum(bs)<=1)
 obj=[]
 for did,vs in on_temp.items():obj.append(vs[0]*duties[did]['net_minutes']*100)
 for i in idxs:
  orig=old[(groups[i]['rows'][0]['need_id'],groups[i]['rows'][0]['slot'])]['person_id']
  for b,st,did in options[i]:
   if duties[did]['person_id'].startswith('VIK-'):obj.append(b*(groups[i]['end']-groups[i]['start'])*100)
   elif orig and duties[did]['person_id']!=orig:obj.append(b*3)
 model.minimize(sum(obj))
 solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=args.seconds_per_day;solver.parameters.num_search_workers=4
 status=solver.solve(model)
 if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):raise RuntimeError('day %d status %s'%(day,solver.status_name(status)))
 for i in idxs:
  chosen=[(did,solver.value(st)) for b,st,did in options[i] if solver.value(b)]
  assert len(chosen)==1;new[i]=chosen[0]
 summary['days']+=1;summary['options']+=sum(len(options[i]) for i in idxs)

changed=0
for i,g in enumerate(groups):
 did,start=new[i];delta=start-g['start'];person=duties[did]['person_id']
 for r in g['rows']:
  r['duty_id']=did;r['start']+=delta;r['end']+=delta;r['person_id']=person;r['position_id']=None
  r['staffing_status']='SYNTHETIC_SUBSTITUTE' if person.startswith('VIK-') else 'ASSIGNED_ORDINARY_FORECAST'
 changed+=bool(delta or did!=g['rows'][0]['duty_id'])
x['assignments']=[r for g in groups for r in g['rows']]+[a for a in x['assignments'] if a['kind']=='ADMIN']
used={a['duty_id'] for a in x['assignments']}
x['duties']=[d for d in x['duties'] if d['id'] in used]
x['candidate_id']='VG-20261202-'+hashlib.sha256(stable({'duties':x['duties'],'assignments':x['assignments']})).hexdigest()[:12]
report=validate(x)
oldcheck=[c for c in x['validation']['checks'] if c['scope']!='CANDIDATE']
checks=[{'id':k,'status':'FAIL' if k in report['failed'] else 'PASS','scope':'CANDIDATE','violations':report['failed'].get(k,0)} for k in sorted(set(report['passed'])|set(report['failed']))]
x['validation']['checks']=checks+oldcheck;x['validation']['summary']=dict(collections.Counter(c['status'] for c in checks+oldcheck))
x['validation']['workload']={'ordinary_minutes':report['ordinary_minutes'],'temporary_minutes':report['substitute_minutes'],'model_cost_sek':report['model_cost_sek']}
out=args.output;open(out,'wb').write(stable(x))
print(json.dumps({'summary':summary,'changed_groups':changed,'candidate_id':x['candidate_id'],'bytes':len(stable(x)),'sha256':hashlib.sha256(stable(x)).hexdigest(),'validator':{'failed':report['failed'],'ordinary_minutes':report['ordinary_minutes'],'substitute_minutes':report['substitute_minutes'],'duties':report['duties']}}))
