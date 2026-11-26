import argparse,json,sys
from pathlib import Path
from .compiler import compile_workflow,ForgeError,LimitError,Actor

def load(path):
    def pairs(xs):
        out={}
        for k,v in xs:
            if k in out: raise ForgeError('duplicate key: '+k)
            out[k]=v
        return out
    with open(path,'rb') as f: b=f.read(262145)
    if len(b)>262144: raise LimitError('input byte limit')
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda v: (_ for _ in ()).throw(ForgeError('nonfinite value')))

def main():
    p=argparse.ArgumentParser(description='Compile bounded resource workflows to Rholang capability actors')
    p.add_argument('spec');p.add_argument('--out',type=Path,required=True,help='new directory (must not exist)');a=p.parse_args()
    try:
        m,s=compile_workflow(load(a.spec));a.out.mkdir(parents=False,exist_ok=False)
        (a.out/'factory.rho').write_text(s,encoding='utf-8');(a.out/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        print(json.dumps({'status':'COMPILED','states':len(m['markings']),'primitive_edges':m['primitive_edges'],'factory':m['factory'],'output':str(a.out)}));return 0
    except LimitError as e: print(json.dumps({'status':'UNKNOWN','reason':str(e)}),file=sys.stderr);return 2
    except (ValueError,OSError,TypeError,KeyError,RecursionError) as e: print(json.dumps({'status':'ERROR','reason':str(e)}),file=sys.stderr);return 2
if __name__=='__main__': raise SystemExit(main())
