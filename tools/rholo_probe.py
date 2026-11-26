"""Differential check against a pinned rnode in a fresh loopback-only devnet.

Checks concrete closed-fragment observations against the compiler's allowed
set; sampled executions do not establish completeness or interpreter equivalence.
Never accepts an external node URL, signs a deploy, or attaches to a live chain.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
import uuid

from rhoweave import rholang, engine
from rhoweave.rholang import Parser, compile_source
from rhoweave.__main__ import atomic_json
from rhoweave.engine import Model, synthesize, verify

FIXTURES = {
    'single': '@"weave_ok"!(Nil)',
    'duplicate': '@"weave_ok"!(Nil) | @"weave_ok"!(Nil)',
    'private_comm': 'new x in { x!(Nil) | for (_ <- x) { @"weave_ok"!(Nil) } }',
    'atomic_join': 'new x,y in { x!(Nil) | y!(Nil) | for (_ <- x; _ <- y) { @"weave_ok"!(Nil) } }',
    'same_channel_join': 'new x in { x!(Nil) | x!(Nil) | for (_ <- x; _ <- x) { @"weave_ok"!(Nil) } }',
    'scoped_names': 'new x in { x!(Nil) | new x in { for (_ <- x) { @"weave_bad"!(Nil) } } | for (_ <- x) { @"weave_ok"!(Nil) } }',
    'deadlock': 'new x in { for (_ <- x) { @"weave_ok"!(Nil) } }',
    'competing_receivers': 'new x in { x!(Nil) | for (_ <- x) { @"weave_ok"!(Nil) } | for (_ <- x) { @"weave_bad"!(Nil) } }',
    'competing_join': 'new x,y in { x!(Nil) | y!(Nil) | for (_ <- x; _ <- y) { @"weave_ok"!(Nil) } | for (_ <- x) { @"weave_bad"!(Nil) } }',
    'both_outputs': '@"weave_ok"!(Nil) | @"weave_bad"!(Nil)',
}
OUTPUTS = ['weave_ok','weave_bad']

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for data in iter(lambda:f.read(1<<20),b''): h.update(data)
    return h.hexdigest()

def capture_term(source):
    parser=Parser(source,[],OUTPUTS); parser.parse()
    sends=Counter(c for op,c,_ in parser.instructions if op=='send')
    watchers=[]
    for name in OUTPUTS:
        for _ in range(sends['public:'+name]):
            watchers.append(f'for (_ <- @"{name}") {{ weaveResult!("{name}") }}')
    return 'new weaveResult in { '+ ' | '.join([source,'weaveResult!("weave_sentinel")',*watchers])+' }'

def decode(reply):
    if not isinstance(reply,dict) or reply.get('replySource')!='firstPrivateName' or not isinstance(reply.get('expr'),list):
        raise ValueError('not a private-name exploratory result: '+str(reply)[:240])
    values=[]
    for item in reply['expr']:
        if not isinstance(item,dict) or set(item)!={'ExprString'}: raise ValueError('unexpected expression type')
        value=item['ExprString']; value=value.get('data') if isinstance(value,dict) else value
        if value not in OUTPUTS+['weave_sentinel']: raise ValueError('unexpected expression value')
        values.append(value)
    if values.count('weave_sentinel')!=1: raise ValueError('sentinel missing or duplicated')
    return {name:values.count(name) for name in OUTPUTS}

def test_probes(request,repeats,anchor):
    rows=[]
    for name,source in FIXTURES.items():
        m=Model.parse(compile_source(source,[],['weave_ok'],['weave_bad']))
        c=synthesize(m); verify(m,c)
        expected=[json.loads(o) for o in sorted(m.partition(m.initial))]
        observed=[]; errors=[]
        for _ in range(repeats):
            try:
                reply=request('/api/explore-deploy',capture_term(source))
                if not isinstance(reply,dict) or not isinstance(reply.get('block'),dict) or reply['block'].get('blockHash')!=anchor:
                    raise ValueError('unexpected anchor or non-object response: '+str(reply)[:240])
                observed.append(decode(reply))
            except (ValueError,OSError,TypeError,KeyError) as e: errors.append(str(e)[:300])
        passed=not errors and len(observed)==repeats and all(o in expected for o in observed)
        rows.append({'fixture':name,'source':source,'model_status':c['status'],'expected':expected,'observed':observed,'errors':errors,'passed':passed})
    return rows

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect denied")

def fresh_ports():
    sockets=[]
    try:
        for _ in range(6):
            s=socket.socket(); s.bind(('127.0.0.1',0)); sockets.append(s)
        return [s.getsockname()[1] for s in sockets]
    finally:
        for s in sockets:s.close()

def run(binary,expected_hash,expected_commit,repeats):
    if sha(binary)!=expected_hash: raise ValueError('binary digest mismatch')
    if not re.fullmatch('[0-9a-f]{40}',expected_commit): raise ValueError('invalid commit')
    if not 1<=repeats<=10: raise ValueError('repeats must be 1..10')
    with tempfile.TemporaryDirectory(prefix='weave-rholo-') as d:
        d=Path(d); home=d/'home';home.mkdir()
        env={'PATH':os.defpath,'HOME':str(home)}
        version=subprocess.check_output([str(binary),'--version'],env=env,stderr=subprocess.DEVNULL,timeout=10,text=True).strip()
        if version!=f'rnode 0.1.0 ({expected_commit})':raise ValueError('binary revision mismatch: '+version)
        keypem=subprocess.check_output(['openssl','ecparam','-name','secp256k1','-genkey','-noout'],env=env,stderr=subprocess.DEVNULL,timeout=10)
        keytext=subprocess.check_output(['openssl','ec','-text','-noout'],input=keypem,env=env,stderr=subprocess.DEVNULL,timeout=10).decode()
        priv,pub=keytext.split('priv:',1)[1].split('pub:',1)
        priv=re.sub(r'[^a-fA-F0-9]','',priv);pub=re.sub(r'[^a-fA-F0-9]','',pub.split('ASN1 OID:',1)[0])
        if len(priv)!=64 or len(pub)!=130 or not pub.startswith('04'):raise ValueError('unexpected synthetic key format')
        key=d/'validator.hex';key.write_text(priv+'\n');key.chmod(0o600)
        bonds=d/'bonds.txt';bonds.write_text(pub+' 100\n');wallets=d/'wallets.txt';wallets.touch()
        port,disc,external,internal,http,admin=fresh_ports();network='weave-'+uuid.uuid4().hex
        args=[str(binary),'run','--standalone','--no-upnp','--dev-mode','--host','127.0.0.1','--api-host','127.0.0.1','--network-id',network,'--shard-name','weave-isolated','--data-dir',str(d/'data'),'--protocol-port',str(port),'--discovery-port',str(disc),'--api-port-grpc-external',str(external),'--api-port-grpc-internal',str(internal),'--api-port-http',str(http),'--api-port-admin-http',str(admin),'--thread-pool-size','2','--autogen-shard-size','1','--validator-private-key-path',str(key),'--validator-public-key',pub,'--bonds-file',str(bonds),'--wallets-file',str(wallets),'--allow-under-minimum','--accept-under-minimum-risk','--no-attest-on-new-blocks']
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        def request(path,body=None):
            req=urllib.request.Request(f'http://127.0.0.1:{http}'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with opener.open(req,timeout=5) as r:
                data=r.read(2_000_001)
            if len(data)>2_000_000: raise ValueError('oversize node response')
            return json.loads(data)
        with open(d/'node.log','wb') as log:
            proc=subprocess.Popen(args,env=env,cwd=d,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+20;status=None
                while time.monotonic()<deadline and proc.poll() is None:
                    try:
                        candidate=request('/api/status')
                        if isinstance(candidate,dict) and isinstance(candidate.get('checkpoint'),dict) and candidate['checkpoint'].get('anchor') and candidate.get('syncPhase')=='running':
                            status=candidate; break
                    except (ValueError,OSError): pass
                    time.sleep(.2)
                if status is None: raise ValueError('isolated node failed to become ready')
                if status.get('networkId')!=network or status.get('shardId')!='/weave-isolated' or status.get('peers')!=0 or status.get('devMode') is not True:raise ValueError('isolation status mismatch')
                anchor=status['checkpoint']['anchor']
                rows=test_probes(request,repeats,anchor)
                end=request('/api/status')
                if end.get('networkId')!=network or end.get('peers')!=0 or end.get('latestBlockNumber')!=status.get('latestBlockNumber') or end['checkpoint']['anchor']!=anchor:raise ValueError('chain changed during probe')
                return {'compiler_sha256':sha(Path(rholang.__file__)),'engine_sha256':sha(Path(engine.__file__)),'binary_sha256':expected_hash,'binary_commit':expected_commit,'runtime_version':version,'fixture_count':len(rows),'repeats':repeats,'peer_count':0,'block_height_before':status['latestBlockNumber'],'block_height_after':end['latestBlockNumber'],'passed':all(r['passed'] for r in rows),'fixtures':rows}
            finally:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('binary',type=Path);p.add_argument('--sha256',required=True);p.add_argument('--commit',required=True);p.add_argument('--repeats',type=int,default=3);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=run(a.binary.resolve(),a.sha256,a.commit,a.repeats)
    atomic_json(a.output,report)
    print(json.dumps({'passed':report['passed'],'fixtures':report['fixture_count'],'runs':report['fixture_count']*report['repeats']}))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
