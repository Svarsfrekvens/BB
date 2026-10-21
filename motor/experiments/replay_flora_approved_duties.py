"""Local holdout replay of approved, executed whole duties.

Inputs are passed as paths and never bundled with this script. This is a
calibration experiment, not a future roster or a live engine request.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from bb.flora import check_case, solve_case
from bb.flora_import import prepare_case


def _union_minutes(spans):
    merged=[]
    for a,b in sorted(spans):
        if merged and a<=merged[-1][1]:merged[-1][1]=max(b,merged[-1][1])
        else:merged.append([a,b])
    return sum(b-a for a,b in merged)


def build_replay_case(submitted, profile, examples):
    request=submitted['request']
    case=prepare_case(request['input'],profile,request.get('scenario'))
    if not examples.get('clean_examples') or examples.get('purpose')!='CALIBRATION_EXAMPLES_NOT_ACTIVE_CANDIDATES':
        raise ValueError('Reviewed historical examples are required.')
    if any(r['code'] in ('St','Sj') for r in case['fixed_segments']):
        raise ValueError('Outcome codes may not be replayed as fixed work.')
    case['config']['break_policy']='EXPLICIT_NO_BREAK_SCENARIO'
    # The existing profile's reference breaks are mathematical, not source
    # clock times. This replay explicitly chooses zero deducted breaks.
    case['references']['import']['breaks']=[]
    H=case['horizon'];source_ar=defaultdict(list)
    for row in case['references']['import']['segments']:
        if row['code']=='Ar':
            a,b=max(0,row['start']),min(H,row['end'])
            if a<b:source_ar[row['person']].append((a,b))
    for person in case['staff']:
        if person['ordinary']:
            person['target_net']=_union_minutes(source_ar[person['id']])
    fixed={row['id']:row for row in case['fixed_segments']}
    held=[];all_ids=set();whole=[]
    for example in examples['clean_examples']:
        ids=example['source_segment_ids']
        if set(ids)-set(fixed):
            # G24 starts in P1 and is deliberately kept as known history.
            if example['group']=='G24':continue
            raise ValueError(f"Historical duty is not wholly fixed: {example['group']}")
        rows=sorted((fixed[sid] for sid in ids),key=lambda row:row['start'])
        if rows[0]['start']<0 or rows[-1]['end']>H:
            continue
        if rows[0]['person']!=example['observed_person_id'] or any(
            row['person']!=rows[0]['person'] for row in rows):
            raise ValueError(f"Historical person changed: {example['group']}")
        if [row['code'] for row in rows]!=[part['code'] for part in example['observed_shape']]:
            raise ValueError(f"Historical time types changed: {example['group']}")
        candidate_id='REPLAY-'+example['group']
        if example['span_minutes']==1440:
            whole.append(dict(id=candidate_id,person=rows[0]['person'],
                start=rows[0]['start'],end=rows[-1]['end'],
                parts=[dict(code=row['code'],start=row['start'],end=row['end']) for row in rows]))
        elif example['span_minutes']==660 and len(rows)==1:
            row=rows[0]
            case['candidates'].append(dict(id=candidate_id,person=row['person'],
                day=row['start']//1440,lo=row['start'],hi=row['end'],
                min_length=660,max_length=660))
        else:
            raise ValueError(f"Unmodelled historical pattern: {example['group']}")
        held.append(example['group']);all_ids.update(ids)
    case['fixed_segments']=[row for row in case['fixed_segments'] if row['id'] not in all_ids]
    case['whole_duty_candidates']=whole
    check_case(case)
    return case,held


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--submitted',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--examples',type=Path,required=True)
    parser.add_argument('--summary',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=20)
    args=parser.parse_args()
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    case,held=build_replay_case(read(args.submitted),read(args.profile),read(args.examples))
    result=solve_case(case,seconds=args.seconds,workers=1)
    chosen={r['pass_id'].removeprefix('generated:REPLAY-') for r in result['schedule']['segments']
            if isinstance(r['pass_id'],str) and r['pass_id'].startswith('generated:REPLAY-')}
    output=dict(method=result['method'],solver_status=result['solver_status'],
        heldout_groups=held,selected_groups=sorted(chosen),not_selected_groups=sorted(set(held)-chosen),
        covered_needs=result['after']['fully_covered_needs'],total_needs=result['after']['total_needs'],
        ordinary_active_minutes=result['after']['ordinary_net_minutes'],
        temporary_active_minutes=result['after']['temporary_net_minutes'],
        oncall_minutes=result['after']['jour_minutes'],break_minutes=result['after']['break_minutes'],
        checked_status=result['validation']['checked_status'],
        violation_rule_ids=sorted({v['rule'] for v in result['validation']['violations']}),
        unknown_rule_ids=sorted({v['rule_id'] for v in result['validation']['unknowns']}),
        objective_stages=result['solver']['phases'],
        local_only=True,source_or_business_data_changed=False,optimality_not_implied=True)
    args.summary.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{len(chosen)}/{len(held)} clean duties selected; "
          f"{output['covered_needs']}/{output['total_needs']} needs covered; "
          f"independent check {output['checked_status']}; {args.summary}")


if __name__=='__main__':
    main()
