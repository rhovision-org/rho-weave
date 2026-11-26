// Optional read-only boundary adapters. No built-in networking or signing.
import {PolicySession} from './policy.mjs';
const HEX=/^[0-9a-f]{64}$/;
const isRecord=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
function admit(session,action) {
  if(!session.allowed().includes(action)) throw Error('action denied by policy: '+action);
}
// Caller supplies a verified finalized block anchor, not an untrusted latest tip.
// Transport is required to target the correct trusted chain and honor the by-hash API.
// No fallback and no partial results. Neither this adapter nor the policy authenticates
// node responses. Use a proof-verifying transport if the node is not trusted.
export async function anchoredRead(table,modelHash,getAnchor,readAt,terms) {
  if(!Array.isArray(terms)||!terms.length||terms.length>256||
     terms.some(t=>typeof t!=='string'||!t.length||t.length>65536)) throw Error('invalid terms');
  const requested=[...terms];
  const s=new PolicySession(table,'start',modelHash);
  admit(s,'pin-finalized');
  const anchor=await getAnchor();
  if(!isRecord(anchor)||typeof anchor.hash!=='string'||!HEX.test(anchor.hash)||
     typeof anchor.genesis!=='string'||!HEX.test(anchor.genesis)) throw Error('invalid finalized anchor');
  const hash=anchor.hash, genesis=anchor.genesis;
  s.step('pin-finalized','pinned');
  admit(s,'read-at-pin');
  const results=[];
  for(const term of requested) {
    const r=await readAt({term,blockHash:hash,usePreStateHash:false,genesis});
    if(!isRecord(r)||!Array.isArray(r.expr)) throw Error('malformed read result');
    // Transport must bind its result to the requested chain and hash. A plain
    // Rholo response does not itself supply cryptographic proof of that binding.
    results.push(structuredClone(r.expr));
  }
  s.step('read-at-pin','coherent');
  if(!s.done) throw Error('incomplete policy execution');
  return {blockHash:hash,genesis,results};
}
// This produces a recommendation, NOT a transaction, not a settlement.
// A status provider must distinguish confirmed absence from unreachability.
export async function recommendPreparedRecovery(table,modelHash,refresh) {
  const s=new PolicySession(table,'unknown',modelHash);
  admit(s,'refresh');
  const r=await refresh();
  if(!['absent','prepared','committed','aborted','retry-exhausted'].includes(r)) throw Error('unclassified or unauthenticated observation');
  s.step('refresh',r);
  const choices=s.allowed();
  if(choices.length!==1) throw Error('non-unique recommendation');
  const action=choices[0];
  s.step(action,action==='defer'?'deferred':'decision');
  if(!s.done) throw Error('incomplete recommendation policy');
  return {action,observation:r,settled:false};
}
