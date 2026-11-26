import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {PolicySession} from './policy.mjs';
const table=JSON.parse(readFileSync(process.argv[2],'utf8'));
const s=new PolicySession(table,'unknown',table.model_sha256);
assert.deepEqual(s.allowed(),['refresh']);
assert.throws(()=>s.step('abort-local','decision'));
s.step('refresh','committed'); assert.deepEqual(s.allowed(),['commit-local']);
s.step('commit-local','decision'); assert.equal(s.done,true);
const t=new PolicySession(table,'unknown',table.model_sha256); assert.throws(()=>t.step('refresh','unexpected')); assert.deepEqual(t.allowed(),[]);
assert.throws(()=>new PolicySession(table,'unknown','wrong-hash'));
console.log('JavaScript runtime: assertions passed');
const bad=structuredClone(table); const first=bad.nodes[bad.initial.unknown]; first.actions.refresh.committed=bad.initial.unknown;
assert.throws(()=>new PolicySession(bad,'unknown',table.model_sha256));
const bytes=readFileSync(process.argv[2]);
if(globalThis.crypto?.subtle){
  const {createHash}=await import('node:crypto');
  const digest=createHash('sha256').update(bytes).digest('hex');
  const checked=await PolicySession.fromVerifiedBytes(bytes,'unknown',table.model_sha256,digest);
  assert.deepEqual(checked.allowed(),['refresh']);
  await assert.rejects(PolicySession.fromVerifiedBytes(bytes,'unknown',table.model_sha256,'0'.repeat(64)));
  console.log('Artifact digest checks passed');
}
