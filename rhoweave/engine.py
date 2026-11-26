from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib, json

class ModelError(ValueError): pass
class LimitError(ModelError): pass

MAX_STATES=256
MAX_EDGES=20000
MAX_ACTIONS=256
MAX_BELIEFS=10000
MAX_WORK=2_000_000

@dataclass(frozen=True)
class Model:
    states: dict
    edges: dict
    initial: tuple
    digest: str

    @classmethod
    def parse(cls, raw):
        if not isinstance(raw,dict) or set(raw)!={'name','states','initial','transitions'}: raise ModelError('expected name, states, initial, transitions')
        if not isinstance(raw['name'],str) or not raw['name']: raise ModelError('invalid name')
        states=raw['states']; initial=raw['initial']; transitions=raw['transitions']
        if not isinstance(states,dict) or not 0<len(states)<=MAX_STATES: raise ModelError('invalid state count')
        for s,p in states.items():
            if not isinstance(s,str) or not s or not isinstance(p,dict) or set(p)!={'observation','safe','goal'}: raise ModelError('invalid state')
            if not isinstance(p['observation'],str) or not p['observation'] or type(p['safe']) is not bool or type(p['goal']) is not bool or p['goal'] and not p['safe']: raise ModelError('invalid state properties')
        if not isinstance(initial,list) or not initial or any(not isinstance(s,str) or s not in states for s in initial) or len(set(initial))!=len(initial): raise ModelError('invalid initial states')
        if not isinstance(transitions,list) or len(transitions)>MAX_EDGES: raise ModelError('invalid transitions')
        edges=defaultdict(lambda:defaultdict(set)); actions=set()
        for t in transitions:
            if not isinstance(t,list) or len(t)!=3 or any(not isinstance(x,str) for x in t): raise ModelError('transition must be [source,action,target]')
            s,a,d=t
            if s not in states or d not in states or not a: raise ModelError('invalid transition reference')
            if states[s]['goal']: raise ModelError('goal states must be terminal')
            edges[s][a].add(d); actions.add(a)
        if len(actions)>MAX_ACTIONS: raise LimitError('action budget exceeded')
        digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        return cls(states,{s:{a:tuple(sorted(ds)) for a,ds in es.items()} for s,es in edges.items()},tuple(sorted(initial)),digest)

    def partition(self, states):
        groups=defaultdict(list)
        for s in sorted(set(states)): groups[self.states[s]['observation']].append(s)
        return {o:tuple(v) for o,v in sorted(groups.items())}

    def outcomes(self, belief):
        # Only actions executable in every possible concrete state are admissible.
        common=set(self.edges.get(belief[0],{}))
        for s in belief[1:]: common.intersection_update(self.edges.get(s,{}))
        return {a:self.partition(d for s in belief for d in self.edges[s][a]) for a in sorted(common)}

    def safe(self,b): return all(self.states[s]['safe'] for s in b)
    def goal(self,b): return all(self.states[s]['goal'] for s in b)

def graph(m,limit=MAX_BELIEFS):
    roots=m.partition(m.initial); q=deque(roots.values()); seen=set(q); edges={}; work=0
    if len(seen)>limit: raise LimitError('belief budget exceeded')
    while q:
        b=q.popleft(); edges[b]=m.outcomes(b) if m.safe(b) and not m.goal(b) else {}
        for outs in edges[b].values():
            for d in outs.values():
                work+=1
                if work>MAX_WORK: raise LimitError('transition budget exceeded')
                if d not in seen:
                    seen.add(d)
                    if len(seen)>limit: raise LimitError('belief budget exceeded')
                    q.append(d)
    return roots,edges

