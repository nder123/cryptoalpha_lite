# Governance Model v1

**Status:** unification spec
**Date:** 2026-06-12
**Scope:** runtime governance layers around decision and execution authority
**Purpose:** define each layer's role exactly once, prevent duplicate rule
ownership, and make drift visible before it becomes runtime behavior.

This document does not introduce runtime behavior. It names the governance
model for already-existing boundary, contract, enforcement, and pre-execution
validation artifacts.

---

## 1. Governance stack

Runtime governance is separated into five roles:

```text
semantics  → definition
boundary   → rule system
contracts  → validation
pre_execution_gate → prevention
runtime_enforcer   → detection
```

The order above is conceptual, not an execution pipeline. No layer receives
authority merely because it is listed later in the stack.

---

## 2. Role separation

### 2.1 `semantics` = definition

Semantics define the meaning of system states, events, decisions, and execution
outcomes.

Responsibilities:

- define vocabulary;
- define what a state or event means;
- define valid status names and lifecycle meanings;
- define the difference between decision, execution, rejection, degradation,
  and observation.

Non-responsibilities:

- does not prevent execution;
- does not detect runtime violations;
- does not implement pre-flight checks;
- does not duplicate boundary rules.

Semantics answer: **"What does this mean?"**

### 2.2 `boundary` = rule system

The boundary declares immutable rules and forbidden changes. In this PR, the
boundary is documented in `docs/runtime_boundary_v1.md`.

Responsibilities:

- define immutable runtime invariants;
- declare which implementation details are mutable;
- define forbidden runtime-core changes;
- state authority rules such as "only decision → execution".

Non-responsibilities:

- does not execute checks;
- does not mutate runtime state;
- does not implement prevention;
- does not store observations.

Boundary answers: **"What rules must never drift?"**

### 2.3 `contracts` = validation

Contracts validate concrete examples or surfaces against the boundary. They are
proof artifacts, not runtime authority.

Responsibilities:

- validate import compatibility;
- validate deterministic contract behavior;
- validate trace and lifecycle examples;
- validate invariant examples such as decision origin and execution result
  consistency.

Non-responsibilities:

- does not own rule definitions;
- does not prevent execution in production flow;
- does not observe arbitrary runtime traces;
- does not add a second version of boundary authority.

Contracts answer: **"Does this example satisfy the rule?"**

### 2.4 `pre_execution_gate` = prevention

The pre-execution gate is a passive pre-flight validation function. It runs
before execution authority is granted and returns allow/deny only.

Responsibilities:

- validate a decision has `trace_id`;
- validate decision origin is present;
- validate risk origin is present;
- validate decision/directive consistency;
- reuse enforcer-style boundary checks where possible;
- return `RuntimeBoundaryResult` or `bool`.

Non-responsibilities:

- does not call `execution_engine`;
- does not route orders;
- does not mutate decision, directive, runtime health, or storage;
- does not start loops, threads, async tasks, or background work;
- does not redefine boundary rules.

Pre-execution gate answers: **"May this decision proceed to execution?"**

### 2.5 `runtime_enforcer` = detection

The runtime enforcer is a passive observer. It detects violations in supplied
events, decisions, and executions.

Responsibilities:

- detect trace continuity violations;
- detect execution without decision origin;
- detect denied/rejected decision producing successful execution;
- return explicit violation codes;
- remain read-only over supplied inputs.

Non-responsibilities:

- does not prevent execution directly;
- does not mutate runtime state;
- does not persist findings;
- does not own semantic definitions;
- does not duplicate contract test fixtures.

Runtime enforcer answers: **"Did this observed flow violate the boundary?"**

---

## 3. Non-overlap rule

Every rule type must have exactly one owner.

| Rule type | Single owner | Other layers may |
|-----------|--------------|------------------|
| Meaning of terms and states | `semantics` | reference |
| Immutable trace / decision / execution rules | `boundary` | reference |
| Example-based proof that a rule holds | `contracts` | consume |
| Pre-flight allow/deny before execution | `pre_execution_gate` | call |
| Post-fact or supplied-trace violation detection | `runtime_enforcer` | call |

If a new rule appears to belong in two places, it must be split into:

