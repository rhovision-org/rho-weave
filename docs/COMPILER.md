# Finite source compiler contract

## Accepted grammar

```text
program := process
process := atom ("|" atom)*
atom    := "Nil" | channel "!" "(" "Nil" ")"
         | "new" private ("," private)* "in" "{" process "}"
         | "for" "(" clause (";" clause)* ")" "{" process "}"
clause  := "_" "<-" channel
channel := private | public-literal
```

Public literals have the form @"identifier". The declared external inputs and goal/forbidden outputs must be disjoint. A public input is receive-only in the source; a public output is send-only. Private names must be lexically bound; each syntactic binder is allocated a distinct static identity, sound for this one-shot fragment. No recursion, persistent contracts, name passing, non-Nil data, arithmetic, arbitrary expressions or external environment interactions.

## Transition semantics

A configuration is a multiset of pending one-shot receives and messages plus the multiset of previously injected inputs. Parallel activation makes sends available immediately and adds receives to the pending multiset. A reduction consumes one matching message per join clause and the receiver atomically, then activates its continuation. The fragment is finite because every syntactic receive can activate and fire at most once in one execution. All enabled reductions are explored until no internal step remains. One external input can be injected at a quiescent boundary if its injection budget has not been exhausted (1 by default). Each resulting quiescent configuration is a nondeterministic target of that input. Public output counts are the observation. A forbidden output makes the state unsafe; all goal outputs make a safe state terminal.

The external controller observes only output counts and the action/observation history. Intermediate forbidden outputs cannot disappear because public output channels cannot be consumed. The game solver checks safety and finite progress to the declared terminal objective; it does not prove fairness or liveness for unbounded real execution. Source hash is included in the model name and the model certificate binds the generated graph.

Limits: 64 KiB source, 128 instruction occurrences, 128 private binders, nesting 64, 32 public names, join width 32, input budgets 1–16 each and total 64, 100,000 internal reduction attempts, 256 compiled states, 20,000 transitions, and engine belief limits. An exhausted bound does not imply no policy. Ten closed-fragment fixtures were compared with the actual pinned Rholo interpreter, five runs each. All 50 observations belonged to the predicted sets. This is sampled agreement, not formal equivalence; see [runtime evidence](RUNTIME.md).

## Acceptance

The tests cover a controllable safe sequence, initial and triggered competing receives (including unsafe schedules), direction constraints, unsupported syntax, one-shot injection, deterministic output and source binding. The compiler is an offline analysis component. Integrations must explicitly account for real network and runtime behaviors absent from this fragment.
