# Source grounding and evidence boundary

Read-only GitHub connector fetches of the following pinned files were performed in this session:

- [RhoGov node.ts](https://github.com/rhovision-org/rhogov/blob/f93afaaf8b8053d230bfaabfe7b35b0377078345/src/chain/node.ts): `latestHash` caches the newest tip for 1500 ms; `explore` uses it if possible and falls back to an unpinned finalized read. A previous Genesis controlled HTTP fixture witnessed a mixed-block read. The model assumes that an explicit pinned read is available and returns coherent results; error handling, trust in node responses, and actual finality selection are not implemented here.
- [Quantum OS exchange-2pc.ts](https://github.com/rhovision-org/quantum-os/blob/4d3e73b1f7d5ffe0c98b1b1c65a17c9937589948/packages/browser/src/exchange-2pc.ts): `TxLegStatus` documents `unknown` as both never prepared and unreachable; `decideRecovery(prepared, unknown)` returns `abort-local`. This motivates the distinction in the model. It does NOT prove a live vulnerability: reachability, race conditions, contract guards and recovery behavior must be examined before any upstream conclusion. The modeled goal is a safe decision or explicit defer, not actual settlement. `refresh` is assumed to return an authoritative status or timeout. No claim of guaranteed eventual network response.
- Previous Genesis evidence also reports Rholo replay operates on observed execution traces and QLF/Quantum OS predicate boundaries differ. These are possible future model-adapter targets, not implemented integration.

The baseline here is the direct unpinned read or direct unknown-to-abort rule represented in the model. The compiler rejects them when a possible outcome is unsafe. There is no comparison against a full conventional model checker or game solver. The fixed-point algorithm is established; novelty and adoption value remain unverified.

No upstream writes, production deployments, external dependency installations, or live network probes were performed. No hosted CI was executed. The examples are hand-authored finite models and use no upstream source execution.
