/** One compatibility experiment; exact production frontend imports, no edits. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readEngineJob } from '@app/src/lib/flora/engine-client';
import { computationOf, proposalOf } from '@app/src/lib/flora/engine-contract';
import { engineWorkingCopy } from '@app/src/lib/flora/engine-working-copy';
import { parseFloraText } from '@app/src/lib/flora/contract';
import { emptyWork } from '@app/src/lib/flora/work';
import { initialDrafts } from '@app/src/lib/flora/review';

const root=process.argv[2]!;
let forbiddenCalls=0, inMemoryReads=0;
const forbidden=()=>{forbiddenCalls++;throw Error('Persistence/network forbidden');};
globalThis.fetch=forbidden as any;
Object.defineProperty(globalThis,'localStorage',{value:{getItem:()=>null,setItem:forbidden,removeItem:forbidden,clear:forbidden}});
Object.defineProperty(globalThis,'indexedDB',{value:{open:forbidden,deleteDatabase:forbidden}});
const cases:any[]=[];
async function check(name:string, fn:()=>unknown|Promise<unknown>){
  try { const evidence=await fn(); cases.push({name,status:'PASS',...(evidence?{evidence}:{})}); }
  catch(e){cases.push({name,status:'FAIL',error:(e as Error).message});}
}
const sha=(b:Buffer)=>createHash('sha256').update(b).digest('hex');
const hashes:any[]=[];
for(const mode of ['start_window','execution_window']){
  const dir=path.join(root,mode);
  const rawJob=fs.readFileSync(path.join(dir,'job.raw.json'));
  const rawResult=fs.readFileSync(path.join(dir,'result.raw.json'));
  const originalJob=JSON.parse(rawJob.toString('utf8'));
  const originalResult=JSON.parse(rawResult.toString('utf8'));
  const source=JSON.parse(fs.readFileSync(path.join(dir,'input.json'),'utf8'));
  assert.deepEqual(originalJob.result,originalResult);
  hashes.push({mode,raw_result_sha256:sha(rawResult),raw_job_sha256:sha(rawJob)});
  const parsed=parseFloraText(JSON.stringify(source));
  assert.equal(parsed.ok,true);
  const work=emptyWork(),drafts=initialDrafts((parsed as any).dataset);
  const stateBefore=JSON.stringify({source,work,drafts});
  async function parse(bytes:Buffer){
    // Serve the exact response bytes in memory. No actual HTTP request is made.
    globalThis.fetch=(async (url:any,options:any)=>{
      assert.equal(url,`/api/engine/jobs/${originalJob.id}`);
      assert.ok(!options.method || options.method==='GET');
      assert.equal(options.headers['X-BB-Organization'],source.metadata.business_id);
      inMemoryReads++;
      return new Response(bytes,{status:200,headers:{'Content-Type':'application/json'}});
    }) as any;
    const job=await readEngineJob(originalJob.id,'synthetic-local-token',source.metadata.business_id,undefined,'engine');
    globalThis.fetch=forbidden as any;
    assert.ok(computationOf(job));assert.ok(proposalOf(job));
    return {job,next:engineWorkingCopy(job,source.metadata.business_id,source,work,drafts)};
  }
  await check(`${mode}:raw_export_to_actual_job_parser`,async()=>{
    const {job,next}=await parse(rawJob);
    assert.deepEqual(job,originalJob);
    assert.deepEqual(job.result,originalResult);
    assert.deepEqual(next.proposal_copy?.need_windows,originalResult.need_window_contract);
    assert.equal(originalResult.need_window_contract.needs.length,2);
    assert.equal(new Set(originalResult.need_window_contract.needs.map((n:any)=>n.need_id)).size,2);
    assert.equal(originalResult.source_basis.verification,'EXACT_SERVER_REVIEWED_INPUT');
    assert.deepEqual(job.result!.source_basis,originalResult.source_basis);
    const p=next.proposal_copy!.placements[0]!;
    const w=originalResult.need_window_contract.needs[0];
    for(const field of ['window_semantics','source_window_start','source_window_end','duration_minutes','personnel_count'])
      assert.equal((p as any)[field],w[field]);
    assert.equal(job.result!.validation.overall,'UNKNOWN');
    assert.equal(job.result!.review_required,true);
    assert.equal(job.result!.business_schedule_approved,false);
    assert.equal(job.result!.provenance!.input_hash,job.input_hash);
    assert.equal(job.result!.provenance!.job_id,job.id);
    assert.equal(job.result!.provenance!.engine_context!.business_id,source.metadata.business_id);
    assert.equal(JSON.stringify({source,work,drafts}),stateBefore);
    if(mode==='start_window'){
      assert.ok(p.end>w.source_window_end);
      assert.equal(p.start,w.source_window_end);
    } else { assert.ok(p.start>=w.source_window_start && p.end<=w.source_window_end); }
    assert.equal(next.proposal_copy!.placement_domains,undefined);
    return {raw_json_unchanged:true,window_contract_preserved:true,duration:p.duration_minutes,
      personnel_count:p.personnel_count,placement_domain_contract:'NOT_REQUIRED_NO_SOURCE_WINDOW_EXCEPTION',
      start:p.start,end:p.end};
  });
  const opposite=mode==='start_window'?'EXECUTION_WINDOW':'START_WINDOW';
  const variants:[string,string,any][]=[
    ['contract_type','result.need_window_contract.needs.0.window_semantics',opposite],
    ['contract_left','result.need_window_contract.needs.0.source_window_start','2027-01-04T08:00+01:00'],
    ['contract_right','result.need_window_contract.needs.0.source_window_end','2027-01-04T09:21+01:00'],
    ['contract_duration','result.need_window_contract.needs.0.duration_minutes',originalResult.need_window_contract.needs[0].duration_minutes+1],
    ['contract_count','result.need_window_contract.needs.0.personnel_count',2],
    ['missing_required_window_contract','result.need_window_contract',undefined],
    ['placement_type','result.schedule.interventions.0.window_semantics',opposite],
    ['placement_left','result.schedule.interventions.0.source_window_start','2027-01-04T08:00+01:00'],
    ['placement_right','result.schedule.interventions.0.source_window_end','2027-01-04T09:21+01:00'],
    ['placement_duration','result.schedule.interventions.0.duration_minutes',originalResult.need_window_contract.needs[0].duration_minutes+1],
    ['placement_count','result.schedule.interventions.0.personnel_count',2],
    ['outside_source_without_required_domain_evidence','result.schedule.interventions.0.start','2027-01-04T08:59+01:00'],
  ];
  if(mode==='execution_window') variants.push(['execution_overrun','result.schedule.interventions.0.end','2027-01-04T09:21+01:00']);
  else variants.push(['start_after_latest','result.schedule.interventions.0.start','2027-01-04T09:21+01:00']);
  for(const [label,field,value] of variants){
    await check(`${mode}:reject_${label}`,async()=>{
      const changed=structuredClone(originalJob), parts=field.split('.');
      const leaf=parts.pop()!;let parent=changed;
      for(const part of parts)parent=parent[part];
      const old=structuredClone(parent[leaf]);
      if(value===undefined)delete parent[leaf];else parent[leaf]=value;
      let message:string|undefined;
      try{await parse(Buffer.from(JSON.stringify(changed)));}catch(e){message=(e as Error).message;}
      assert.ok(message,'Contradictory result was accepted');
      // Prove that restoring this one field restores the exact original object.
      parent[leaf]=old;assert.deepEqual(changed,originalJob);
      assert.equal(JSON.stringify({source,work,drafts}),stateBefore);
      return {mutated_field:field,error:message};
    });
  }
  assert.deepEqual(fs.readFileSync(path.join(dir,'result.raw.json')),rawResult);
  assert.deepEqual(fs.readFileSync(path.join(dir,'job.raw.json')),rawJob);
}
const report={app_commit:'c6d2c810de8628a33177c35c70a6e7e0ddd6081d',
  motor_base:'d60b518922040771016a6335f8d1310a6fbe249a',
  entry:'readEngineJob -> jobResponse -> computationOf/proposalOf -> engineWorkingCopy -> checkNeedWindowContract/checkPlacementWindow -> validateProposalCopy/placementDomainErrors -> proposal_copy',
  raw_exports:hashes,cases,pass:cases.filter(x=>x.status==='PASS').length,
  fail:cases.filter(x=>x.status==='FAIL').length,in_memory_reads:inMemoryReads,
  actual_network_calls:0,persistence_calls:forbiddenCalls,
  placement_domain_scope:'Exporter does not emit placement_domain_contract; no typed source-window exception is allowed. Absence is valid inside source windows, and out-of-window mutations without domain evidence are rejected. Positive domain-exception path and deletion of an emitted mandatory contract are not exercised.'};
fs.writeFileSync(path.join(root,'frontend-evidence.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(report.fail || forbiddenCalls)process.exitCode=1;
