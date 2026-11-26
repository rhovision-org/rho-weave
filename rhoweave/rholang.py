"""Closed, recursion-free Rholang fragment -> exact finite observation game.

Public names are literal strings (@"name"); private names use lexically scoped new. Every send carries Nil; receivers discard it.
Join receives are atomic. Public inputs have explicit finite injection budgets
and occur only at quiescence.
"""
import argparse
import hashlib
from collections import deque, Counter
import json
from pathlib import Path
import re
import sys
from .__main__ import atomic_json
from .engine import Model, ModelError, LimitError, synthesize, verify, MAX_STATES, MAX_EDGES

TOKEN = re.compile(r'\s+|//[^\n]*|@"[A-Za-z_][A-Za-z0-9_]*"|[A-Za-z_][A-Za-z0-9_]*|<-|[!(){},|;]')
MAX_REDUCTIONS = 100000

class Parser:
    def __init__(self, source, inputs, outputs):
        if len(source) > 65536:
            raise LimitError("source too large")
        self.tokens = []
        pos = 0
        while pos < len(source):
            m = TOKEN.match(source, pos)
            if not m:
                raise ModelError("unsupported token at offset " + str(pos))
            t = m.group()
            if not t.isspace() and not t.startswith("//"):
                self.tokens.append(t)
            pos = m.end()
        self.i = 0
        self.private = {}
        self.next_private = 0
        self.inputs, self.outputs = set(inputs), set(outputs)
        self.instructions = []

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, wanted=None):
        t = self.peek()
        if t is None or (wanted is not None and t != wanted):
            raise ModelError("expected " + str(wanted) + ", got " + str(t))
        self.i += 1
        return t

    def channel(self, sending):
        t = self.take()
        if t.startswith('@"'):
            n = t[2:-1]
            if n not in (self.outputs if sending else self.inputs):
                raise ModelError("public channel direction or declaration mismatch: " + n)
            return "public:" + n
        if t not in self.private:
            raise ModelError("unbound private channel: " + t)
        return self.private[t]

    def process(self, depth=0):
        if depth > 64:
            raise LimitError("nesting budget exceeded")
        out = []
        while True:
            t = self.peek()
            if t == "Nil":
                self.take()
            elif t == "new":
                self.take()
                previous = self.private.copy()
                declared = set()
                while True:
                    n = self.take()
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n) or n in {"new","in","for","Nil","_"} or n in declared:
                        raise ModelError("invalid private binder")
                    declared.add(n)
                    self.private[n] = "private:" + str(self.next_private)
                    self.next_private += 1
                    if self.next_private > 128:
                        raise LimitError("private binder budget exceeded")
                    if self.peek() != ",":
                        break
                    self.take(",")
                self.take("in"); self.take("{")
                out.extend(self.process(depth + 1))
                self.take("}")
                self.private = previous
            elif t == "for":
                self.take(); self.take("(")
                channels = []
                while True:
                    self.take("_"); self.take("<-")
                    channels.append(self.channel(False))
                    if len(channels)>32:
                        raise LimitError("join width exceeded")
                    if self.peek() != ";":
                        break
                    self.take(";")
                self.take(")"); self.take("{")
                body = self.process(depth + 1)
                self.take("}")
                out.append(len(self.instructions))
                self.instructions.append(("recv", tuple(channels), tuple(body)))
            else:
                c = self.channel(True)
                self.take("!"); self.take("("); self.take("Nil"); self.take(")")
                out.append(len(self.instructions))
                self.instructions.append(("send", c, ()))
            if len(self.instructions) > 128:
                raise LimitError("instruction budget exceeded")
            if self.peek() != "|":
                return out
            self.take("|")

    def parse(self):
        root = self.process()
        if self.peek() is not None:
            raise ModelError("unexpected trailing syntax")
        return root

