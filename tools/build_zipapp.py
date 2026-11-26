"""Build deterministic, dependency-free CLI artifact from the checked-out source."""
import argparse
import hashlib
from pathlib import Path
import zipfile
import tempfile
import os

ROOT=Path(__file__).resolve().parents[1]
ENTRY=b"""import sys
from rhoweave import __version__
if len(sys.argv)>1 and sys.argv[1]=="--version":
    print(__version__)
elif len(sys.argv)>1 and sys.argv[1]=="compile":
    del sys.argv[1]
    from rhoweave.rholang import main
    sys.exit(main())
elif len(sys.argv)>1 and sys.argv[1]=="audit":
    del sys.argv[1]
    from rhoweave.recovery import main
    sys.exit(main())
else:
    from rhoweave.__main__ import main
    sys.exit(main())
"""

def build(path):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        tmp=Path(f.name)
    try:
        with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_STORED) as z:
            entries={"__main__.py":ENTRY}
            entries.update({str(p.relative_to(ROOT)):p.read_bytes() for p in sorted((ROOT/"rhoweave").glob("*.py"))})
            for name,content in sorted(entries.items()):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
                info.create_system=3
                info.external_attr=0o100644<<16
                z.writestr(info,content)
        os.replace(tmp,path)
        return hashlib.sha256(path.read_bytes()).hexdigest()
    finally:
        tmp.unlink(missing_ok=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    if a.output.suffix!=".pyz": p.error("output must end in .pyz")
    print(build(a.output),a.output)
