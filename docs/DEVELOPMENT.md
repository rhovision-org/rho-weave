# Working on Weave

The graph and certificate checker live in `rhoweave/engine.py`. `rhoweave/machine.py` imports supported machine artifacts and emits the recovery controller. `rhoweave/anchor.py` checks the Observer envelope and a caller's by-hash read. The Python CLI is in `rhoweave/__main__.py`, and the portable JavaScript monitor and adapters are in `runtime/`.

Use Python 3.10 or newer. The offline tests cover the solver, certificate checks, supported artifact formats, generated controller structure and expected failure cases. Node.js runs the portable monitor examples.

```sh
python3 -m unittest discover -s tests -v
python3 -m rhoweave examples/quantum-os.json --export policy.json
node runtime/test.mjs policy.json
```

`examples/` holds the manual models and the reservation recovery objective. `tools/demo_recovery.py` reproduces the contract integration on native Rholo, including a capability denial and the Observer missing-finality case. `tools/rholo_probe.py` checks the separate fragment compiler on simulated inputs executed by native Rholo. [README recovery example](../README.md#finish-the-reservation) · [Native reproduction](RECOVERY.md) · [Fragment runtime guide](RUNTIME.md)

When proposing a model or compiler change, include a minimal input and the expected certificate result. Show how the model bounds observations and authority, and include a case that should defer or reject. Changes to generated Rholang should describe a native test case readers can reproduce. [Policy rules](POLICY.md) · [Security](../SECURITY.md) · [CI workflow](../.github/workflows/ci.yml)
