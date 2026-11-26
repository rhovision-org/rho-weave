# Resume a reservation from its actor state

A box office has three seats. The clerk begins issuing tickets and a reply goes missing. The application must finish from the actor's actual state without selling twice or writing a separate recovery branch for every possible marking.

Forge compiles the offices into independently clocked actors. Weave imports the transitions already authorized by the selected lane and role. The objective declares which initial markings are possible and what completion means. Weave synthesizes a checked policy and emits the Rholang controller that reads the actor and executes its next steps.

## Generate the controller

Run these from a Weave checkout with a sibling Forge checkout at [7b06bd2](https://github.com/rhovision-org/rho-forge/tree/7b06bd2d0d46933627e533e22d605ccf2b839397), with Python 3.10 or newer.

```sh
(cd ../rho-forge && python3 -m rhoforge examples/venues.json --partition --out ../venues)
python3 -m rhoweave.machine ../venues/manifest.json examples/venue-recovery.json --lane free_a --out recovery
python3 -m rhoweave recovery/model.json --verify recovery/certificate.json
```

The output contains the inferred `model.json`, a checked certificate, the portable policy and `recovery.rho`. The binding records the SHA-256 of the actor manifest and generated controller. Use a reviewed manifest from the exact actor you intend to call.

## Run it on Rholo

Use the pinned x86-64 Rholo binary from the [native CI recipe](../.github/workflows/ci.yml). The probe verifies its hash and revision and starts a standalone loopback node with a disposable network ID and synthetic key.

```sh
PYTHONPATH=. python3 tools/demo_recovery.py --forge ../rho-forge \
  --rholo /path/to/rnode --out /tmp/rho-reservation-native.json
```

The cold actor reserves all three seats and issues them. In the lost-reply case the first issuance has already committed inside the exploratory term. The generated controller resumes at the next issuance. Both scenarios finish with three issued seats. The same controller invoked with the manager's capability defers. Removing the observations from the objective produces `NO_POLICY` and no executable controller.

Add `--foundry ../rho-foundry` at the revision pinned in CI to run the same construction on a guarded enumerated contract. Add `--observer /path/to/rchain-observer` to exercise the missing-finality boundary. CI runs both options. The native terms run at the standalone node's explicit exploration checkpoint. Two local read routes expose that same node to Observer, which returns HTTP 503 because the node has no finalized block to report. Weave's read adapter refuses to run a callback on that evidence. The node's block height stays fixed throughout.

Rholo documents the distinction between exploratory genesis and finalized block reads in its [pinned block API implementation](https://github.com/rhovision-org/rholo/blob/e63b7e5a8ccfcc25ff64860ac989d95a748eaaca/casper/src/api/block_api_impl.rs#L169).

## Define a recovery objective

| Field | Meaning |
| --- | --- |
| `role` | Grant whose mutating operations can be considered. |
| `initial` | List of partial markings. The actor may start in any reachable marking matching at least one. |
| `goal` | A partial marking whose exact counts mark completion. |
| `avoid` | Partial markings that exclude unsafe states. Use an empty list to admit all compiled markings. |
| `observe` | Resources whose counts the decision may use. States sharing those counts stay indistinguishable to the solver. |
| `operations` | Explicit list of role-authorized mutating operations allowed during recovery. |

The generated controller uses one portable policy action per belief, selected lexically among optimal choices. Supply its bound view and role capabilities from the same Forge actor instance, or the bound Foundry role capability. Each accepted step checks the expected target and the incremented revision. Stale, denied, exhausted and unexpected replies stop the controller. A successful result witnesses the declared goal at the returned actor revision. Through an external transport, loss of a reply or a concurrent writer may require the caller to obtain a fresh observation.

The model is limited to the enumerated artifact and declared observations. Recovery spans a single instance and revision scope. Other writers can change its state between calls, and each revision check can cause a defer. The controller provides bounded progress for admitted modeled outcomes. The caller authenticates transports and owns external effects, retries and deployment. [Read anchor adapter](POLICY.md#observer-read-anchors)

## Comparison

A handwritten controller needs a separate table of authority, valid transitions, visible observations and revision checks. Changing the actor can invalidate that table. A general-purpose model checker such as [PRISM](https://www.prismmodelchecker.org/) can synthesize a strategy from a supplied model. This compiler derives the finite model from the actor's emitted rules and generates the Rholang that applies the checked strategy through the existing capability interface.