1. definition;
2. boundary rule;
3. validation example;
4. prevention check;
5. detection check.

No artifact may own more than one of those roles for the same rule.

---

## 4. Single responsibility enforcement

No layer may duplicate another layer or partially check the same rule with
different semantics.

### 4.1 No duplicate rule implementation

Forbidden:

```text
pre_execution_gate defines its own trace contract
runtime_enforcer defines a different trace contract
contract tests define a third trace contract
```

Allowed:

```text
boundary defines trace rule
runtime_enforcer detects supplied trace violations
pre_execution_gate calls/reuses enforcer-style validation before execution
contracts prove representative traces satisfy the rule
```

### 4.2 No partial same-rule checks

A layer must not implement a weaker local version of a rule unless the weaker
scope is explicitly named.

Forbidden:

```text
pre_execution_gate checks trace_id exists
but ignores decision origin while claiming boundary compliance
```

Allowed:

```text
pre_execution_gate checks only pre-flight eligibility
and delegates broader boundary compliance to runtime_enforcer helpers
```

### 4.3 No hidden authority

Validation does not become authority unless the governance model explicitly says
so.

Forbidden:

```text
runtime_enforcer result mutates execution state
contract test fixture becomes production routing condition
semantics document changes execution behavior by implication
```

Allowed:

```text
pre_execution_gate returns allow/deny before execution
execution_engine remains the only executor
runtime_enforcer remains observer-only
```

---

## 5. Execution truth model

Execution truth is governed by three ordered statements.

### 5.1 Decision is authoritative before execution

Before execution starts, the decision object is the authority source.

Required:

- decision exists;
- decision has trace context;
- decision has risk origin;
- decision/directive origin is internally consistent;
- decision is executable, not deny/reject/no-trade.

No raw event, raw hypothesis, raw risk assessment, runtime health state, or
mutable global state may authorize execution.

### 5.2 Execution is immutable once started

Once execution starts, the execution result is historical evidence. It may be
followed by later corrective events, but it must not be rewritten silently.

Allowed:

- append correction;
- append cancellation;
- append degradation;
- append failure or reconciliation result.

Forbidden:

- silently converting a rejected execution into a filled execution;
- modifying a prior execution result to match a later decision;
- removing trace metadata after execution;
- changing execution origin after execution starts.

### 5.3 Enforcer is passive observer only

`runtime_enforcer` observes supplied traces and reports violations. It does not
own the runtime flow.

Required:

- returns structured result;
- preserves supplied inputs;
- no storage;
- no async loop;
- no runtime mutation;
- no execution side effects.

---

## 6. Drift prevention rules

### 6.1 No duplicate validation logic across layers

If logic is already implemented by a layer, other layers must call it, reference
it, or narrow their scope explicitly.

Examples:

- boundary rule: one source in `docs/runtime_boundary_v1.md`;
- detection: one implementation in `runtime_enforcer`;
- prevention: one pre-flight entrypoint in `pre_execution_gate`;
- contract proof: tests assert behavior without becoming authority.

### 6.2 No cross-layer authority

A layer must not claim the authority of another layer.

Forbidden:

- contracts preventing execution;
- enforcer routing execution;
- pre-execution gate redefining semantics;
- boundary document acting as runtime storage;
- semantics deciding allow/deny.

### 6.3 Changes must preserve ownership

Every future governance-adjacent change must state:

1. Which layer owns the rule?
2. Which layers only reference it?
3. Is the change definition, boundary, validation, prevention, or detection?
4. Does any existing layer already implement the same rule?
5. Does the change create a second authority path?

If the answers are unclear, the change is not ready.

---

## 7. Minimal ownership map

| Artifact | Role | Authority limit |
|----------|------|-----------------|
| `docs/runtime_boundary_v1.md` | boundary / rule system | declares immutable rules only |
| `backend/app/services/runtime_enforcer.py` | detection | observes supplied data only |
| `backend/app/services/pre_execution_gate.py` | prevention | allow/deny before execution only |
| runtime contract tests | contracts / validation | prove examples only |
| semantics documents or enums | semantics / definition | define meaning only |
| `execution_engine` | execution implementation | executes only after decision authority |

This map is normative for v1. Future layers must either fit one row or justify
a new row without overlapping an existing role.
