# Runtime Semantics v1

Frozen semantic contract for the CryptoAlpha runtime system.

This document is the single authoritative reference for how runtime,
contracts, and observability relate to each other. No runtime module,
test, or observability layer may violate these rules.

---

## §1 Source of Truth

| Layer           | Role                                      |
|-----------------|-------------------------------------------|
| **Runtime**     | единственный источник состояния (state)   |
| **Tests**       | observer — never a generator              |
| **Observability** | derived layer — not authoritative       |

- Runtime (`execution_engine`, `risk_engine`, `trading_gate`) owns all
  mutable state.
- Tests read and validate state; they never produce runtime events.
- Observability records artifacts derived from runtime; it has no
  authority over state transitions.

---

## §2 Event Semantics

Every event in the system belongs to exactly one category:

| Category               | Origin                          | Example                        |
|------------------------|---------------------------------|--------------------------------|
| `input_event`          | external feed / operator command | `MarketSnapshot`, `OperatorCommand` |
| `decision_event`       | `risk_engine` + `trading_gate`  | `RiskAssessment`, `GateDecision`, `TradeDirective` |
| `execution_event`      | `execution_engine`              | `ExecutionReport`              |
| `observability_event`  | observability layer (PR #8)     | `ObservabilityArtifact`        |

**Rule:** `observability_event` is a derived category.  It MUST NOT
influence runtime state, decisions, or execution.

---

## §3 Trace Contract

1. `trace_id` is **mandatory** on every runtime event.
2. Absence of `trace_id` = **invalid state** → observability validation
   MUST reject it.
3. Trace lineage follows a strict causal chain:

```
input_event → decision_event → execution_event
```

4. Every link in the chain shares a `trace_id` (or equivalent
   `directive_id` / `hypothesis_id` lineage).
5. Broken lineage (orphan `parent_id`) MUST be detected by
   `check_lineage_compatibility`.

---

## §4 Execution Rule

`execution_engine` is a **pure executor**.  It:

- **accepts** a decision (`TradeDirective` / `CTOAiDecision`)
- **executes** the action against the exchange
- **reports** the outcome (`ExecutionReport`)

It **MUST NOT**:

- originate trading decisions
- bypass `risk_engine` or `trading_gate`
- mutate risk parameters

**Decision authority** belongs exclusively to:

```
risk_engine  →  trading_gate  →  CTO-AI orchestrator
```

---

## §5 Observability Rule

The observability layer (`ObservabilityLedger`, `ShadowRuntime`,
contract tests) **may**:

- verify event presence
- validate trace consistency
- record artifacts in memory

It **MUST NOT**:

- modify runtime state
- influence any `decision_event`
- influence any `execution_event`
- write to the exchange or event bus
- introduce side-effects into the runtime path

Observability is **read-only** with respect to the runtime.

---

## §6 Determinism Rule

```
same input  →  same decision  →  same execution
```

1. No randomness is permitted in the runtime path
   (`input → decision → execution`).
2. Non-deterministic sources (timestamps, UUIDs, network jitter) MUST
   be isolated behind injectable interfaces so that tests can supply
   fixed values.
3. Any function on the runtime path that introduces
   non-deterministic behaviour violates this contract.

---

## §7 Test Contract Boundary

Tests (contract tests, e2e, invariant checks) **MUST NOT**:

- create runtime events
- emulate runtime logic (risk evaluation, gate checks, execution)
- replace `execution_engine`, `risk_engine`, or `trading_gate`

Tests **MAY only**:

- verify event sequences
- verify invariants (state machine transitions, risk bounds)
- verify trace consistency (`trace_id` presence, lineage integrity)
- use lightweight in-memory validation (no daemons, no async loops)

---

## Revision History

| Version | Date       | Description          |
|---------|------------|----------------------|
| v1      | 2026-06-12 | Initial frozen spec  |
