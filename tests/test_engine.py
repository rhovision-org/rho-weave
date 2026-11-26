import copy,json,random,unittest
from pathlib import Path
from rhoweave.engine import Model,ModelError,LimitError,Session,graph,synthesize,verify
BASE=Path(__file__).resolve().parents[1]/'examples'
def model(n): return Model.parse(json.loads((BASE/(n+'.json')).read_text()))
class Tests(unittest.TestCase):
    def test_gov(self):
        m=model('rhogov'); c=synthesize(m); s=Session(m,c,'start'); self.assertEqual(s.allowed(),['pin-finalized']); s.step('pin-finalized','pinned'); s.step('read-at-pin','coherent'); self.assertTrue(s.done)
    def test_qos(self):
        m=model('quantum-os'); c=synthesize(m); s=Session(m,c,'unknown'); self.assertEqual(s.allowed(),['refresh']); s.step('refresh','committed'); self.assertEqual(s.allowed(),['commit-local']); s.step('commit-local','decision'); self.assertTrue(s.done)
    def test_timeout(self):
        m=model('quantum-os'); s=Session(m,synthesize(m),'unknown'); s.step('refresh','retry-exhausted'); s.step('defer','deferred'); self.assertTrue(s.done)
    def test_partition(self):
        m=model('partition'); c=synthesize(m); self.assertEqual(c['status'],'NO_POLICY'); verify(m,c)
    def test_denied(self):
        m=model('rhogov'); s=Session(m,synthesize(m),'start'); self.assertRaises(ModelError,s.step,'read-latest','mixed')
    def test_unexpected(self):
        m=model('rhogov'); s=Session(m,synthesize(m),'start'); self.assertRaises(ModelError,s.step,'pin-finalized','bogus'); self.assertEqual(s.allowed(),[]); self.assertFalse(s.done)
    def test_tamper(self):
        m=model('rhogov'); c=synthesize(m); c['nodes'][0]['rank']=999; self.assertRaises(ModelError,verify,m,c)
    def test_binding(self):
        self.assertRaises(ModelError,verify,model('quantum-os'),synthesize(model('rhogov')))
    def test_coverage(self):
        m=model('rhogov'); c=synthesize(m); c['nodes'].pop(); self.assertRaises(ModelError,verify,m,c)
    def test_limit(self): self.assertRaises(LimitError,synthesize,model('rhogov'),1)
    def test_random_against_synchronous_reference(self):
        rng=random.Random(72)
        for trial in range(300):
            states={str(i):{'observation':str(rng.randrange(3)),'safe':True,'goal':False} for i in range(5)}
            states['4'].update(observation='goal',goal=True); states['3'].update(safe=False)
            edges=[[str(i),a,str(j)] for i in range(4) for a in ('a','b','c') for j in range(5) if rng.random()<.18]
            m=Model.parse({'name':str(trial),'states':states,'initial':['0','1'],'transitions':edges}); _,g=graph(m)
            ref={b:0 for b in g if m.goal(b)}
            while True:
                new={b:1+min(max(ref[d] for d in o.values()) for o in acts.values() if all(d in ref for d in o.values())) for b,acts in g.items() if b not in ref and any(all(d in ref for d in o.values()) for o in acts.values())}
                if not new: break
                ref.update(new)
            c=synthesize(m); verify(m,c); self.assertEqual({tuple(n['belief']):n['rank'] for n in c['nodes'] if n['rank'] is not None},ref)
    def test_all_policy_paths_terminate(self):
        for name in ('rhogov','quantum-os'):
            m=model(name); c=synthesize(m); entries=verify(m,c)
            for b,n in entries.items():
                for a in n['actions']:
                    for d in m.outcomes(b)[a].values(): self.assertLess(entries[d]['rank'],n['rank']); self.assertTrue(m.safe(d))
    def test_missing_action_in_hidden_state(self):
        m=Model.parse({'name':'partial','states':{'a':{'observation':'x','safe':True,'goal':False},'b':{'observation':'x','safe':True,'goal':False},'g':{'observation':'g','safe':True,'goal':True}},'initial':['a','b'],'transitions':[['a','go','g']]}); self.assertEqual(synthesize(m)['status'],'NO_POLICY')
if __name__=='__main__': unittest.main()
