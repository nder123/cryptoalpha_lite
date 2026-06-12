# Runtime Boundary v1

**Status:** contract boundary document
**Date:** 2026-06-12
**Scope:** runtime execution contract for `event_bus → risk_engine → trading_gate → execution_engine`
**Purpose:** separate implementation details that may evolve from invariants that must not drift.

This document is intentionally narrow. It does not introduce a new runtime
system, a new validation framework, or a new execution path. It names the
boundary between:

1. **Mutable implementation details** — code may change if the contract still
   holds.
2. **Immutable runtime invariants** — code must not change in ways that break
   traceability, decision order, or execution authority.

---

## 1. Runtime boundary summary

The runtime execution path is:

```text
input event
  → event_bus
  → risk_engine
  → trading_gate
  → execution_engine
  → execution result
```

The implementation behind any stage may be refactored, optimized, or routed
differently. The observable contract between stages must remain stable.

---

## 2. Mutable layer — what can change

The following are implementation details. They may change without violating
this boundary document, provided the immutable layer in §3 remains true.

### 2.1 Risk strategy implementation

Allowed changes include:

- risk scoring formulas;
- threshold tuning;
- position sizing heuristics;
- denylist / allowlist evaluation details;
- risk budget source or aggregation method;
- additional non-authoritative risk metrics.

Constraint: changing risk strategy must not allow a trade decision to bypass
`risk_engine`.

### 2.2 Execution routing logic — internal only

Allowed changes include:

- exchange adapter internals;
- dry-run routing internals;
- order parameter formatting;
- retry/backoff details;
- internal routing between paper, shadow, testnet, and live modes;
- internal rejection reason formatting.

Constraint: execution routing is not an authority boundary. It can route only
after a decision object exists.

### 2.3 Performance optimizations

Allowed changes include:

- caching read-only inputs;
- reducing allocations;
- batching internal reads;
- improving serialization;
- optimizing validation helpers;
- replacing equivalent pure functions with faster implementations.

Constraint: performance work must not reorder the externally observable event
sequence or mutate decision/execution state silently.

---

## 3. Immutable layer — what cannot change

These are runtime contract invariants. A change that breaks any item in this
section is a boundary violation, even if all modules still import.

### 3.1 Trace ID contract

Every runtime flow has one `trace_id`.

That `trace_id` must remain identical across:

```text
input event
risk output
gate decision
execution result
```

Rules:

- each downstream output must preserve the upstream `trace_id`;
- derived metadata may add context, but must not replace or fork the trace;
- a missing `trace_id` is invalid;
- multiple trace IDs in one execution flow are invalid unless the flow is
  explicitly modeled as a new root event with its own lineage.

### 3.2 Decision flow order

The runtime flow order is immutable:

```text
event_bus.emit(event)
  → risk_engine.evaluate(event)
  → trading_gate.decide(event)
  → execution_engine.execute(decision)
```

Required ordering guarantees:

1. input event exists before risk evaluation;
2. risk output exists before gate decision;
3. gate decision exists before execution;
4. execution result is downstream of exactly one decision;
5. each stage must be traceable to its immediate parent stage.

Implementation may rename methods or refactor classes, but the authority order
must remain equivalent to this sequence.

### 3.3 Execution authority

Only a decision can authorize execution.

Valid authority chain:

```text
risk_engine result
  → trading_gate decision
  → execution_engine execution result
```

Invalid authority chains:

```text
input event → execution_engine
risk_engine → execution_engine
trading_gate state read → exchange order
manual state mutation → execution result
```

Execution may reject, cancel, or degrade a decision. It must not invent a
successful execution without a decision object.

### 3.4 Event ordering guarantees

The ordered event trace is part of the contract.

For a single execution flow:

```text
created
  → risk_checked
  → decided
  → executed | rejected | cancelled | degraded
```

Rules:

- downstream events must not appear before their parent event;
- no orphan execution result may exist;
- no decision may exist without traceable input/risk context;
- rejected or denied decisions must not produce a successful execution status;
- ordering is strict inside one trace, even if different traces are processed
  concurrently by future outer orchestration.

---

## 4. Forbidden changes

The following changes are forbidden inside the runtime core boundary.

### 4.1 Adding async loops in runtime core

Do not introduce new async loops, background schedulers, or thread/process
systems into the core contract path as a way to satisfy runtime closure.

Allowed: outer orchestration may remain async if already present.

Forbidden: making the core contract depend on a new loop to preserve ordering,
traceability, or execution authority.

### 4.2 Bypassing `risk_engine`

No execution-class decision may skip risk evaluation.

Forbidden examples:

- trading gate emits an execution decision from raw input only;
- execution engine accepts a raw hypothesis/event as authority;
- manual/operator path mutates execution state without risk context or an
  explicit decision object.

### 4.3 Direct execution without decision

`execution_engine` must not execute from:

- raw event;
- raw hypothesis;
- raw risk assessment;
- runtime health state alone;
- mutable global state.

The input to execution authority is a decision object. Everything else is
context, not authority.

### 4.4 Silent state mutation

Runtime state transitions must be observable through event output, trace
metadata, evidence, or explicit result objects.

Forbidden examples:

- changing decision status without an emitted/recorded result;
- mutating trace metadata without preserving parent lineage;
- converting a denied decision into a successful execution silently;
- modifying runtime health state as a side effect of unrelated validation.

---

## 5. Review checklist for future changes

Before merging a runtime-adjacent change, reviewers should be able to answer:

1. Does every execution result still have a decision parent?
2. Does every decision still have traceable input/risk ancestry?
3. Does `trace_id` remain stable from input through execution result?
4. Can rejected/denied decisions ever report successful execution?
5. Did the change add a new loop, scheduler, replay engine, or hidden runtime
   authority inside the core contract path?
6. Are performance changes preserving strict per-trace ordering?

If any answer is unclear, the change belongs outside the immutable runtime
boundary until the contract is made explicit.
