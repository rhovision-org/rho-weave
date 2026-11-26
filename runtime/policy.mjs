// Offline policy monitor. A trusted model hash alone does not authenticate a table.
const own=(obj,key)=>Object.hasOwn(obj,key);
const record=x=>x!==null && typeof x==='object' && !Array.isArray(x);
const rank=x=>Number.isSafeInteger(x)&&x>=0;
function validate(t,hash){
  if(!record(t)||t.format!==1||typeof hash!=='string'||!(/^[a-f0-9]{64}$/).test(hash)||t.model_sha256!==hash||!record(t.initial)||!record(t.nodes)||!Object.keys(t.initial).length||!Object.keys(t.nodes).length) throw Error('invalid policy binding');
  for(const id of Object.values(t.initial)) if(typeof id!=='string'||!own(t.nodes,id)) throw Error('invalid initial node');
  for(const n of Object.values(t.nodes)){
    if(!record(n)||!rank(n.rank)||!record(n.actions)||(n.rank===0)!==(Object.keys(n.actions).length===0)) throw Error('invalid policy node');
    for(const outcomes of Object.values(n.actions)){
      if(!record(outcomes)||!Object.keys(outcomes).length) throw Error('invalid outcomes');
      for(const id of Object.values(outcomes)) if(typeof id!=='string'||!own(t.nodes,id)||!rank(t.nodes[id]?.rank)||t.nodes[id].rank>=n.rank) throw Error('non-descending outcome');
    }
  }
}
export class PolicySession {
  #table; #state; #failed=false;
  constructor(table, initialObservation, expectedModelHash) {
    this.#table=structuredClone(table); validate(this.#table,expectedModelHash);
    if(!own(this.#table.initial,initialObservation)) throw Error('initial observation mismatch');
    this.#state=this.#table.initial[initialObservation];
  }
  // The expected artifact digest must come from an independently trusted channel.
  static async fromVerifiedBytes(bytes, observation, modelHash, artifactHash) {
    if(!globalThis.crypto?.subtle||typeof artifactHash!=='string'||!(/^[a-f0-9]{64}$/).test(artifactHash)) throw Error('artifact verification unavailable');
    const copy=new Uint8Array(bytes);
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',copy)),x=>x.toString(16).padStart(2,'0')).join('');
    if(digest!==artifactHash) throw Error('policy artifact digest mismatch');
    return new PolicySession(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(copy)),observation,modelHash);
  }
  allowed(){return this.#failed?[]:Object.keys(this.#table.nodes[this.#state].actions).sort();}
  get done(){return !this.#failed&&this.#table.nodes[this.#state].rank===0;}
  step(action, observation){
    if(!this.allowed().includes(action)) throw Error('action denied');
    const next=this.#table.nodes[this.#state].actions[action];
    if(!own(next,observation)){this.#failed=true;throw Error('unexpected observation; session invalidated');}
    this.#state=next[observation];
  }
}
