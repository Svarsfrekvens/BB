"""Finalize source-bound evidence without inventing a full-night staffing minimum."""
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
relief=[]
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
x['validation']={'scope':'DECEMBER','validator':'vg_validate_candidate.py','validator_commit':args.engine_commit,'checks':checks,
                 'summary':dict(collections.Counter(z['status'] for z in checks)),
                 'workload':{'ordinary_minutes':report['ordinary_minutes'],'temporary_minutes':report['substitute_minutes'],
                             'model_cost_sek':report['model_cost_sek']}}
out=args.output;data=stable(x);open(out,'wb').write(data)
print(json.dumps({'candidate_id':x['candidate_id'],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'relief_duties':len(relief),'validator':report,'extra':extra,'checks':x['validation']['summary']},ensure_ascii=False))
