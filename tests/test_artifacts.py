import json
import tempfile
import unittest
from pathlib import Path
from rhoweave.__main__ import atomic_json,load
from rhoweave.engine import LimitError

class ArtifactTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"policy.json"
            atomic_json(p,{"test":[1,2]})
            self.assertEqual(load(p),{"test":[1,2]})

    def test_output_budget_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"policy.json"
            p.write_text("old")
            with self.assertRaises(LimitError):
                atomic_json(p,{"test":"x"*100},limit=32)
            self.assertEqual(p.read_text(),"old")
            self.assertEqual(list(Path(d).iterdir()),[p])
