import argparse,json,sys,os,tempfile
from pathlib import Path
from .engine import Model,ModelError,LimitError,Session,prepare_policy

MAX_ARTIFACT=64_000_000

def load(p,limit=4_000_000):
    with open(p,'rb') as f: data=f.read(limit+1)
    if len(data)>limit: raise LimitError('input exceeds byte budget')
    return parse_json(data)

def parse_json(data):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ModelError('duplicate JSON key')
            d[k]=v
        return d
    def invalid_constant(value):
        raise ModelError('non-finite JSON constant: '+value)
    return json.loads(data,object_pairs_hook=unique,parse_constant=invalid_constant)
def atomic_json(path,value,limit=MAX_ARTIFACT):
    path=Path(path)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",dir=path.parent,prefix=".weave-",delete=False) as f:
            tmp=Path(f.name); size=0
            for chunk in json.JSONEncoder(indent=2).iterencode(value):
                encoded=chunk.encode("utf-8"); size+=len(encoded)
                if size+1>limit: raise LimitError("output exceeds byte budget")
                f.write(encoded)
            f.write(b"\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if tmp is not None and tmp.exists(): tmp.unlink()

def main():
    p=argparse.ArgumentParser(description='Compile a finite protocol into an observation-safe policy')
    p.add_argument('model'); p.add_argument('--output'); p.add_argument('--export'); p.add_argument('--verify'); p.add_argument('--trace'); p.add_argument('--limit',type=int,default=10000)
    a=p.parse_args()
    try:
        if not 1<=a.limit<=10000: raise ModelError('limit must be 1..10000')
        inputs={Path(v).resolve() for v in (a.model,a.verify,a.trace) if v}
        outputs=[Path(v).resolve() for v in (a.output,a.export) if v]
        if len(set(outputs))!=len(outputs) or inputs.intersection(outputs): raise ModelError("output aliases another path")
        m=Model.parse(load(a.model))
        c, table = prepare_policy(
            m, load(a.verify,MAX_ARTIFACT) if a.verify else None, a.limit, export=bool(a.export)
        )
        if a.output: atomic_json(a.output,c)
        if a.export:
            if table is None:
                raise ModelError('cannot export losing initial policy')
            atomic_json(a.export,table)
        result={'status':c['status'],'beliefs':len(c['nodes']),'winning':sum(n['rank'] is not None for n in c['nodes']),'initial':[n for n in c['nodes'] if tuple(n['belief']) in m.partition(m.initial).values()]}
        if a.trace:
            t=load(a.trace)
            if not isinstance(t,dict) or set(t)!={'initial','steps'} or not isinstance(t['initial'],str) or not isinstance(t['steps'],list) or any(not isinstance(step,list) or len(step)!=2 or not all(isinstance(x,str) for x in step) for step in t['steps']): raise ModelError('invalid trace')
            s=Session(m,c,t['initial']); steps=[]
            for action,obs in t['steps']:
                steps.append({'allowed':s.allowed(),'action':action,'observed':obs}); s.step(action,obs)
            result['trace']={'steps':steps,'done':s.done,'allowed':s.allowed()}
        print(json.dumps(result,indent=2)); return 0 if c['status']=='WIN' else 1
    except (LimitError,RecursionError) as e: print(json.dumps({'status':'UNKNOWN','reason':str(e)}),file=sys.stderr); return 2
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'status':'ERROR','reason':str(e)}),file=sys.stderr); return 2
if __name__=='__main__': sys.exit(main())
