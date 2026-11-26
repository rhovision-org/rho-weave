import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tools.build_zipapp import build
from rhoweave import __version__

class PackageTests(unittest.TestCase):
    def test_reproducible_zipapp_and_detached_cli(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); a=d/"a.pyz"; b=d/"b.pyz"
            self.assertEqual(build(a),build(b))
            self.assertEqual(a.read_bytes(),b.read_bytes())
            version=subprocess.check_output([sys.executable,str(a),"--version"],cwd=d,text=True)
            self.assertEqual(version.strip(),__version__)
            model=Path("examples/rhogov.json").resolve()
            result=subprocess.run([sys.executable,str(a),str(model)],cwd=d,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('"status": "WIN"',result.stdout)
            source=Path("examples/coherent-read.rho").resolve()
            result=subprocess.run([sys.executable,str(a),"compile",str(source),"--input","pin","--input","read","--input","unsafe_read","--goal","coherent","--forbid","mixed","--output",str(d/"model.json")],cwd=d,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((d/"model.json").exists())
