"""Add verified night-break relief and finalize source-bound validation evidence."""
import argparse,json,collections,hashlib
from vg_validate_candidate import validate,stable,source_projection,external_work_rest,name_free,night_eligibility
parser=argparse.ArgumentParser()
parser.add_argument('--candidate',required=True)
parser.add_argument('--output',required=True)
parser.add_argument('--source-workbook',required=True)
parser.add_argument('--conditions-workbook',required=True)
parser.add_argument('--engine-commit',required=True)
args=parser.parse_args()
x=json.load(open(args.candidate))
x['engine_commit']=args.engine_commit
DEC_END=28*1440
night=[d for d in x['duties'] if d['segment_type']=='VAKEN_NATT']
next_vik=max(int(s['id'].split('-')[1]) for s in x['staff'] if s['id'].startswith('VIK-'))+1
resource=f'VIK-{next_vik}'
x['staff'].append({'id':resource,'type':'SYNTHETIC_SUBSTITUTE','alias':f'Vikarie {next_vik}'})
relief=[]
for day in range(28):
 missing=[]
 for m in range(day*1440+1320,(day+1)*1440+390,5):
  if not any(d['start']<=m<d['end'] and all(not(a<=m<b) for a,b in d['breaks']) for d in night):missing.append(m)
 if not missing:continue
 groups=[];start=prev=missing[0]
 for m in missing[1:]:
  if m>prev+5:groups.append((start,prev+5));start=m
  prev=m
 groups.append((start,prev+5))
 for gap_start,gap_end in groups:
  if day==27:
   start=day*1440+1285
   end=max(start+240,gap_end)
  else:
   start=max(0,gap_start-120)
   end=max(start+240,gap_end)
  if start%5 or end%5 or end-start>300:raise RuntimeError('invalid night relief span')
  did=f'C-NIGHT-RELIEF-{len(relief)+1:02d}'
  relief.append({'id':did,'slot':len(x['duties'])+len(relief),'day':start//1440,'start':start,'end':end,
                 'breaks':[],'net_minutes':end-start,'person_id':resource,'position_id':None,
                 'staffing_status':'SYNTHETIC_SUBSTITUTE','segment_type':'VAKEN_NATT','purpose':'AWAKE_NIGHT_BREAK_RELIEF'})
x['duties'].extend(relief)
for n in x['administration_requirements']:
 n['source_ref']='VC-beslut 2026-11-02; skyddad källa'
x['candidate_id']='VG-20261202-'+hashlib.sha256(stable({'duties':x['duties'],'assignments':x['assignments']})).hexdigest()[:12]
report=validate(x)
w=args.source_workbook;c=args.conditions_workbook
extra={'SOURCE_PROJECTION':source_projection(x,w),'EXTERNAL_WORK_REST':external_work_rest(x,w),'NIGHT_ELIGIBILITY':night_eligibility(x,c),'NAME_FREE':name_free(x,w)}
history=[z for z in x['validation']['checks'] if z.get('scope')!='CANDIDATE' and z['status'] in ('FAIL','UNKNOWN')]
checks=[{'id':k,'status':'FAIL' if k in report['failed'] else 'PASS','scope':'CANDIDATE','violations':report['failed'].get(k,0)} for k in sorted(set(report['passed'])|set(report['failed']))]
checks += [{'id':k,'status':v['status'],'scope':'SOURCE','details':{kk:vv for kk,vv in v.items() if kk!='status'}} for k,v in extra.items()]
checks += history
x['validation']={'scope':'DECEMBER','validator':'vg_validate_candidate.py','checks':checks,
                 'summary':dict(collections.Counter(z['status'] for z in checks)),
                 'workload':{'ordinary_minutes':report['ordinary_minutes'],'temporary_minutes':report['substitute_minutes'],
                             'model_cost_sek':report['model_cost_sek']}}
out=args.output;data=stable(x);open(out,'wb').write(data)
print(json.dumps({'candidate_id':x['candidate_id'],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'relief_duties':len(relief),'validator':report,'extra':extra,'checks':x['validation']['summary']},ensure_ascii=False))