def synthesize(m,limit=MAX_BELIEFS):
    roots,edges=graph(m,limit)
    # Least fixed point: guaranteed finite reachability of a safe goal, even
    # when the environment chooses any modeled outcome. No fairness assumed.
    ranks={b:0 for b in edges if m.goal(b) and m.safe(b)}
    # Reverse hyperedge worklist. Each action is winning only when ALL its
    # outcome beliefs have ranks. Heap pops in rank order for minimum horizon.
    import heapq
    back=defaultdict(list); pending={}; worst={}; heap=[(0,b) for b in ranks]; heapq.heapify(heap)
    for b,actions in edges.items():
        for a,outs in actions.items():
            k=(b,a); children=set(outs.values()); pending[k]=len(children); worst[k]=0
            for d in children: back[d].append(k)
    while heap:
        r,b=heapq.heappop(heap)
        for k in back[b]:
            pending[k]-=1; worst[k]=max(worst[k],r)
            if pending[k]==0:
                parent,a=k
                if parent not in ranks:
                    ranks[parent]=worst[k]+1; heapq.heappush(heap,(ranks[parent],parent))
    nodes=[]
    for b,actions in sorted(edges.items()):
        rank=ranks.get(b)
        permitted=[] if rank is None else [a for a,outs in actions.items() if all(d in ranks and ranks[d]<rank for d in outs.values())]
        nodes.append({'belief':list(b),'rank':rank,'actions':permitted})
    return {'format':1,'model_sha256':m.digest,'status':'WIN' if all(b in ranks for b in roots.values()) else 'NO_POLICY','nodes':nodes}

def verify(m,cert,limit=MAX_BELIEFS):
    # Check Bellman equations over full reachable graph, not solver history.
    # Positive ranks must descend. Null ranks must have no all-winning action.
    if not isinstance(cert,dict) or set(cert)!={'format','model_sha256','status','nodes'} or type(cert['format']) is not int or cert['format']!=1 or cert['model_sha256']!=m.digest: raise ModelError('certificate binding mismatch')
    roots,edges=graph(m,limit); entries={}
    if not isinstance(cert['nodes'],list) or len(cert['nodes'])!=len(edges): raise ModelError('certificate coverage mismatch')
    for n in cert['nodes']:
        if not isinstance(n,dict) or set(n)!={'belief','rank','actions'} or not isinstance(n['belief'],list) or any(not isinstance(s,str) for s in n['belief']) or not isinstance(n['actions'],list) or any(not isinstance(a,str) for a in n['actions']): raise ModelError('malformed certificate node')
        b=tuple(n['belief']); r=n['rank']
        if b not in edges or b in entries or (r is not None and (type(r) is not int or not 0<=r<=len(edges))): raise ModelError('invalid certificate node')
        entries[b]=n
    for b,actions in edges.items():
        n=entries[b]; r=n['rank']; options=[]
        for a,outs in actions.items():
            rs=[entries[d]['rank'] for d in outs.values()]
            if all(x is not None for x in rs): options.append((1+max(rs),a))
        expected=0 if m.safe(b) and m.goal(b) else min((v for v,a in options),default=None)
        if r!=expected: raise ModelError('incorrect rank at '+repr(b))
        allowed=sorted(a for v,a in options if r is not None and v<=r)
        if n['actions']!=allowed: raise ModelError('incorrect actions at '+repr(b))
    status='WIN' if all(entries[b]['rank'] is not None for b in roots.values()) else 'NO_POLICY'
    if cert['status']!=status: raise ModelError('incorrect status')
    return entries

class Session:
    """Fail-closed monitor for a verified model-bound policy. No network I/O."""
    def __init__(self,m,cert,observation):
        self.m=m; self.nodes=verify(m,cert); self.belief=m.partition(m.initial).get(observation); self.failed=False
        if self.belief is None or self.nodes[self.belief]['rank'] is None: raise ModelError('no winning initial belief')
    def allowed(self): return [] if self.failed else list(self.nodes[self.belief]['actions'])
    def step(self,action,observation):
        if self.failed: raise ModelError('session invalidated')
        if action not in self.allowed(): raise ModelError('action denied')
        target=self.m.outcomes(self.belief)[action].get(observation)
        if target is None: self.failed=True; raise ModelError('unexpected observation; session invalidated')
        self.belief=target
    @property
    def done(self): return not self.failed and self.nodes[self.belief]['rank']==0

def export_policy(m,cert,limit=MAX_BELIEFS):
    """Portable runtime transition table from a checked winning certificate."""
    entries=verify(m,cert,limit)
    if cert['status']!='WIN': raise ModelError('cannot export losing initial policy')
    ids={b:str(i) for i,b in enumerate(sorted(entries)) if entries[b]['rank'] is not None}
    nodes={}
    for b,i in ids.items():
        n=entries[b]; outcomes=m.outcomes(b) if n['actions'] else {}
        nodes[i]={'rank':n['rank'],'actions':{a:{o:ids[d] for o,d in outcomes[a].items()} for a in n['actions']}}
    return {'format':1,'model_sha256':m.digest,'initial':{o:ids[b] for o,b in m.partition(m.initial).items()},'nodes':nodes}