def compile_source(source, inputs, goals, forbidden, input_budgets=None):
    if any(not isinstance(v, (list, tuple)) for v in (inputs, goals, forbidden)):
        raise ModelError("interfaces must be lists")
    names = list(inputs) + list(goals) + list(forbidden)
    if not goals or len(names) > 32 or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', n) for n in names) or len(set(names)) != len(names):
        raise ModelError("invalid or overlapping public interface")
    if input_budgets is None:
        input_budgets = {n:1 for n in inputs}
    if not isinstance(input_budgets,dict) or set(input_budgets)!=set(inputs) or any(type(v) is not int or not 1<=v<=16 for v in input_budgets.values()) or sum(input_budgets.values())>64:
        raise ModelError("input budgets must cover declared inputs, 1..16 each, total <=64")
    p = Parser(source, inputs, list(goals) + list(forbidden))
    root = p.parse()
    ins = p.instructions
    output = set(goals) | set(forbidden)
    work = 0

    # State = pending receives, multiset of messages, multiset of injected inputs.
    def activate(wait, msgs, ids):
        wait, msgs = list(wait), list(msgs)
        for i in ids:
            op, c, _ = ins[i]
            (msgs if op == "send" else wait).append(c if op == "send" else i)
        return tuple(sorted(wait)), tuple(sorted(msgs))

    def closure(wait, msgs):
        nonlocal work
        first = (wait, msgs)
        q = [first]; seen = {first}; terminal = set()
        while q:
            w, m = q.pop()
            enabled = False
            available=Counter(m)
            for i in sorted(set(w)):
                _, channels, body = ins[i]
                if any(available[c]<n for c,n in Counter(channels).items()):
                    continue
                enabled = True
                ww, mm = list(w), list(m)
                ww.remove(i)
                for c in channels:
                    mm.remove(c)
                child = activate(ww, mm, body)
                work += 1
                if work > MAX_REDUCTIONS:
                    raise LimitError("reduction budget exceeded")
                if child not in seen:
                    seen.add(child); q.append(child)
            if not enabled:
                terminal.add((w, m))
        return sorted(terminal)

    def label(state):
        _, msgs, _ = state
        counts = {n: msgs.count("public:" + n) for n in sorted(output)}
        safe = not any(counts[n] for n in forbidden)
        goal = safe and all(counts[n] for n in goals)
        return {"observation": json.dumps(counts, sort_keys=True, separators=(",", ":")), "safe": safe, "goal": goal}

    ids = {}; states = {}; transitions = []; queue = deque()
    def add(s):
        if s not in ids:
            if len(ids) >= MAX_STATES:
                raise LimitError("compiled state budget exceeded")
            k = str(len(ids)); ids[s] = k; states[k] = label(s); queue.append(s)
        return ids[s]

    w, m = activate([], [], root)
    initial = [add((a,b,())) for a,b in closure(w,m)]
    while queue:
        s = queue.popleft(); w,m,used = s; k = ids[s]
        if not states[k]["safe"] or states[k]["goal"]:
            continue
        for n in sorted(n for n in inputs if used.count(n)<input_budgets[n]):
            next_used = tuple(sorted((*used,n)))
            for ww,mm in closure(w,tuple(sorted((*m,"public:"+n)))):
                transitions.append([k,n,add((ww,mm,next_used))])
                if len(transitions)>MAX_EDGES:
                    raise LimitError("compiled transition budget exceeded")
    raw = {"name":"Compiled finite Rholang fragment sha256:"+hashlib.sha256(source.encode()).hexdigest(),"states":states,"initial":initial,"transitions":transitions}
    Model.parse(raw)
    return raw

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source"); p.add_argument("--input",action="append",default=[])
    p.add_argument("--goal",action="append",required=True)
    p.add_argument("--budget",action="append",default=[],metavar="INPUT=COUNT")
    p.add_argument("--forbid",action="append",default=[])
    p.add_argument("--output",required=True)
    a = p.parse_args()
    try:
        if Path(a.source).resolve()==Path(a.output).resolve(): raise ModelError("output aliases source")
        with open(a.source,"r",encoding="utf-8") as f:
            budgets={n:1 for n in a.input}
            for item in a.budget:
                n,sep,count=item.partition("=")
                if not sep or n not in budgets: raise ModelError("invalid input budget")
                budgets[n]=int(count)
            raw = compile_source(f.read(65537),a.input,a.goal,a.forbid,budgets)
        model = Model.parse(raw); cert = synthesize(model); verify(model,cert)
        atomic_json(a.output,raw,limit=4_000_000)
        print(json.dumps({"status":cert["status"],"states":len(raw["states"]),"transitions":len(raw["transitions"])}))
        return 0 if cert["status"]=="WIN" else 1
    except (LimitError,RecursionError) as e:
        print(json.dumps({"status":"UNKNOWN","reason":str(e)}),file=sys.stderr); return 2
    except (OSError,ValueError,TypeError) as e:
        print(json.dumps({"status":"ERROR","reason":str(e)}),file=sys.stderr); return 2

if __name__=="__main__":
    sys.exit(main())
