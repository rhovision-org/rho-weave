from copy import deepcopy
import unittest
from unittest.mock import patch

from rhoweave import engine
from rhoweave.anchor import anchored_read
from rhoweave.machine import compile_recovery


FORGE = {
    "schema": "rho-forge/partitioned-v1",
    "roles": ["clerk", "manager"],
    "lanes": {
        "free": {
            "places": ["free", "held", "issued"],
            "markings": [
                {"free": 1, "held": 0, "issued": 0},
                {"free": 0, "held": 1, "issued": 0},
                {"free": 0, "held": 0, "issued": 1},
            ],
            "actions": {
                "clerk": {
                    "0": {"reserve": {"target": 1, "plan": ["reserve"]}},
                    "1": {"issue": {"target": 2, "plan": ["issue"]}},
                    "2": {},
                },
                "manager": {"0": {}, "1": {}, "2": {}},
            },
        },
    },
}
OBJECTIVE = {
    "name": "recover_seats", "role": "clerk", "initial": [{"issued": 0}],
    "goal": {"issued": 1}, "avoid": [], "observe": ["held"], "operations": ["reserve", "issue"],
}


class MachineCompiler(unittest.TestCase):
    def test_recovery_derives_legal_action_for_each_possible_start(self):
        raw, cert, table, source = compile_recovery(FORGE, OBJECTIVE, lane="free")
        engine.verify(engine.Model.parse(raw), cert)
        self.assertEqual(cert["status"], "WIN")
        start = table["nodes"][table["initial"]["held=0"]]
        self.assertEqual(set(start["actions"]), {"reserve"})
        resumed = table["nodes"][table["initial"]["held=1"]]
        self.assertEqual(set(resumed["actions"]), {"issue"})
        self.assertIn('sendop!("issue", 2,', source)
        self.assertIn('revision == expected + 1', source)

    def test_blind_or_forbidden_observation_produces_no_controller(self):
        for change in ({"observe": []}, {"avoid": [{"held": 1}]}):
            _, cert, table, source = compile_recovery(FORGE, {**OBJECTIVE, **change}, "free")
            self.assertEqual(cert["status"], "NO_POLICY")
            self.assertIsNone(table)
            self.assertIsNone(source)

    def test_scope_and_manifest_validation(self):
        with self.assertRaisesRegex(engine.ModelError, "selected role"):
            compile_recovery(FORGE, {**OBJECTIVE, "role": "manager"}, "free")
        with self.assertRaisesRegex(engine.ModelError, "Forge lane"):
            compile_recovery(FORGE, OBJECTIVE)
        bad = deepcopy(FORGE)
        bad["lanes"]["free"]["actions"]["clerk"]["0"]["reserve"]["target"] = True
        with self.assertRaisesRegex(engine.ModelError, "rule target"):
            compile_recovery(bad, OBJECTIVE, "free")

    def test_foundry_uses_its_contract_abi(self):
        foundry = {
            "schema": 1, "resources": ["free", "held", "issued"], "roles": ["clerk"],
            "states": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "rules": [
                {"role": "clerk", "state": 0, "operation": "reserve", "target": 1},
                {"role": "clerk", "state": 1, "operation": "issue", "target": 2},
            ],
        }
        _, cert, _, source = compile_recovery(foundry, OBJECTIVE)
        self.assertEqual(cert["status"], "WIN")
        self.assertIn('writecap!("inspect", 0, *initial)', source)
        self.assertNotIn("viewcap", source)

    def test_prepare_reuses_one_graph_and_matches_independent_export(self):
        raw, cert, table, _ = compile_recovery(FORGE, OBJECTIVE, lane="free")
        model = engine.Model.parse(raw)
        with patch.object(engine, "graph", wraps=engine.graph) as counted:
            self.assertEqual(engine.prepare_policy(model, export=True), (cert, table))
        counted.assert_called_once()
        self.assertEqual(engine.export_policy(model, cert), table)


class AnchoredReads(unittest.TestCase):
    def setUp(self):
        self.evidence = {
            "schema": "rho-observer/read-anchor/v1", "status": "available",
            "evidence": "unanimous_reports", "snapshot_age_ms": 0, "stale_after_ms": 30_000,
            "observed_nodes": 2, "comparable_nodes": 2,
            "anchor": {"network_id": "test", "shard_id": "/root", "block_number": 8, "block_hash": "a" * 64},
        }

    def read(self, callback):
        return anchored_read(lambda: self.evidence, callback, network="test", shard="/root", max_age_ms=1000)

    def test_reads_only_the_given_block(self):
        anchor, value = self.read(lambda a: {**self.evidence["anchor"], "value": ["seat"]})
        self.assertEqual((anchor.block_hash, anchor.block_number, value), ("a" * 64, 8, ["seat"]))
        with self.assertRaisesRegex(engine.ModelError, "does not match"):
            self.read(lambda a: {**self.evidence["anchor"], "block_hash": "b" * 64, "value": []})

    def test_insufficient_stale_and_wrong_chain_never_read(self):
        for change in ({"comparable_nodes": 1}, {"snapshot_age_ms": 1000},
                       {"anchor": {**self.evidence["anchor"], "network_id": "other"}}):
            previous = self.evidence.copy()
            self.evidence.update(change)
            with self.assertRaises(engine.ModelError):
                self.read(lambda a: self.fail("read used inadmissible evidence"))
            self.evidence = previous

    def test_deadline_can_expire_during_the_read(self):
        with patch("rhoweave.anchor.monotonic_ns", side_effect=[0, 1, 1_000_000_000]):
            with self.assertRaisesRegex(engine.ModelError, "freshness expired"):
                self.read(lambda a: {**self.evidence["anchor"], "value": []})

    def test_freshness_budget_includes_rounding(self):
        self.evidence["snapshot_age_ms"] = 999
        with self.assertRaisesRegex(engine.ModelError, "freshness expired"):
            self.read(lambda a: self.fail("read used the sample's rounding margin"))
