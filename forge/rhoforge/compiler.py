"""Bounded resource workflow compilation and atomic goal planning.

No source-language eval, arbitrary code execution, or network access.
"""
from collections import deque
import hashlib
import json
import re

MAX_STATES=128
MAX_EDGES=4096
MAX_SOURCE=512_000
MAX_EPOCH=2**63-2
NAME=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z')

class ForgeError(ValueError): pass
class LimitError(ForgeError): pass

def need(ok, msg):
    if not ok: raise ForgeError(msg)

def obj(v, fields, where):
    need(isinstance(v,dict) and set(v)==set(fields), f'{where}: expected fields {sorted(fields)}')
    return v

def name(v,where):
    need(isinstance(v,str) and NAME.fullmatch(v) is not None, f'{where}: invalid identifier')
    return v

def integer(v,lo,hi,where):
    need(type(v) is int and lo<=v<=hi, f'{where}: expected integer {lo}..{hi}')
    return v

def mapping(v,keys,lo,hi,where):
    need(isinstance(v,dict) and set(v)<=set(keys), f'{where}: unknown place or invalid map')
    return {k:integer(x,lo,hi,where+'.'+k) for k,x in v.items()}

def encode(v): return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'))

def compile_workflow(raw):
    obj(raw,['name','places','roles','transitions','invariants','missions'],'workflow')
    title=name(raw['name'],'name')
    places=raw['places']; need(isinstance(places,dict) and 1<=len(places)<=12,'places: expected 1..12')
    names=sorted(name(k,'place') for k in places)
    caps=[]; initial=[]
    for k in names:
        p=obj(places[k],['capacity','initial'],k)
        cap=integer(p['capacity'],1,1000,k+'.capacity'); caps.append(cap)
        initial.append(integer(p['initial'],0,cap,k+'.initial'))
    roles=raw['roles']; need(isinstance(roles,list) and 1<=len(roles)<=8,'roles: expected 1..8')
    roles=sorted(name(r,'role') for r in roles); need(len(set(roles))==len(roles),'duplicate role')
    need('read' not in roles,'read is reserved')
    ts=raw['transitions']; need(isinstance(ts,list) and 1<=len(ts)<=32,'transitions: expected 1..32')
    transitions={}
    for t in ts:
        obj(t,['name','role','consume','produce'],'transition')
        n=name(t['name'],'transition'); need(n not in transitions and t['role'] in roles,'duplicate transition or unknown role')
        c=mapping(t['consume'],names,1,1000,n+'.consume'); p=mapping(t['produce'],names,1,1000,n+'.produce')
        need(c or p,n+': empty transition')
        cc=tuple(c.get(k,0) for k in names); pp=tuple(p.get(k,0) for k in names)
        need(cc!=pp,n+': no state change')
        transitions[n]=(t['role'],cc,pp)
    invariants=raw['invariants']; need(isinstance(invariants,dict) and len(invariants)<=12,'invariants: expected 0..12')
    inv={}
    for k,w in sorted(invariants.items()):
        name(k,'invariant'); m=mapping(w,names,-1000,1000,k); weights=tuple(m.get(n,0) for n in names)
        need(any(weights),k+': zero invariant')
        total=sum(a*b for a,b in zip(initial,weights)); inv[k]={'weights':dict(zip(names,weights)),'value':total}
        for n,(_,c,p) in transitions.items():
            need(sum((b-a)*w for a,b,w in zip(c,p,weights))==0, f'{n} violates invariant {k}')
    missions=raw['missions']; need(isinstance(missions,list) and len(missions)<=16,'missions: expected 0..16')
    mission_defs={}
    for m in missions:
        obj(m,['name','role','goal'],'mission'); n=name(m['name'],'mission')
        need(n not in transitions and n not in mission_defs and m['role'] in roles,'duplicate action or unknown mission role')
        goal=mapping(m['goal'],names,0,1000,n+'.goal'); need(goal,'empty mission goal')
        need(all(v<=caps[names.index(k)] for k,v in goal.items()),'goal exceeds capacity')
        mission_defs[n]=(m['role'],goal)
    # Exhaustively enumerate the reachable bounded markings. Capacity is enforced before every edge.
    states=[tuple(initial)]; ids={states[0]:0}; edges={}; q=deque([0]); count=0
    while q:
        i=q.popleft(); s=states[i]; row={}; edges[i]=row
        for n,(_,c,p) in sorted(transitions.items()):
            if any(x<a for x,a in zip(s,c)): continue
            target=tuple(x-a+b for x,a,b in zip(s,c,p))
            if any(x>cap for x,cap in zip(target,caps)): continue
            if target not in ids:
                if len(states)>=MAX_STATES: raise LimitError('reachable state limit; no source emitted')
                ids[target]=len(states); states.append(target); q.append(ids[target])
            row[n]=ids[target]; count+=1
            if count>MAX_EDGES: raise LimitError('edge limit; no source emitted')
    # Reverse BFS derives shortest authorized paths for every starting marking.
    # Deterministic lexical tie-breaking. Mission is an atomic macro, not a series of external calls.
    actions={r:{str(i):{} for i in range(len(states))} for r in roles}
    for i,row in edges.items():
        for n,j in row.items(): actions[transitions[n][0]][str(i)][n]={'target':j,'plan':[n]}
    for n,(role,goal) in sorted(mission_defs.items()):
        goals={i for i,s in enumerate(states) if all(s[names.index(k)]==v for k,v in goal.items())}
        rev={i:[] for i in range(len(states))}
        for i,row in edges.items():
            for a,j in row.items():
                if transitions[a][0]==role: rev[j].append(i)
        d={i:0 for i in goals}; queue=deque(sorted(goals))
        while queue:
            j=queue.popleft()
            for i in rev[j]:
                if i not in d: d[i]=d[j]+1;queue.append(i)
        for i in sorted(d):
            j=i; plan=[]
            while d[j]:
                a,k=next((a,k) for a,k in sorted(edges[j].items()) if transitions[a][0]==role and d.get(k)==d[j]-1)
                plan.append(a);j=k
            actions[role][str(i)][n]={'target':j,'plan':plan}
    digest=hashlib.sha256(encode(raw).encode()).hexdigest()
    manifest={'schema':'rho-forge/v1','name':title,'spec_sha256':digest,'factory':'rhoForge_'+title+'_'+digest[:16], 'roles':roles,'places':names,'initial_state':0,'max_epoch':MAX_EPOCH,'markings':[dict(zip(names,s)) for s in states], 'actions':actions,'invariants':inv,'primitive_edges':count,'mission_goals':{n:{'role':r,'goal':g} for n,(r,g) in mission_defs.items()}}
    source=emit(manifest)
    if len(source.encode())>MAX_SOURCE: raise LimitError('generated source limit; no source emitted')
    manifest['source_sha256']=hashlib.sha256(source.encode()).hexdigest()
    return manifest,source

