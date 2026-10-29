/** Only the newly authorized synthetic placement through the current parser. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { readEngineJob } from '@app/src/lib/flora/engine-client';
import { proposalOf } from '@app/src/lib/flora/engine-contract';
import { engineWorkingCopy } from '@app/src/lib/flora/engine-working-copy';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { emptyWork } from '@app/src/lib/flora/work';
import { initialDrafts } from '@app/src/lib/flora/review';
const dir=process.argv[2]!;
let forbidden=0;
const reject=()=>{forbidden++;throw Error('No network or persistence');};
globalThis.fetch=reject as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:reject,removeItem:reject}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:reject}});
const bytes=fs.readFileSync(dir+'/synthetic-job.raw.json');
const rawResult=fs.readFileSync(dir+'/synthetic-result.raw.json');
const input=JSON.parse(fs.readFileSync(dir+'/synthetic-input.json','utf8'));
const parsed=parseFloraText(JSON.stringify(input));assert.ok(parsed.ok);
const expected=JSON.parse(bytes.toString());
globalThis.fetch=(async(url:any,options:any)=>{
 assert.equal(url,'/api/engine/jobs/'+expected.id);
 assert.ok(!options.method || options.method==='GET');
 return new Response(bytes,{status:200});
}) as any;
const job=await readEngineJob(expected.id,'synthetic',input.metadata.business_id,undefined,'engine');
globalThis.fetch=reject as any;
assert.deepEqual(job.result,JSON.parse(rawResult.toString()));assert.ok(proposalOf(job));
const work=emptyWork(),drafts=initialDrafts(parsed.dataset),before=JSON.stringify({input,work,drafts});
const next=engineWorkingCopy(job,input.metadata.business_id,input,work,drafts);
assert.equal(job.result!.schedule.interventions[0].start,'2027-01-04T09:10+01:00');
assert.equal(job.result!.schedule.interventions[0].end,'2027-01-04T09:20+01:00');
assert.equal(job.result!.validation.overall,'UNKNOWN');
assert.deepEqual(next.proposal_copy!.need_windows,job.result!.need_window_contract);
assert.equal(next.proposal_copy!.placements[0].start,'2027-01-04T09:10+01:00');
assert.equal(job.result!.placement_domain_contract,undefined);
const bad=structuredClone(job);
bad.result!.schedule.interventions[0].start='2027-01-04T09:11+01:00';
bad.result!.schedule.interventions[0].end='2027-01-04T09:21+01:00';
assert.throws(()=>engineWorkingCopy(bad,input.metadata.business_id,input,work,drafts));
assert.equal(JSON.stringify({input,work,drafts}),before);assert.equal(forbidden,0);
const report={frontend_commit:'95b9c43ee92751397ddd066b2379e28a54a33df9',
 checks:[{case:'authorized_synthetic_placement_raw_export_to_current_parser_and_in_memory_proposal',status:'PASS'},
 {case:'movement_permission_does_not_allow_execution_window_overrun',status:'PASS'}],
 raw_result_sha256:crypto.createHash('sha256').update(rawResult).digest('hex'),field_translation:false,
 original_state_unchanged:true,persistence_calls:0,network_calls:0,no_live_browser_rerun:true,no_actual_flora_result:true};
fs.writeFileSync(dir+'/frontend-evidence.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
