import copy,json,unittest
from collections import deque
from pathlib import Path
from rhoforge.compiler import Actor,ForgeError,LimitError,MAX_EPOCH,compile_workflow
from rhoforge.__main__ import load
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/'examples/escrow.json').read_text())

class ForgeTests(unittest.TestCase):
    def setUp(self): self.m,self.s=compile_workflow(copy.deepcopy(SPEC))
    def test_compile_deterministic(self):
        self.assertEqual((self.m,self.s),compile_workflow(SPEC))
        self.assertEqual(len(self.m['markings']),9)
        self.assertEqual(self.m['primitive_edges'],12)
    def test_goal_synthesis_atomic(self):
        a=Actor(self.m)
        r=a.call('buyer','open',0)
        self.assertEqual(r,['OK',7,1,['fund','fund','fund','reserve']])
        self.assertEqual(self.m['markings'][7]['escrow'],3)
        self.assertEqual(a.call('seller','settle',1)[0],'OK')
        self.assertEqual(a.epoch,2)
        self.assertEqual(self.m['markings'][a.state]['seller'],3)
    def test_refund_from_partial_state(self):
        a=Actor(self.m);a.call('buyer','fund',0)
        r=a.call('buyer','refund',1)
        self.assertEqual(r[0],'OK');self.assertEqual(a.state,0);self.assertEqual(a.epoch,2)
    def test_wrong_role_and_stale(self):
        a=Actor(self.m);self.assertEqual(a.call('seller','open',0)[0],'DENIED')
        a.call('buyer','open',0);self.assertEqual(a.call('buyer','refund',0)[0],'STALE')
        self.assertEqual(a.call('buyer','release',1)[0],'DENIED')
        self.assertEqual(a.epoch,1)
    def test_already_no_commit(self):
        a=Actor(self.m);self.assertEqual(a.call('buyer','refund',0)[0],'ALREADY');self.assertEqual(a.epoch,0)
    def test_epoch_exhaustion(self):
        a=Actor(self.m);a.epoch=MAX_EPOCH;self.assertEqual(a.call('buyer','open',MAX_EPOCH)[0],'EXHAUSTED');self.assertEqual(a.state,0)
    def test_independent_instances(self):
        a,b=Actor(self.m),Actor(self.m);a.call('buyer','open',0);self.assertEqual(b.call('read','',0),['READ',0,0,[]])
    def test_conservation_all_states(self):
        for row in self.m['markings']:
            for inv in self.m['invariants'].values(): self.assertEqual(sum(row[k]*v for k,v in inv['weights'].items()),inv['value'])
            for k,v in row.items(): self.assertTrue(0<=v<=SPEC['places'][k]['capacity'])
    def test_reject_invariant_violation(self):
        x=copy.deepcopy(SPEC);x['transitions'][0]['produce']['escrow']=2
        with self.assertRaisesRegex(ForgeError,'violates invariant'):compile_workflow(x)
    def test_unknown_place_and_injection(self):
        for edit in ('unknown','injection','boolean'):
            x=copy.deepcopy(SPEC)
            if edit=='unknown':x['transitions'][0]['consume']['unknown']=1
            if edit=='injection':x['transitions'][0]['name']='x") | @"bad"!(1)'
            if edit=='boolean':x['places']['escrow']['initial']=False
            with self.assertRaises(ForgeError):compile_workflow(x)
    def test_capacity_and_unreachable_mission(self):
        x=copy.deepcopy(SPEC);x['missions'].append({'name':'steal','role':'buyer','goal':{'seller':3}})
        m,_=compile_workflow(x)
        self.assertNotIn('steal',m['actions']['buyer']['0'])
        self.assertEqual(Actor(m).call('buyer','steal',0)[0],'DENIED')
    def test_state_budget_no_partial_source(self):
        x={'name':'counter','places':{'x':{'capacity':1000,'initial':0}},'roles':['owner'],'transitions':[{'name':'inc','role':'owner','consume':{},'produce':{'x':1}}],'invariants':{},'missions':[]}
        with self.assertRaises(LimitError):compile_workflow(x)
    def test_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"name":1,"name":2}')
            with self.assertRaises(ForgeError):load(p)
    def test_every_mission_against_independent_forward_bfs(self):
        # Independent forward search on markings, not compiler's reverse graph.
        primitives={t['name']:t for t in SPEC['transitions']}
        for mission in SPEC['missions']:
            role=mission['role']; goal=mission['goal']; name=mission['name']
            for i,row in enumerate(self.m['markings']):
                def key(r):return tuple(r[k] for k in self.m['places'])
                q=deque([(row,[])]) ;seen={key(row)}; shortest=None
                while q:
                    state,plan=q.popleft()
                    if all(state[k]==v for k,v in goal.items()): shortest=plan;break
                    for n,t in sorted(primitives.items()):
                        if t['role']!=role or any(state[k]<v for k,v in t['consume'].items()):continue
                        child={k:v-t['consume'].get(k,0)+t['produce'].get(k,0) for k,v in state.items()}
                        if any(v>SPEC['places'][k]['capacity'] for k,v in child.items()) or key(child) in seen:continue
                        seen.add(key(child));q.append((child,plan+[n]))
                step=self.m['actions'][role][str(i)].get(name)
                if shortest is None:self.assertIsNone(step)
                else:
                    self.assertEqual(step['plan'],shortest)
                    self.assertTrue(all(self.m['markings'][step['target']][k]==v for k,v in goal.items()))

if __name__=='__main__':unittest.main()
