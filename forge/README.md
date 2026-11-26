# Rho Forge

**Describe the resources. Declare the goal. Generate the transaction.**

Rho Forge is a standalone finite-resource workflow compiler. It takes a JSON declaration of bounded resources, role-scoped primitive transitions, linear conservation invariants, and target markings (missions). It generates a runnable Rholang factory and a machine-readable mapping of states, actions and synthesized plans. No Python library dependencies, no network calls at compile time, and no hand-written Rholang transition branches.

Unlike a test tool or policy checker, Forge emits the actual stateful actor. Each factory invocation returns a fresh read capability and separate private operation capabilities, one per declared role. Each operation consumes the single private state cell, checks the expected revision, and restores or changes the cell exactly once. A mission is compiled from a shortest role-authorized path and commits its final marking in one state-cell update; intermediate markings are not exposed. It is not a sequence of calls to external contracts.

## First use

```sh
python3 -m rhoforge examples/escrow.json --out build-escrow
python3 -m unittest discover -s tests -v
```

`build-escrow/factory.rho` is Rholang source; `manifest.json` maps the returned state IDs to resource markings and plans. The output directory must not already exist. A checked-in, reproducible [factory](examples/generated/factory.rho) and [manifest](examples/generated/manifest.json) are also ready to inspect or run.

The example is a **synthetic** escrow/resource-reservation model, not a REV wallet, asset custody or financial product. Three funding steps plus one reservation become one `open` mission. A seller capability can settle only when its declared prerequisites hold. A buyer capability cannot release seller-owned resources. Two competing `open` requests at revision zero result in one `OK` and one `STALE`. Two instances from the same factory have independent private state.

## Interface

The compiler provides the public factory name in the manifest. A caller invokes it with a private reply channel:

```rho
new ready in {
  @"rhoForge_escrow_0ff8383b9b4703a8"!(*ready) |
  for (view, buyer, seller <- ready) {
    new reply in {
      buyer!("open", 0, *reply) |
      for (@result <- reply) { @"out"!(result) }
    }
  }
}
```

Compose that invocation in parallel with the generated factory source. The factory returns the read capability, then role capabilities in sorted role-name order. The operation protocol is `cap!("action", expectedRevision, *reply)`; the read protocol is `view!(*reply)`. Replies are `(status, stateId, revision, plan)`. `OK` increments the revision; `STALE`, `DENIED`, `ALREADY`, `EXHAUSTED`, and `READ` do not. The factory creator is trusted to distribute capabilities appropriately; possession, not a username or signature, determines role admission. Do not publish private capabilities.

## Model

For marking `m`, transition `t` has consumption `c_t`, production `p_t`, and capacity `C`. It is enabled iff `m >= c_t` and `m - c_t + p_t <= C` componentwise. Every declared invariant `w` must satisfy `w·(p_t-c_t)=0` for every primitive. The compiler enumerates reachable markings exactly for the supported finite model. For a mission of role `r`, reverse BFS from its goal markings on the role's primitive edges produces shortest paths, with lexical tie-breaking. No path means no emitted admission branch. An already satisfied mission is a non-mutating operation. The runtime uses a private state cell and a compare-and-set revision to serialize operations, including missions.

Input schema: see [escrow.json](examples/escrow.json). Place capacities 1..1000, up to 12 places, 8 roles, 32 primitive transitions, 16 missions, 12 linear invariants, 128 reachable states, 4096 primitive edges, 512 KB generated source. On a size limit the compiler returns `UNKNOWN` and does not emit a partial actor. No arbitrary source snippets, arithmetic expressions, loops, external effects, unbounded resource counts, or data-dependent predicates are accepted. A mission can use only its role's own primitives; it never acquires another role's capability. The generated actor enforces only supplied constraints. Do not mistake them for comprehensive application invariants.

## Runtime validation

The included [runtime evidence](evidence/runtime.json) records 151 exploratory executions against the pinned actual Rholo binary (commit `e63b7e5a8ccfcc25ff64860ac989d95a748eaaca`), using an ephemeral loopback-only standalone devnet with synthetic keys and unchanged block height. All 126 state × role × action combinations in the escrow example were executed once; five additional scenarios were executed five times each. Each concrete reply multiset matched the reference interpreter. No transaction was signed or deployed to any existing network. This establishes finite-fixture agreement, not full semantic equivalence or proof of chain-level production behavior.

In the Rho Weave checkout, run from the `forge/` directory:

```sh
PYTHONPATH=. python tools/probe_generated.py --weave-root .. \
  --binary /path/to/rnode \
  --sha256 232d12bd5d3fadc8371c26ec6a888ea48a4062b1187bb63c35b9d19423f28ead \
  --commit e63b7e5a8ccfcc25ff64860ac989d95a748eaaca \
  --repeats 5 --output /tmp/forge-runtime.json
```

Use the pinned Rholo artifact identified in the parent [runtime guide](../docs/RUNTIME.md). The compiler itself is standalone; only optional runtime reproduction uses the adjacent isolation harness. The actual runtime checks are bounded; real deployment, resource sizing/phlo, durable recovery, external state/asset effects, authorization and adversarial audits remain separate tasks. No production asset claims. No upstream changes or deployment required. See the parent repository for licensing.

## License

Rho Forge is covered by the parent repository's [Apache License 2.0](../LICENSE).
