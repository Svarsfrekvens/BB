/** Private source-certificate check. Does not create a proposal or persisted copy. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { originalRunBasis, engineOriginalChanges } from '@app/src/lib/flora/engine-comparison';
import { proposalOf } from '@app/src/lib/flora/engine-contract';
let forbiddenCalls=0;
const forbidden=()=>{forbiddenCalls++;throw Error('Network/persistence forbidden');};
globalThis.fetch=forbidden as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:forbidden,removeItem:forbidden,clear:forbidden}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:forbidden,deleteDatabase:forbidden}});
const dir=process.argv[2]!;
const bytes=fs.readFileSync(dir+'/positive-source-export.json');
const result=JSON.parse(bytes.toString());
const input=JSON.parse(fs.readFileSync(dir+'/exact-input.json','utf8'));
const before=JSON.stringify(result);
const parsed=parseFloraText(JSON.stringify(input));
assert.equal(parsed.ok,true);if(!parsed.ok)throw Error('Source parse rejected');
assert.equal(originalRunBasis(result),true);
assert.notEqual(engineOriginalChanges(result,parsed.dataset.segments),null);
assert.equal(result.source_basis.segments.length,292);
assert.equal(result.source_basis.source_identity,'0c8fb9635f4a8562fb1b592702c30eb9c955e48937e5ba2f39ac81a6a05390c4');
assert.equal(result.source_basis.source_file_sha256,'5bd741c2a7f6e9058b32e3d6858b0f8951c1d1816eccd85c3cee1a1f5fd1ca38');
assert.equal('history_period_id' in input.metadata,false);assert.equal('source_layout' in input.metadata,false);
assert.equal(result.schedule.segments.length,0);
assert.equal(proposalOf({status:'succeeded',result} as any),null);
assert.equal(JSON.stringify(result),before);assert.equal(forbiddenCalls,0);
console.log(JSON.stringify({frontend_commit:'ce9668eab9a2e048dd5a7c142fbd28e42ed6d701',status:'PASS',source_segments:292,
 source_proof_accepted:true,period_source_rows_match:true,raw_json_sha256:createHash('sha256').update(bytes).digest('hex'),
 raw_export_unmodified:true,no_field_translation:true,no_proposal_or_solver_result:true,forbidden_calls:forbiddenCalls},null,2));
