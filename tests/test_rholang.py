import unittest
from rhoweave.rholang import compile_source
from rhoweave.engine import Model, ModelError, synthesize, verify, Session

def run(src, inputs, goals, forbidden):
    m = Model.parse(compile_source(src, inputs, goals, forbidden))
    c = synthesize(m); verify(m,c)
    return m,c

class RholangTests(unittest.TestCase):
    def test_pin_read(self):
        with open("examples/coherent-read.rho") as f:
            m,c=run(f.read(),["pin","read","unsafe_read"],["coherent"],["mixed"])
        self.assertEqual(c["status"],"WIN")
        obs=next(iter(m.partition(m.initial)))
        s=Session(m,c,obs)
        self.assertEqual(set(s.allowed()),{"pin","read"})
        for action in ("pin","read"):
            outcomes=m.outcomes(s.belief)[action]
            s.step(action,next(iter(outcomes)))
        self.assertTrue(s.done)

    def test_competing_receivers_explore_both(self):
        m,c=run('new x in { for (_ <- @"start") { x!(Nil) } | for (_ <- x) { @"ok"!(Nil) } | for (_ <- x) { @"bad"!(Nil) } }',["start"],["ok"],["bad"])
        b=next(iter(m.partition(m.initial).values()))
        self.assertEqual(len(m.outcomes(b)["start"]),2)
        self.assertEqual(c["status"],"NO_POLICY")

    def test_initial_race(self):
        m,c=run('new x in { x!(Nil) | for (_ <- x) { @"ok"!(Nil) } | for (_ <- x) { @"bad"!(Nil) } }',[],["ok"],["bad"])
        self.assertEqual(len(m.initial),2)
        self.assertEqual(c["status"],"NO_POLICY")

    def test_public_output_cannot_be_consumed(self):
        with self.assertRaises(ModelError):
            run('for (_ <- @"bad") { @"ok"!(Nil) }',[],["ok"],["bad"])

    def test_unsupported_syntax(self):
        for src in ('contract x(@v) = { Nil }','@"ok"!(42)','x!(Nil)','new x in { new y in { Nil } }','for (v <- @"start") { @"ok"!(Nil) }'):
            with self.subTest(src=src), self.assertRaises(ModelError):
                run(src,["start"],["ok"],[])

    def test_source_binding_and_determinism(self):
        src='for (_ <- @"go") { @"ok"!(Nil) }'
        a=compile_source(src,["go"],["ok"],[])
        self.assertEqual(a,compile_source(src,["go"],["ok"],[]))
        self.assertNotEqual(Model.parse(a).digest,Model.parse(compile_source(src+" // comment",["go"],["ok"],[])).digest)

    def test_one_shot_inputs(self):
        m,c=run('for (_ <- @"go") { for (_ <- @"go") { @"ok"!(Nil) } }',["go"],["ok"],[])
        self.assertEqual(c["status"],"NO_POLICY")

if __name__=="__main__":
    unittest.main()
