import argparse,json,sys
from pathlib import Path
from .engine import Model,ModelError,LimitError,synthesize,verify,Session,export_policy

def load(p):
    with open(p,'rb') as f: data=f.read(4_000_001)
    if len(data)>4_000_000: raise LimitError('input exceeds 4 MB')
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ModelError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(data,object_pairs_hook=unique)
def main():
    p=argparse.ArgumentParser(description='Compile a finite protocol into an observation-safe policy')
    p.add_argument('model'); p.add_argument('--output'); p.add_argument('--export'); p.add_argument('--verify'); p.add_argument('--trace'); p.add_argument('--limit',type=int,default=10000)
    a=p.parse_args()
    try:
        if not 1<=a.limit<=10000: raise ModelError('limit must be 1..10000')
        m=Model.parse(load(a.model)); c=load(a.verify) if a.verify else synthesize(m,a.limit); verify(m,c,a.limit)
        if a.output: Path(a.output).write_text(json.dumps(c,indent=2)+'\n')
        if a.export: Path(a.export).write_text(json.dumps(export_policy(m,c,a.limit),indent=2)+'\n')
        result={'status':c['status'],'beliefs':len(c['nodes']),'winning':sum(n['rank'] is not None for n in c['nodes']),'initial':[n for n in c['nodes'] if tuple(n['belief']) in m.partition(m.initial).values()]}
        if a.trace:
            t=load(a.trace); s=Session(m,c,t['initial']); steps=[]
            for action,obs in t['steps']:
                steps.append({'allowed':s.allowed(),'action':action,'observed':obs}); s.step(action,obs)
            result['trace']={'steps':steps,'done':s.done,'allowed':s.allowed()}
        print(json.dumps(result,indent=2)); return 0 if c['status']=='WIN' else 1
    except (LimitError,RecursionError) as e: print(json.dumps({'status':'UNKNOWN','reason':str(e)}),file=sys.stderr); return 2
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'status':'ERROR','reason':str(e)}),file=sys.stderr); return 2
if __name__=='__main__': sys.exit(main())
