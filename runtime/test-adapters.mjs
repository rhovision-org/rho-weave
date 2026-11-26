import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {anchoredRead,recommendPreparedRecovery} from './adapters.mjs';
const load=p=>JSON.parse(readFileSync(p,'utf8'));
const gov=load(process.argv[2]), qos=load(process.argv[3]);
const A='a'.repeat(64), B='b'.repeat(64), G='c'.repeat(64);
let head=A;
const naive=[head]; head=B; naive.push(head);
assert.notEqual(naive[0],naive[1]);
const calls=[];
const result=await anchoredRead(gov,gov.model_sha256,async()=>({hash:A,genesis:G}),async req=>{
  calls.push(req); head=B; return {expr:[req.blockHash]};
},['membership','tally']);
assert.deepEqual(result.results,[[A],[A]]);
assert.equal(calls.length,2);
assert.ok(calls.every(c=>c.blockHash===A&&c.genesis===G&&c.usePreStateHash===false));
await assert.rejects(anchoredRead(gov,gov.model_sha256,async()=>({hash:'bad',genesis:G}),async()=>{throw Error('must not read')},['x']),/invalid finalized anchor/);
let attempts=0;
await assert.rejects(anchoredRead(gov,gov.model_sha256,async()=>({hash:A,genesis:G}),async()=>{attempts++; throw Error('404')},['x','y']),/404/);
assert.equal(attempts,1);
await assert.rejects(anchoredRead(gov,gov.model_sha256,async()=>({hash:A,genesis:G}),async()=>({expr:null}),['x']),/malformed/);
for(const [obs,action] of Object.entries({absent:'abort-local',prepared:'commit-both',committed:'commit-local',aborted:'abort-local','retry-exhausted':'defer'})){
  const r=await recommendPreparedRecovery(qos,qos.model_sha256,async()=>obs);
  assert.deepEqual(r,{action,observation:obs,settled:false});
}
await assert.rejects(recommendPreparedRecovery(qos,qos.model_sha256,async()=>'unknown'),/unclassified/);
await assert.rejects(recommendPreparedRecovery(qos,qos.model_sha256,async()=>{throw Error('transport unavailable')}),/transport unavailable/);
console.log('Read-only boundary adapter tests passed');
