# Model and integration guide

Start with the [README](../README.md) for examples.

## Model contract

The JSON object has a name, a mapping of concrete state IDs to objects with observation (string), safe (boolean) and goal (boolean), a nonempty initial list of possible state IDs, and transitions represented as triples of source state, action name and target state.

Goal states are terminal. A missing action is unavailable, not a self-loop. Multiple targets for an action represent nondeterminism: the environment can choose any target. Include every possible interference outcome, timeout and race relevant to the protocol. Internal safety between modeled state boundaries must also be represented if it is relevant.

## Solving

An initial belief is an observation-equivalent subset of the initial states. From a belief, an action must be available in every concrete state. Its successors are the unions of all possible targets partitioned by their observations.

A safe belief entirely composed of goal states has rank zero. Otherwise a winning belief has rank one plus the smallest worst-case successor rank over actions for which every successor is winning. A losing belief has no finite rank. The solver computes the least fixed point of robust reachability with a reverse hyperedge worklist and rank-ordered priority queue.

Each exported action strictly decreases rank, guaranteeing finite progress to a goal for modeled outcomes. Equal optimal actions may all be emitted. This minimizes worst-case decision count, not elapsed time, operational cost or maximum permissiveness. An indistinguishable mixture of goal and non-goal states does not terminate automatically.

The certificate checker recomputes graph coverage, the rank recurrence, allowed actions and model binding. It is a separate checking procedure in the same implementation, not third-party formal verification.

## Operating limits

| Item | Limit |
| --- | ---: |
| Concrete states | 256 |
| Action names | 256 |
| Transitions | 20,000 |
| Beliefs | 10,000 |
| Distinct action/observation graph arcs | 2,000,000 |
| Model and trace files | 4 MB |
| Certificate input and artifact output | 64 MB |

The CLI --limit option sets the belief budget from 1 to 10,000. Search can still consume substantial memory or time. Use external process limits and disposable directories for untrusted inputs. Budget exhaustion is UNKNOWN, not NO_POLICY.

The CLI rejects duplicate keys, invalid JSON constants and output paths that alias input paths. Each output is written by atomic replacement; multiple output files are not one transactional publication.

## Runtime integration

Use a policy produced from a reviewed model. The Python monitor checks the certificate and snapshots supplied inputs. The JavaScript monitor verifies table structure, model hash and descending ranks. PolicySession.fromVerifiedBytes additionally checks an artifact SHA-256 supplied through an independently trusted channel using Web Crypto.

The application must authenticate observations, serialize side effects, enforce policy admission before execution and model all relevant external interference. The monitor does not execute actions, verify remote state proofs, guarantee deadlines or grant on-chain authority.

The optional anchoredRead adapter requires a verified finalized hash, genesis and trusted by-hash transport. It rejects malformed responses and does not fall back to another block. recommendPreparedRecovery requires an authoritative status provider and produces a recommendation rather than a transaction. See [SECURITY.md](../SECURITY.md).

### Observer read anchors

`rhoweave.anchor.anchored_read` accepts a fetch callback for Observer's read-anchor envelope and a by-hash callback. Supply the expected network and shard plus your own maximum sample age. The adapter checks the service freshness threshold, complete source coverage, the caller's age limit including both callbacks, and the response binding to the chosen block hash. The callback returns a mapping with `network_id`, `shard_id`, `block_hash` and `value`.

Use authenticated transports. The caller supplies any independent validation of chain identity, data and external effects. A valid older anchor may still be stale relative to an actor's current revision. [Full reservation demo](RECOVERY.md)

## Other inputs

The [finite Rholang fragment](COMPILER.md) has a separate source compiler. The optional TypeScript auditor supports a particular literal recovery switch, not arbitrary TypeScript.

To reproduce the historical Quantum OS table extraction without executing upstream TypeScript:

```sh
gh api 'repos/rhovision-org/quantum-os/contents/packages/browser/src/exchange-2pc.ts?ref=4d3e73b1f7d5ffe0c98b1b1c65a17c9937589948' --jq .content | base64 -d > ../qos-pinned.ts
python3 -m rhoweave.recovery ../qos-pinned.ts examples/quantum-os.json
```

The auditor extracts all 16 status pairs. The historical prepared/unknown recommendation conflicts with two possible states in the supplied model. This is a model-relative counterexample, not evidence of a live attack.

The [source evidence](../evidence/SOURCE.md) and [runtime guide](RUNTIME.md) identify pinned revisions, experimental boundaries and reproduction commands.
