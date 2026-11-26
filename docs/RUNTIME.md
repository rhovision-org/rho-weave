# Real Rholo differential execution

## Reproduction

Obtain the x86-64 Linux rnode executable from Rholo CI run 45517240553 (commit e63b7e5a8ccfcc25ff64860ac989d95a748eaaca, artifact 14977847392). The archive SHA-256 is f2ecced8a2b085183654828e1061f67469b95e225f1ae8ce022ea8fd9a5167e1. Verify the binary against the digest below. Requires Python and OpenSSL, a compatible Linux environment, and loopback sockets. No live network credentials or upstream writes are required.

```sh
# From this checkout, with a verified executable at /path/to/rnode
PYTHONPATH=. python tools/rholo_probe.py /path/to/rnode \
  --sha256 232d12bd5d3fadc8371c26ec6a888ea48a4062b1187bb63c35b9d19423f28ead \
  --commit e63b7e5a8ccfcc25ff64860ac989d95a748eaaca \
  --repeats 5 --output /tmp/rholo-runtime-probes.json
```

The harness starts its own standalone devnet in a temporary directory, generates synthetic validator keys, restricts requests to loopback, rejects redirects, verifies network identity, peer count and checkpoint anchor, and terminates the subprocess. The `--allow-under-minimum` flag is used only for this ephemeral devnet, never a live validator. Run the pinned binary inside an isolated environment. Each probe reads the same genesis anchor via exploratory deploy. No signed deploy is submitted. The published evidence is bound to compiler and solver source hashes; CI rejects stale evidence or observations outside the model. Re-execution requires obtaining the exact binary (CI artifacts can expire).

## Interpretation

50/50 sampled concrete observations belonged to the predicted sets across 10 fixtures. Competing receives and competing joins exhibited only one of their two predicted outcomes on this runtime; the result is one-sided observational consistency, not exhaustive scheduler coverage. The tested fixtures are closed, finite, recursion-free programs, not arbitrary Rholang programs or distributed transactions. The evidence does not establish formal equivalence, production safety, or third-party replication.
