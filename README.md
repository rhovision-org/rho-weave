# Rho Weave

**Compile an uncertain protocol into a checked decision policy.**

Rho Weave is a standalone, dependency-free finite-game policy synthesizer. Given a protocol with hidden concrete states, visible observations, nondeterministic action outcomes, a safety predicate and a terminal objective, it derives a decision policy with a finite worst-case step bound. It returns `NO_POLICY` when no such strategy exists in the supplied finite model, rather than guessing. Export a verified policy table to the included JavaScript monitor or use the Python monitor.

```sh
python3 -m rhoweave examples/quantum-os.json --output policy-cert.json --export policy.json
python3 -m rhoweave examples/quantum-os.json --verify policy-cert.json --trace examples/quantum-os-trace.json
python3 -m unittest discover -s tests -v
node runtime/test.mjs policy.json
```

Python 3.10+, Node 18+ for the optional JS runtime. No installation dependencies or network requests. `WIN` exits 0, `NO_POLICY` exits 1, `UNKNOWN` (resource limit) and `ERROR` (invalid input) exit 2. Model and trace input limit 4 MB; certificate input and artifact output limit 64 MB. Artifact writes are atomic and reject output/input path aliasing. Run only in a disposable directory for untrusted models.

## Why RhoVision

Two source-grounded boundary problems: RhoGov's pinned read client uses a short cached tip and fallback; Quantum OS's recovery decision table conflates missing and unreachable remote legs. The models demonstrate automated policy construction, not merely identification of failing cases. The RhoGov example finds a two-operation coherent read strategy; the Quantum OS example selects a safe recovery recommendation after bounded re-observation, or defers explicitly. The third example demonstrates infeasibility under an unlimited partition with no permissible defer.

See [source anchors and limitations](evidence/SOURCE.md). The original examples are manually authored abstractions. Version 0.2 adds a finite Rholang fragment compiler, a literal TypeScript recovery-table extractor, and offline boundary adapters. No live deployment has been validated. No claim of global novelty, superiority over established game solvers, actual project schedule savings, or production readiness is made. This is an executable research prototype.

## Input and semantics

A JSON model contains `name`, `states` (mapping IDs to `{observation,safe,goal}`), `initial` (possible starting IDs), and `transitions` (triples `[source,action,target]`). Each action must be available in every possible concrete state. The environment chooses any listed target; the client sees the observation of that target. The model must encode all admissible interference between actions, including timeouts and races. Goal states are terminal. Missing action means unavailable, not an implicit self-loop. A goal mixed with indistinguishable non-goal states cannot silently terminate.

A belief is the set of concrete states consistent with observations. The compiler enumerates reachable beliefs and solves the least fixed point of robust reachability over safe beliefs. Rank zero means all states are goals. Otherwise `rank = 1 + min_action max_outcome rank(successor)` over actions with all winning outcomes. Null rank is losing. The certificate checker independently checks this recurrence, exact reachable graph coverage, action sets and model binding. All emitted actions strictly decrease rank, so every modeled execution terminates safely in at most its initial rank. Safety applies only to modeled state boundaries; intermediate effects must be modeled explicitly. The policy is minimum worst-case decision horizon, not maximum permissiveness or minimum latency/cost.

The solver uses a reverse hyperedge worklist, with a priority queue ordered by rank. Explicit belief enumeration can be exponential in concrete state count. Bounds: 256 concrete states, 256 action names, 20,000 transitions, 10,000 beliefs, 2 million distinct action/observation graph arcs (limits are not a strict wall-clock or memory guarantee). `NO_POLICY` is conclusive only for the declared model and objective; resource exhaustion is `UNKNOWN`. No fairness, distributed atomicity, or liveness under arbitrary real network partitions is assumed.

## Safe adoption

Keep the existing repos unchanged. Run this standalone, review the model with maintainers, validate model-to-implementation correspondence on pinned isolated fixtures, then consider an explicitly approved adapter. The runtime does not execute network actions; it checks which named actions are permitted and advances on observations. A real caller must check admission **before** side effects, authenticate and bind observations, serialize execution, handle action failure, and model external interference. Do not use the monitor as a transaction engine or as a substitute for on-chain authorization. See SECURITY.md.

## Release 0.1.1

The Python monitor snapshots caller-owned inputs; the JS monitor validates table structure and descending ranks and supports SHA-256 artifact verification against an independently trusted digest. These checks do not authenticate the underlying model or observations. The project remains an offline bounded-model prototype, not a production transaction engine.

## Release 0.2.0 — executable boundary integration

### Compile a finite Rholang fragment

```sh
python -m rhoweave.rholang examples/coherent-read.rho \
  --input pin --input read --input unsafe_read \
  --goal coherent --forbid mixed --output compiled.json
python -m rhoweave compiled.json --output cert.json --export policy.json
```

The compiler translates a closed recursion-free process fragment into a finite observation game. It explores all maximal internal communication reductions between one-shot external input injections, rather than assuming a particular receive schedule. Supported syntax: one outer `new`, parallel composition, `Nil`, sends carrying `Nil`, one-shot wildcard receives, static private channels and literal public input/output names. Public output channels are write-only; a forbidden output cannot be hidden by later consumption. Goals are terminal once all declared goal outputs appear. Private names are local to the source; no external messages other than declared injections are modeled. This is an explicit finite abstraction, not the complete Rholang language or a verified equivalent of the Rholo interpreter. Unsupported syntax fails closed; limits return UNKNOWN. See [compiler contract](docs/COMPILER.md).

### Audit the pinned Quantum OS recovery table

```sh
# Obtain this public source by immutable revision, outside the project tree:
gh api 'repos/rhovision-org/quantum-os/contents/packages/browser/src/exchange-2pc.ts?ref=4d3e73b1f7d5ffe0c98b1b1c65a17c9937589948' --jq .content | base64 -d > ../qos-pinned.ts
python -m rhoweave.recovery ../qos-pinned.ts examples/quantum-os.json
```

The auditor reads the supported literal switch structure without executing TypeScript. All 16 status pairs are extracted; the pinned source recommends abort-local for (prepared, unknown), which conflicts with two states in the supplied model. The result is a model-relative counterexample, not a demonstrated live exploit or proof that a transaction can reach these states. The extracted table and hashes are in [evidence](evidence/quantum-os-source-audit.json).

### Use the policy at a client boundary

`runtime/adapters.mjs` exports `anchoredRead` (same finalized hash for all reads, no fallback) and `recommendPreparedRecovery` (refresh and produce a recommendation, never execute settlement). These accept a caller-provided transport/status provider and trusted policy table. They perform no networking/signing themselves. Finality, chain identity, observation authentication, and deadlines are caller/transport obligations.

```sh
python -m rhoweave examples/rhogov.json --export gov-policy.json
python -m rhoweave examples/quantum-os.json --export qos-policy.json
node runtime/test-adapters.mjs gov-policy.json qos-policy.json
```

The reference tests use controlled in-process transports. No live-network access, upstream writes, or claims of full protocol verification. The supported envelope remains offline finite-model synthesis and checked client recommendations.
