"""Reject stale/altered fixture evidence by reconstructing expected replies."""
from pathlib import Path
import json,hashlib
from rhoforge.compiler import compile_workflow
from probe_generated import cases,exhaustive,multiset
ROOT=Path(__file__).resolve().parents[1]
m,s=compile_workflow(json.loads((ROOT/'examples/escrow.json').read_text()))
e=json.loads((ROOT/'evidence/runtime.json').read_text())
expected={n:x for n,_,x in (*cases(m,s),*exhaustive(m,s))}
for path,key in [('rhoforge/compiler.py','forge_compiler_sha256'),('tools/probe_generated.py','probe_sha256')]:
    assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==e[key], 'stale source '+path
assert e['forge_spec_sha256']==m['spec_sha256'] and e['forge_source_sha256']==m['source_sha256']
assert e['passed'] and e['peer_count']==0 and e['block_height_before']==e['block_height_after']
assert len(e['fixtures'])==len(expected)==e['fixture_count']==131
seen=set(); runs=0
for i,row in enumerate(e['fixtures']):
    n=row['fixture']; assert n not in seen and n in expected;seen.add(n)
    assert row['passed'] and not row['errors'] and row['expected']==expected[n]
    assert len(row['observed'])==(e['repeats'] if i<5 else 1)
    assert all(multiset(x)==multiset(expected[n]) for x in row['observed']);runs+=len(row['observed'])
assert seen==set(expected) and runs==151
print('PASS: evidence source binding and 151 concrete reply multisets')