def emit(m):
    # All identifiers/literals generated from validated data. No interpolation of arbitrary code.
    # One private cell serializes requests; every branch puts the cell back exactly once.
    roles=m['roles']; channels=['cap'+str(i) for i in range(len(roles))]
    out=['// Rho Forge generated resource actor; spec sha256 '+m['spec_sha256'],
         'contract @'+encode(m['factory'])+'(ret) = {',
         '  new cell, view, '+', '.join(channels)+' in {',
         '    cell!(0, 0) |',
         '    contract view(reply) = { for (@s, @v <- cell) { cell!(s, v) | reply!(("READ", s, v, [])) } } |']
    for role,channel in zip(roles,channels):
        out += [f'    contract {channel}(@action, @expected, reply) = {{',
                '      for (@s, @v <- cell) {',
                '        if (expected == v) {',
                '          match (s, action) {']
        for i,row in m['actions'][role].items():
            for a,step in sorted(row.items()):
                j=step['target']; plan=encode(step['plan'])
                if not step['plan']:
                    body='cell!(s, v) | reply!(("ALREADY", s, v, []))'
                else:
                    body=f'if (v == {MAX_EPOCH}) {{ cell!(s, v) | reply!(("EXHAUSTED", s, v, [])) }} else {{ cell!({j}, v + 1) | reply!(("OK", {j}, v + 1, {plan})) }}'
                out.append(f'            ({i}, {encode(a)}) => {{ {body} }}')
        out += ['            _ => { cell!(s, v) | reply!(("DENIED", s, v, [])) }',
                '          }', '        } else { cell!(s, v) | reply!(("STALE", s, v, [])) }',
                '      }', '    } |']
    out += ['    ret!(*view, '+', '.join('*'+c for c in channels)+')','  }','}']
    return '\n'.join(out)+'\n'

class Actor:
    """Reference interpreter for generated actor, not a network runtime."""
    def __init__(self,manifest): self.m=manifest;self.state=0;self.epoch=0
    def call(self,role,action,expected):
        if role=='read': return ['READ',self.state,self.epoch,[]]
        if role not in self.m['roles']: raise ForgeError('no such role capability')
        if type(expected) is not int or expected!=self.epoch: return ['STALE',self.state,self.epoch,[]]
        step=self.m['actions'][role][str(self.state)].get(action)
        if not step: return ['DENIED',self.state,self.epoch,[]]
        if not step['plan']: return ['ALREADY',self.state,self.epoch,[]]
        if self.epoch==MAX_EPOCH: return ['EXHAUSTED',self.state,self.epoch,[]]
        self.state=step['target'];self.epoch+=1
        return ['OK',self.state,self.epoch,step['plan'][:]]
