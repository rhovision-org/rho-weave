import json
import unittest
from rhoweave.recovery import extract,audit,STATUSES
from rhoweave.engine import ModelError

def fixture():
    actions={
        "unknown": ["noop"]*4,
        "prepared": ["abort-local","commit-both","commit-local","abort-local"],
        "committed": ["inconsistent","commit-remote","noop","inconsistent"],
        "aborted": ["noop","abort-remote","inconsistent","noop"],
    }
    body=['export function decideRecovery(local: TxLegStatus, remote: TxLegStatus): RecoveryAction { switch(local) {']
    for l in STATUSES:
        body.append('case "'+l+'":')
        if l=="unknown":
            body.append('return "noop";')
        else:
            body.append('switch(remote){')
            for r,a in zip(STATUSES,actions[l]):
                body.append('case "'+r+'": return "'+a+'";')
            body.append('} break;')
    body.append('} return "inconsistent"; }')
    return "\n".join(body),{l:dict(zip(STATUSES,actions[l])) for l in STATUSES}

class RecoveryTests(unittest.TestCase):
    def test_literal_table(self):
        src,table=fixture()
        self.assertEqual(extract(src),table)

    def test_reject_nonliteral(self):
        src,_=fixture()
        with self.assertRaises(ModelError):
            extract(src.replace('return "noop";','return noop;',1))

    def test_reject_missing_case(self):
        src,_=fixture()
        with self.assertRaises(ModelError):
            extract(src.replace('case "unknown": return "abort-local";','',1))

    def test_model_conflict(self):
        src,_=fixture()
        with open("examples/quantum-os.json") as f: model=json.load(f)
        result=audit(src,model)
        self.assertEqual(result["checked_pairs"],16)
        self.assertEqual(result["upstream_action"],"abort-local")
        self.assertEqual(result["permitted_actions"],["refresh"])
        self.assertEqual(result["status"],"MODEL_CONFLICT")
        self.assertEqual(len(result["model_counterexamples"]),2)

if __name__=="__main__": unittest.main()
