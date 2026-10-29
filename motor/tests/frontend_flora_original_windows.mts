/** Exact frontend imports; transport fixture only, no network or saved working copy. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { readEngineJob } from '@app/src/lib/flora/engine-client';
import { computationOf, proposalOf } from '@app/src/lib/flora/engine-contract';
import { engineWorkingCopy } from '@app/src/lib/flora/engine-working-copy';
import { originalRunBasis } from '@app/src/lib/flora/engine-comparison';
import { checkNeedWindowContract } from '@app/src/lib/flora/need-window-contract';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { emptyWork } from '@app/src/lib/flora/work';
import { initialDrafts } from '@app/src/lib/flora/review';
const dir=process.argv[2]!, privateDir=process.argv[3]!;
let forbiddenCalls=0;
const forbidden=()=>{forbiddenCalls++;throw Error('Network/persistence forbidden');};
globalThis.fetch=forbidden as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:forbidden,removeItem:forbidden,clear:forbidden}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:forbidden,deleteDatabase:forbidden}});
const resultBytes=fs.readFileSync(dir+'/synthetic-result.raw.json');
const result=JSON.parse(resultBytes.toString());
const jobBytes=fs.readFileSync(dir+'/synthetic-job.raw.json');
const originalJob=JSON.parse(jobBytes.toString());
const input=JSON.parse(fs.readFileSync(dir+'/synthetic-input.json','utf8'));
const parsed=parseFloraText(JSON.stringify(input));assert.ok(parsed.ok);
const work=emptyWork(),drafts=initialDrafts(parsed.dataset);
const before=JSON.stringify({input,work,drafts});
const results:any[]=[];
async function parse(bytes:Buffer){
 globalThis.fetch=(async(url:any,options:any)=>{
   assert.equal(url,'/api/engine/jobs/'+originalJob.id);
   assert.ok(!options.method || options.method==='GET');
   return new Response(bytes,{status:200,headers:{'Content-Type':'application/json'}});
 }) as any;
 let job;
 try{job=await readEngineJob(originalJob.id,'synthetic',input.metadata.business_id,undefined,'engine');}
 finally{globalThis.fetch=forbidden as any;}
 assert.ok(computationOf(job));assert.ok(proposalOf(job));
 return {job,next:engineWorkingCopy(job,input.metadata.business_id,input,work,drafts)};
}
const positive=await parse(jobBytes);
assert.deepEqual(positive.job.result,result);
assert.deepEqual(positive.next.proposal_copy!.need_windows,result.need_window_contract);
assert.ok(originalRunBasis(positive.job.result!));
assert.deepEqual(positive.job.result!.source_basis,result.source_basis);
assert.equal(result.need_window_contract.needs[0].window_semantics,'EXECUTION_WINDOW');
assert.equal(result.schedule.interventions[0].end,result.need_window_contract.needs[0].source_window_end);
assert.equal(result.placement_domain_contract,undefined);
results.push({case:'unchanged_raw_export_to_parser_and_proposal_copy',status:'PASS'});
for(const [path,value] of [
 ['result.need_window_contract.needs.0.window_semantics','START_WINDOW'],
 ['result.need_window_contract.needs.0.source_window_start','2027-01-04T08:00+01:00'],
 ['result.need_window_contract.needs.0.source_window_end','2027-01-04T20:00+01:00'],
 ['result.need_window_contract.needs.0.duration_minutes',11],
 ['result.need_window_contract.needs.0.personnel_count',2],
 ['result.schedule.interventions.0.start','2027-01-04T08:59+01:00'],
 ['result.schedule.interventions.0.end','2027-01-04T09:21+01:00'],
 ['result.placement_domain_contract',{version:'bb-placement-domains/1.0',input_hash:'forged'}],
] as [string,unknown][]){
 const bad=structuredClone(originalJob),parts=path.split('.');let parent=bad;
 for(const key of parts.slice(0,-1))parent=parent[key];parent[parts.at(-1)!]=value;
 await assert.rejects(()=>parse(Buffer.from(JSON.stringify(bad))));
 results.push({case:'reject_'+path,status:'PASS'});
}
// The actual 1451-row contract is checked against actual source without creating
// any schedule, result interpretation or business working copy.
const actualInput=JSON.parse(fs.readFileSync(privateDir+'/exact-input.json','utf8'));
const actualContract=JSON.parse(fs.readFileSync(dir+'/need-window-contract.private.json','utf8'));
const actual=parseFloraText(JSON.stringify(actualInput));assert.ok(actual.ok);
const periodNeeds=actualInput.customer_needs.filter((n:any)=>n.date>='2026-05-11'&&n.date<='2026-06-07');
const checked=checkNeedWindowContract(actualContract,periodNeeds,actual.dataset,(message:string):never=>{throw Error(message);});
assert.equal(checked.size,1451);
assert.ok([...checked.values()].every(n=>n.window_semantics==='EXECUTION_WINDOW'));
results.push({case:'all_1451_original_windows_match_actual_frontend_source',status:'PASS'});
assert.equal(JSON.stringify({input,work,drafts}),before);
assert.deepEqual(fs.readFileSync(dir+'/synthetic-result.raw.json'),resultBytes);
assert.equal(forbiddenCalls,0);
const report={app_commit:'c6d2c810de8628a33177c35c70a6e7e0ddd6081d',
 raw_result_sha256:crypto.createHash('sha256').update(resultBytes).digest('hex'),
 field_translation:false,actual_network_calls:0,persistence_calls:forbiddenCalls,
 results,pass:results.length,fail:0,actual_period_contract_rows:checked.size,
 no_actual_flora_schedule_or_feasibility_claim:true};
fs.writeFileSync(dir+'/frontend-evidence.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
