# Rho Weave

The first ticket went out. Its reply never came back.

The clerk still needs to finish issuing the tickets. From outside the contract, the missing reply leaves more than one possible state. I built Weave to turn those possibilities into a checked decision and, for supported compiled contracts, into recovery code that can act on it.

Created by [AixAria](https://github.com/aixaria0).

Forge and Foundry can supply the rules that drive a recovery. Observer helps the application pin a separate read to one block. [Where the inputs come from](#where-the-inputs-come-from)

![The reply to ticket 1 disappears. Weave's generated controller reads one issued and two held, issues tickets 2 and 3 at the expected revisions, and returns DONE.](docs/motion/overview.gif)

[Static storyboard](docs/motion/overview.png) · [Text walkthrough](docs/motion/README.md)

## Finish the reservation

In the native Rholo example, the clerk holds all three seats and issues the first. The demo discards the issuance reply. The generated controller reads the actor at revision 2, sees one issued and two held, and issues the remaining two. At revision 4 the actor has issued all three. Try the same recovery with the manager's capability and it returns `DEFER`.

The developer specifies possible starting counts, observable counts, a goal and allowed actions. Weave gets the role's actual transitions from the actor manifest. The controller checks the new state and revision after each step. That keeps the recovery implementation tied to the contract's rules as they evolve. [Native walkthrough](docs/RECOVERY.md) · [Recorded run](https://github.com/rhovision-org/rho-weave/actions/runs/45809327924)

### Build the controller

Git and Python 3.10+ are enough for this part. Start in a directory for the two checkouts.

```sh
git clone https://github.com/rhovision-org/rho-forge.git
git clone https://github.com/rhovision-org/rho-weave.git
(cd rho-forge && python3 -m rhoforge examples/venues.json --partition --out ../venues)
cd rho-weave
python3 -m rhoweave.machine ../venues/manifest.json examples/venue-recovery.json \
  --lane free_a --out recovery
python3 -m rhoweave recovery/model.json --verify recovery/certificate.json
```

Expect `WIN`. Open `recovery/model.json` to see the derived problem and `recovery/policy.json` to see the portable decisions. The certificate can be checked separately, and `recovery/recovery.rho` is the executable controller. For Rholo, give it the view and operation capabilities from the same Forge lane instance. [Objective format, invocation and native reproduction](docs/RECOVERY.md)

Try a copy of the objective with `"observe": []`, then point the compiler at the copy and use a new output directory. It returns `NO_POLICY` and writes the checked model and certificate. Without the counts, the controller cannot distinguish a state where it should issue a ticket from one where it must reserve first. [Example objective](examples/venue-recovery.json)

## What a policy can promise

Weave groups possible states by what the caller can see. A group of states consistent with an observation is a *belief*. An action has to work from every state in the belief, and every modeled outcome has to preserve safety and make progress toward the goal. The certificate checker can reproduce those obligations. The solve, check and export path shares one construction of the reachable graph, down from three.

You can also supply your own finite model. The Quantum OS recovery example starts with several possible remote statuses. It admits a refresh first and can defer when the model's retry budget expires. An exhausted search budget returns `UNKNOWN`. A checked model is valuable within its supplied observations, actions and failure assumptions. At runtime a stale revision or unexpected reply can stop the controller. [Policy and formats](docs/POLICY.md) · [Manual model walkthrough](docs/GUIDE.md)

A portable policy can be used by the Python or JavaScript monitor. To generate a model directly from source, the separate Rholang fragment compiler supports a restricted one-shot fragment. [Fragment compiler](docs/COMPILER.md) · [Runtime evidence](docs/RUNTIME.md) · [Security](SECURITY.md)

## Where the inputs come from

![Forge and enumerated Foundry feed Weave's Rholang recovery compiler. Observer provides a separate input to a by-hash read adapter.](docs/images/ecosystem.svg)

[Forge](https://github.com/rhovision-org/rho-forge) supplies flat actor manifests or a selected lane of a partitioned manifest. [Foundry](https://github.com/rhovision-org/rho-foundry) supplies an enumerated state-and-rule table. Its symbolic backend produces an arithmetic contract with a different machine format, so use the enumerated backend when you want Weave recovery. [Supported artifact interfaces](docs/ECOSYSTEM.md)

[Observer](https://github.com/rhovision-org/rho-observer) can supply a finalized anchor when your application needs an external read. The optional adapter checks freshness and requires the response to match that block. Your application provides the trusted read callback. Recovery still uses the actor's capabilities and revision. [Observer adapter](docs/POLICY.md#observer-read-anchors)

[Repository structure and contributions](docs/DEVELOPMENT.md) · [CI](https://github.com/rhovision-org/rho-weave/actions)

## License

[Apache License 2.0](LICENSE). External software remains under its own license.
