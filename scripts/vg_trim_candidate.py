"""Trim redundant substitute duty edges without moving any need or reducing awake-night coverage."""
import argparse,json,collections
from vg_validate_candidate import stable
parser=argparse.ArgumentParser()
parser.add_argument('--candidate',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args()
x=json.load(open(args.candidate))
by=collections.defaultdict(list)
for a in x['assignments']:by[a['duty_id']].append(a)
saved=0;four=0
for d in x['duties']:
 if not d['person_id'].startswith('VIK-') or d['segment_type']!='AKTIVT_ARBETE':continue
 rows=by[d['id']];earliest=min(a['start'] for a in rows);latest=max(a['end'] for a in rows)
 best=None
 for start in range(d['start'],earliest+1,5):
  for end in range(((latest+4)//5)*5,d['end']+1,5):
   if end-start<240 or end-start>780:continue
   original_breaks=d['breaks']
   if any((a<start<b) or (a<end<b) for a,b in original_breaks):continue
   breaks=[v for v in original_breaks if start<=v[0] and v[1]<=end]
   if end-start>300 and sum(b-a for a,b in breaks)<30:
    gaps=[];prev=start
    for r in sorted(rows,key=lambda r:r['start']):
     if r['start']-prev>=30:gaps.append((prev,r['start']))
     prev=max(prev,r['end'])
    if end-prev>=30:gaps.append((prev,end))
    possible=[]
    for lo,hi in gaps:
     for b in range(((lo+4)//5)*5,hi-29,5):
      if b-start<=300 and end-(b+30)<=300:possible.append([b,b+30])
    if not possible:continue
    breaks=[possible[0]]
   last=start
   if any(a<start or b>end for a,b in breaks):continue
   valid=True
   for a,b in sorted(breaks):
    if a-last>300:valid=False
    last=b
   if end-last>300:valid=False
   if not valid:continue
   if any(max(a,r['start'])<min(b,r['end']) for a,b in breaks for r in rows):continue
   net=end-start-sum(b-a for a,b in breaks)
   if best is None or net<best[0]:best=(net,start,end,breaks)
 if best:
  old=d['net_minutes'];net,start,end,breaks=best
  saved+=old-net;four+=end-start==240 and old>net
  d.update(start=start,end=end,breaks=breaks,net_minutes=net)
day_saved=saved
by=collections.defaultdict(list)
for a in x['assignments']:by[a['duty_id']].append(a)
night=[d for d in x['duties'] if d['segment_type']=='VAKEN_NATT']
saved=0
for d in night:
 if not d['person_id'].startswith('VIK-') or not by[d['id']]:continue
 required=[]
 for day in range(28):
  for m in range(day*1440+1320,(day+1)*1440+390,5):
   providers=[q for q in night if q['start']<=m<q['end'] and all(not(a<=m<b) for a,b in q['breaks'])]
   if len(providers)==1 and providers[0]['id']==d['id']:required.append((m,m+5))
 rows=by[d['id']];intervals=[(r['start'],r['end']) for r in rows]+required;earliest=min(a for a,b in intervals);latest=max(b for a,b in intervals)
 best=None
 for start in range(d['start'],earliest+1,5):
  for end in range(((latest+4)//5)*5,d['end']+1,5):
   if end-start<240 or end-start>780:continue
   if any(a<start<b or a<end<b for a,b in d['breaks']):continue
   breaks=[v for v in d['breaks'] if start<=v[0] and v[1]<=end]
   if end-start>300 and sum(b-a for a,b in breaks)<30:continue
   last=start;valid=True
   for a,b in sorted(breaks):
    if a-last>300:valid=False
    last=b
   if end-last>300:valid=False
   if not valid:continue
   if any(max(a,u)<min(b,v) for a,b in breaks for u,v in intervals):continue
   net=end-start-sum(b-a for a,b in breaks)
   if best is None or net<best[0]:best=(net,start,end,breaks)
 if best:
  net,start,end,breaks=best;saved+=d['net_minutes']-net
  d.update(start=start,end=end,breaks=breaks,net_minutes=net)
night_saved=saved
open(args.output,'wb').write(stable(x))
print(json.dumps({'day_saved_minutes':day_saved,'night_saved_minutes':night_saved}))
