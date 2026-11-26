"""Run compiled actors on a pinned, isolated Rholo executable.

Uses the adjacent Rho Weave tools/rholo_probe.py only for devnet lifecycle.
No deployed network, signing, or upstream mutation.
"""
import argparse
from collections import Counter,deque
import hashlib
import json
from pathlib import Path
import sys

from rhoforge.compiler import Actor,compile_workflow

ROOT=Path(__file__).resolve().parents[1]

def decode(expr):
    if not isinstance(expr,dict) or len(expr)!=1: raise ValueError('invalid expression')
    typ,data=next(iter(expr.items()))
    if not isinstance(data,dict) or 'data' not in data: raise ValueError('invalid expression payload')
    v=data['data']
    if typ=='ExprString' and isinstance(v,str): return v
    if typ=='ExprInt' and type(v) is int: return v
    if typ in ('ExprTuple','ExprList') and isinstance(v,list): return [decode(x) for x in v]
    raise ValueError('unexpected expression type '+typ)

def multiset(xs): return Counter(json.dumps(x,separators=(',',':')) for x in xs)

def sequential(m,source,operations):
    # Every next request waits for the prior response; results are emitted to
    # the first private name in a single exploratory deploy.
    a=Actor(m); expected=[]; body='Nil'
    role_names={'read':'view',**{r:'role'+str(i) for i,r in enumerate(m['roles'])}}
    for role,action,version in operations: expected.append(a.call(role,action,version))
    for i,(role,action,version) in reversed(list(enumerate(operations))):
        call=f'{role_names[role]}!(*r{i})' if role=='read' else f'{role_names[role]}!({json.dumps(action)}, {version}, *r{i})'
        body=f'new r{i} in {{ {call} | for (@x{i} <- r{i}) {{ result!(x{i}) | {body} }} }}'
    caps=', '.join(role_names.values())
    term=f'new result, ready in {{ {source} | @"{m["factory"]}"!(*ready) | for ({caps} <- ready) {{ {body} }} }}'
    return term,expected

def race(m,source):
    # Two conflicting calls with the same expected revision: exactly one may commit.
    actor=Actor(m);first=actor.call('buyer','open',0);second=actor.call('buyer','open',0);last=actor.call('read','',0)
    term=f'''new result, ready in {{ {source} | @"{m['factory']}"!(*ready) |
      for (view,buyer,seller <- ready) {{ new a,b,c in {{
        buyer!("open",0,*a) | buyer!("open",0,*b) |
        for (@x <- a; @y <- b) {{ result!(x) | result!(y) | view!(*c) | for (@z <- c) {{ result!(z) }} }}
      }} }} }}'''
    return term,[first,second,last]

def isolated_instances(m,source):
    a=Actor(m); b=Actor(m);expected=[a.call('buyer','open',0),b.call('read','',0)]
    term=f'''new result, ra, rb in {{ {source} | @"{m['factory']}"!(*ra) | @"{m['factory']}"!(*rb) |
      for (va,ba,sa <- ra; vb,bb,sb <- rb) {{ new a,b in {{
        ba!("open",0,*a) | vb!(*b) | for (@x <- a; @y <- b) {{ result!(x) | result!(y) }}
      }} }} }}'''
    return term,expected

def cases(m,source):
    yield 'goal_open_and_settle',*sequential(m,source,[('read','',0),('buyer','open',0),('buyer','release',1),('seller','settle',1),('read','',2),('seller','settle',2)])
    yield 'goal_refund',*sequential(m,source,[('buyer','fund',0),('buyer','refund',1),('read','',2)])
    yield 'stale_and_disabled',*sequential(m,source,[('seller','settle',0),('buyer','open',0),('buyer','refund',0),('buyer','refund',1),('read','',2)])
    yield 'same_revision_race',*race(m,source)
    yield 'independent_instances',*isolated_instances(m,source)

def exhaustive(m,source):
    # Reach each marking using primitive transitions, then exercise every
    # action name under each role capability, including all denied pairs.
    paths={0:[]}; q=deque([0]); names=set()
    for role,rows in m['actions'].items():
        for row in rows.values(): names.update(row)
    while q:
        i=q.popleft()
        for role,rows in m['actions'].items():
            for action,step in rows[str(i)].items():
                if step['plan']!=[action]: continue
                j=step['target']
                if j not in paths:
                    paths[j]=paths[i]+[(role,action,len(paths[i]))];q.append(j)
    if len(paths)!=len(m['markings']): raise ValueError('unreachable manifest marking')
    for i,path in sorted(paths.items()):
        for role in m['roles']:
            for action in sorted(names):
                yield f'state_{i}_{role}_{action}',*sequential(m,source,path+[(role,action,len(path)),('read','',0)])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--weave-root',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--commit',required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    sys.path.insert(0,str(a.weave_root.resolve()))
    from tools import rholo_probe as harness
    m,source=compile_workflow(json.loads((ROOT/'examples/escrow.json').read_text()))
    def probe(request,repeats,anchor):
        rows=[]
        for index,(name,term,expected) in enumerate((*cases(m,source),*exhaustive(m,source))):
            observed=[]; errors=[]
            for _ in range(repeats if index<5 else 1):
                try:
                    reply=request('/api/explore-deploy-by-block-hash',{'term':term,'blockHash':anchor,'usePreStateHash':False})
                    if reply.get('replySource')!='firstPrivateName' or reply.get('block',{}).get('blockHash')!=anchor: raise ValueError('unexpected reply or anchor')
                    got=[decode(x) for x in reply['expr']]; observed.append(got)
                    if multiset(got)!=multiset(expected): errors.append('concrete result differs from reference')
                except (ValueError,OSError,TypeError,KeyError) as e: errors.append(str(e)[:400])
            rows.append({'fixture':name,'expected':expected,'observed':observed,'errors':errors,'passed':not errors and len(observed)==(repeats if index<5 else 1)})
        return rows
    harness.test_probes=probe
    report=harness.run(a.binary.resolve(),a.sha256,a.commit,a.repeats)
    report.update({'forge_spec_sha256':m['spec_sha256'],'forge_source_sha256':m['source_sha256'],'forge_compiler_sha256':hashlib.sha256((ROOT/'rhoforge/compiler.py').read_bytes()).hexdigest(),'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'fixtures':report['fixture_count'],'runs':sum(len(r['observed']) for r in report['fixtures']),'errors':[(r['fixture'],r['errors']) for r in report['fixtures'] if r['errors']]}))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
