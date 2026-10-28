/** External read-only harness: aliases point to the exact unmodified app archive. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { engineWorkingCopy } from '@app/src/lib/flora/engine-working-copy';
import { previewProposalTransfer } from '@app/src/lib/flora/proposal-transfer';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { computationOf, proposalOf } from '@app/src/lib/flora/engine-contract';
import { emptyWork } from '@app/src/lib/flora/work';
import { initialDrafts } from '@app/src/lib/flora/review';

let forbiddenCalls=0;
const forbidden=()=>{forbiddenCalls++;throw Error('Network or persistence forbidden');};
globalThis.fetch=forbidden as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:forbidden,removeItem:forbidden,clear:forbidden}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:forbidden,deleteDatabase:forbidden}});
const exported=JSON.parse(fs.readFileSync(process.argv[2]!, 'utf8'));
const source=exported.input;
const result=exported.result;
// The worker envelope is simulated; result fields below came from actual motor normalization.
result.input_hash='synthetic-no-job';
result.provenance={input_hash:'synthetic-no-job',job_id:'a'.repeat(32),profile_hash:'b'.repeat(64),engine_context:{business_id:source.metadata.business_id,data_use:'development',profile_id:'synthetic-window-reviewed'}};
const job={id:'a'.repeat(32),status:'succeeded',input_hash:result.input_hash,created_at:'2027-01-04T00:00:00Z',started_at:null,finished_at:null,error:null,result};
const parsed=parseFloraText(JSON.stringify(source));
assert.equal(parsed.ok,true,JSON.stringify(parsed));
const context={original:source,organizationId:source.metadata.business_id,work:emptyWork(),drafts:initialDrafts((parsed as any).dataset),fileName:'synthetic-only.json'};
const file={format:'bb-proposal-transfer/1.0',id:'synthetic-no-job',organization_id:context.organizationId,producer:{kind:'local-model-run',build_commit:'a'.repeat(40)},source_input:source,result};
const before=JSON.stringify({source,result,context});
const cases:any[]=[];
function check(name:string,fn:()=>void){try{fn();cases.push({name,status:'PASS'});}catch(e){cases.push({name,status:'FAIL',error:(e as Error).message});}}
const engine=(r:any)=>engineWorkingCopy({...job,result:r} as any,context.organizationId,source,context.work,context.drafts);
const preview=(r:any)=>previewProposalTransfer({...file,result:r},context);
check('job_and_proposal_gates_accept_actual_normalized_result',()=>{assert.ok(computationOf(job as any));assert.ok(proposalOf(job as any));});
check('actual_engine_parser_accepts_export',()=>{const work=engine(structuredClone(result));assert.deepEqual(work.proposal_copy?.need_windows,result.need_window_contract);});
check('file_preview_parser_accepts_export',()=>{const p=preview(structuredClone(result));assert.deepEqual(p.copy.need_windows,result.need_window_contract);});
const variants:[string,(r:any)=>void][]=[
 ['missing_contract',r=>{delete r.need_window_contract;}],
 ['wrong_version',r=>{r.need_window_contract.version='bad';}],
 ['missing_need',r=>{r.need_window_contract.needs=[];}],
 ['duplicate_need',r=>{r.need_window_contract.needs.push(structuredClone(r.need_window_contract.needs[0]));}],
 ['unknown_type',r=>{r.need_window_contract.needs[0].window_semantics='BAD';}],
 ['contradict_source_type',r=>{r.need_window_contract.needs[0].window_semantics='EXECUTION_WINDOW';}],
 ['contradict_source_bound',r=>{r.need_window_contract.needs[0].source_window_start='2027-01-04T08:00+01:00';}],
 ['contradict_duration',r=>{r.need_window_contract.needs[0].duration_minutes=59;}],
 ['contradict_person_count',r=>{r.need_window_contract.needs[0].personnel_count=2;}],
];
for(const [name,mutate]of variants){
 for(const [route,parse]of [['engine',engine],['file_preview',preview]] as const){
  check(`${route}_rejects_${name}`,()=>{const r=structuredClone(result);mutate(r);assert.throws(()=>parse(r));});
 }
}
check('UNKNOWN_not_approved_and_no_mutation',()=>{assert.equal(result.validation.overall,'UNKNOWN');assert.equal(result.review_required,true);assert.equal(result.business_schedule_approved,false);assert.equal(JSON.stringify({source,result,context}),before);assert.equal(forbiddenCalls,0);});
console.log(JSON.stringify({app_commit:'585c3a12356dc5e3a05f6a00d4f6cf2dc3f3950d',fixture:'actual motor import/validation/normalization; synthetic job envelope; no solver',cases,pass:cases.filter(x=>x.status==='PASS').length,fail:cases.filter(x=>x.status==='FAIL').length,forbidden_calls:forbiddenCalls},null,2));
if(cases.some(x=>x.status==='FAIL'))process.exitCode=1;
