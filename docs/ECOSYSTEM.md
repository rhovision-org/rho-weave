# Recovering an interrupted resource workflow

| Project | What it provides |
| --- | --- |
| [Weave](https://github.com/rhovision-org/rho-weave) | A checked policy and Rholang recovery controller from a finite machine and an application objective. |
| [Forge](https://github.com/rhovision-org/rho-forge) | Resource actors with local revision checks and independent lanes for disjoint workflows. |
| [Foundry](https://github.com/rhovision-org/rho-foundry) | Guarded arithmetic contracts and enumerated machines for finite policy derivation. |
| [Observer](https://github.com/rhovision-org/rho-observer) | An anchor with source coverage and freshness for explicit by-hash reads. |

The [native reservation demo](RECOVERY.md) builds a Forge actor, derives its recovery policy and executes the resulting controller on Rholo. It also exercises the enumerated Foundry interface and Observer's missing-finality response. The supplied actor capabilities govern mutation within one instance. Applications own deployment and external effects.
