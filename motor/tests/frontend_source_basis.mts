/** Read-only harness against the exact, unmodified frontend archive. */
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { originalRunBasis, engineOriginalChanges } from '@app/src/lib/flora/engine-comparison';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { computationOf, proposalOf } from '@app/src/lib/flora/engine-contract';

let forbiddenCalls=0;
const forbidden=()=>{forbiddenCalls++;throw Error('Network/persistence forbidden');};
globalThis.fetch=forbidden as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:forbidden,removeItem:forbidden,clear:forbidden}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:forbidden,deleteDatabase:forbidden}});
const dir=process.argv[2]!;
const bytes=fs.readFileSync(dir+'/motor-result.json');
const result=JSON.parse(bytes.toString());
const input=JSON.parse(fs.readFileSync(dir+'/synthetic-input.json','utf8'));
const frozen=JSON.stringify(result);
const source=parseFloraText(JSON.stringify(input));
assert.equal(source.ok,true);
if(!source.ok)throw Error('Synthetic source parse failed');
const results:{case:string,status:string}[]=[];
function check(name:string,fn:()=>void){fn();results.push({case:name,status:'PASS'});}
// Only a synthetic status envelope; raw motor JSON is never translated or amended.
const job={id:'synthetic-source-basis-no-job',status:'succeeded',result} as any;
check('computationOf receives unchanged motor export',()=>assert.equal(computationOf(job),result));
check('proposalOf accepts existing validated synthetic schedule',()=>assert.equal(proposalOf(job),result));
check('complete joint-method proof accepted',()=>assert.equal(originalRunBasis(result),true));
check('exact source rows accepted for comparison',()=>assert.deepEqual(engineOriginalChanges(result,source.dataset.segments),[]));
check('missing proof rejected with actual historical profile name',()=>{
 const bad=structuredClone(result);delete bad.source_basis;
 bad.provenance={engine_context:{profile_id:'flora-original-upload-morning-plan-historical-pass-20261021'}};
 assert.equal(originalRunBasis(bad),false);assert.equal(engineOriginalChanges(bad,source.dataset.segments),null);
});
for(const [field,value] of [['kind','UNVERIFIED'],['verification','UNKNOWN'],['source_identity','x'.repeat(64)],['source_file_sha256',null],['segments',null]]){
 check('invalid '+field+' rejected',()=>{const bad=structuredClone(result);bad.source_basis[field as string]=value;assert.equal(originalRunBasis(bad),false);});
}
for(const field of ['person_id','start','end','code','segment_id']){
 check('changed source '+field+' rejected',()=>{
  const bad=structuredClone(result);
  const row=bad.source_basis.segments.find((r:any)=>r.segment_id==='active-row');
  assert.ok(row);row[field]=field==='start'?'2027-01-04T08:01':field==='end'?'2027-01-04T11:59':'changed';
  assert.equal(engineOriginalChanges(bad,source.dataset.segments),null);
 });
}
check('missing original row rejected',()=>{const bad=structuredClone(result);bad.source_basis.segments=bad.source_basis.segments.filter((r:any)=>r.segment_id!=='active-row');assert.equal(engineOriginalChanges(bad,source.dataset.segments),null);});
check('duplicate original row rejected',()=>{const bad=structuredClone(result);bad.source_basis.segments.push(bad.source_basis.segments.find((r:any)=>r.segment_id==='active-row'));assert.equal(engineOriginalChanges(bad,source.dataset.segments),null);});
assert.equal(JSON.stringify(result),frozen);
assert.equal(forbiddenCalls,0);
console.log(JSON.stringify({frontend_commit:'ce9668eab9a2e048dd5a7c142fbd28e42ed6d701',
 raw_motor_json_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),
 unchanged_result:true,field_translation:false,forbidden_calls:forbiddenCalls,results},null,2));
