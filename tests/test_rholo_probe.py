import json
from pathlib import Path
import unittest
from tools import rholo_probe as probe
from rhoweave import rholang, engine

class RuntimeProbeTests(unittest.TestCase):
    def test_capture_and_decode(self):
        term=probe.capture_term(probe.FIXTURES['duplicate'])
        self.assertEqual(term.count('for (_ <- @"weave_ok")'),2)
        reply={'replySource':'firstPrivateName','expr':[{'ExprString':{'data':v}} for v in ['weave_sentinel','weave_ok','weave_ok']]}
        self.assertEqual(probe.decode(reply),{'weave_ok':2,'weave_bad':0})
        reply['expr'].pop(0)
        with self.assertRaises(ValueError):probe.decode(reply)

    def test_model_mismatch_fails(self):
        def fake(path,term):
            return {'replySource':'firstPrivateName','block':{'blockHash':'x'},'expr':[{'ExprString':{'data':'weave_sentinel'}}]}
        rows=probe.test_probes(fake,1,'x')
        self.assertFalse(next(r for r in rows if r['fixture']=='single')['passed'])
        self.assertTrue(next(r for r in rows if r['fixture']=='deadlock')['passed'])

    def test_redirect_denied(self):
        with self.assertRaises(ValueError):probe.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')

    def test_historical_runtime_replies_match_current_model(self):
        report=json.loads(Path('evidence/rholo-runtime-probes.json').read_text())
        self.assertEqual(report['compiler_sha256'],probe.sha(Path(rholang.__file__)))
        # Keep the engine binding of the original native run at 3807799.
        self.assertEqual(report['engine_sha256'],'5a63d4e17a419a7bfdb4fb5bb2442183476705939e3301f16ac8e1bbe0752af2')
        self.assertEqual(report['binary_commit'],'e63b7e5a8ccfcc25ff64860ac989d95a748eaaca')
        self.assertEqual(report['peer_count'],0)
        self.assertEqual(report['block_height_before'],report['block_height_after'])
        self.assertEqual(report['fixture_count'],len(probe.FIXTURES))
        self.assertTrue(report['passed'])
        self.assertEqual(set(probe.FIXTURES),{row['fixture'] for row in report['fixtures']})
        for row in report['fixtures']:
            source=probe.FIXTURES[row['fixture']]
            m=engine.Model.parse(rholang.compile_source(source,[],['weave_ok'],['weave_bad']))
            self.assertEqual(row['source'],source)
            self.assertEqual(row['expected'],[json.loads(o) for o in sorted(m.partition(m.initial))])
            self.assertTrue(row['passed']);self.assertFalse(row['errors'])
            self.assertEqual(len(row['observed']),report['repeats'])
            self.assertTrue(all(v in row['expected'] for v in row['observed']))
