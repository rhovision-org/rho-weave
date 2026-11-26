"""Read-only auditor for the finite Quantum OS decideRecovery switch table."""
import argparse
import hashlib
import json
import re
import sys
from .__main__ import load
from .engine import ModelError, Model, synthesize, verify

STATUSES = ("unknown", "prepared", "committed", "aborted")
ACTIONS = {"commit-both","commit-local","commit-remote","abort-local","abort-remote","noop","inconsistent"}
HEADER = re.compile(r'export\s+function\s+decideRecovery\s*\(\s*local\s*:\s*TxLegStatus\s*,\s*remote\s*:\s*TxLegStatus\s*\)\s*:\s*RecoveryAction\s*\{')
TOKEN = re.compile(r'\s+|"(?:[a-z-]+)"|[A-Za-z_][A-Za-z0-9_]*|[(){}:;]')

def extract(source):
    if len(source)>262144: raise ModelError("source too large")
    # The supported function contains only literal returns and nested switches.
    # No TypeScript execution, dynamic parsing, or arbitrary evaluation.
    clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    headers = list(HEADER.finditer(clean))
    if len(headers)!=1: raise ModelError("expected exactly one supported decideRecovery signature")
    start = headers[0].end()
    pos=start; depth=1; tokens=[]
    while depth:
        m=TOKEN.match(clean,pos)
        if not m: raise ModelError("unsupported recovery syntax")
        t=m.group(); pos=m.end()
        if t.isspace(): continue
        if t=="{": depth+=1
        elif t=="}": depth-=1
        tokens.append(t)
    i=0
    def take(w=None):
        nonlocal i
        if i>=len(tokens): raise ModelError("truncated recovery body")
        t=tokens[i]; i+=1
        if w is not None and t!=w: raise ModelError("expected "+w+", got "+t)
        return t
    def peek(): return tokens[i] if i<len(tokens) else None
    def ret():
        take("return"); literal=take(); take(";")
        if not literal.startswith('"') or not literal.endswith('"'): raise ModelError("expected literal action")
        a=literal[1:-1]
        if a not in ACTIONS: raise ModelError("unsupported recovery action")
        return a
    def case():
        take("case"); t=take(); take(":")
        if t not in ['"'+s+'"' for s in STATUSES]: raise ModelError("unsupported status")
        return t[1:-1]
    take("switch"); take("("); take("local"); take(")"); take("{")
    table={}
    while peek()=="case":
        l=case()
        if l in table: raise ModelError("duplicate local status")
        table[l]={}
        if peek()=="return":
            action=ret(); table[l]={r:action for r in STATUSES}
        else:
            take("switch"); take("("); take("remote"); take(")"); take("{")
            while peek()=="case":
                r=case()
                if r in table[l]: raise ModelError("duplicate remote status")
                table[l][r]=ret()
            take("}"); take("break"); take(";")
        if set(table[l])!=set(STATUSES): raise ModelError("incomplete remote cases")
    take("}"); fallback=ret(); take("}")
    if fallback!="inconsistent" or set(table)!=set(STATUSES) or i!=len(tokens):
        raise ModelError("unsupported fallback or incomplete table")
    return table

def audit(source, model):
    table=extract(source)
    m=Model.parse(model); c=synthesize(m); entries=verify(m,c)
    initial=m.partition(m.initial).get("unknown")
    if initial is None: raise ModelError("model lacks ambiguous initial observation")
    # Existing recovery model specifically represents a prepared local leg.
    # Compare the upstream actual recommendation with the synthesized policy.
    action=table["prepared"]["unknown"]
    allowed=entries[initial]["actions"]
    unsafe=[]
    for s in initial:
        for d in m.edges.get(s,{}).get(action,()):
            if not m.states[d]["safe"]: unsafe.append({"state":s,"target":d})
    return {"source_sha256":hashlib.sha256(source.encode()).hexdigest(),"model_sha256":m.digest,
            "table":table,"checked_pairs":16,"upstream_action":action,
            "permitted_actions":allowed,"model_counterexamples":unsafe,
            "status":"MODEL_CONFLICT" if unsafe else "NO_MODELED_CONFLICT"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source"); p.add_argument("model")
    a=p.parse_args()
    try:
        with open(a.source,encoding="utf-8") as f: source=f.read(262145)
        model=load(a.model)
        print(json.dumps(audit(source,model),indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({"status":"ERROR","reason":str(e)}),file=sys.stderr); return 2
if __name__=="__main__": sys.exit(main())
