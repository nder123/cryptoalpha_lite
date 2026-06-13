# Architecture Lock Manifest v2

This document freezes the Validation System v2 architecture boundary for the
controlled pilot validation system.

## 1. Final authority map

| Component | Final authority | Boundary |
| --- | --- | --- |
| `ContractRegistry` | ONLY contract evaluation | Interprets `CONTRACT_RULES` and produces hard contract outcomes. |
| `ValidationCore` | ONLY decision authority | Orchestrates validation layers and owns final decision semantics. |
| `ValidationCore._merge()` | ONLY final `allowed` computation | Computes the final `ValidationResult.allowed` value. |
| `event_contract` / `event_lineage` | Observation only | Validate trace-level and event-level lineage structure without decision authority. |
| `pre_execution_gate` / `runtime_enforcer` | Warning-only signals | Produce soft observability and risk signals only. |
| `cross_module_consistency` | Observability only | Reports coverage and consistency visibility without mutating final decision state. |

## 2. Hard invariants

These rules are immutable for Validation System v2:

1. Contract failure MUST produce `allowed=False`.
2. No downstream layer can override contract failure.
3. Only `ValidationCore` defines the final decision.
4. Lineage MUST NOT influence `allowed`.
5. Pre/runtime MUST NOT set final `allowed=True` or `allowed=False`.

## 3. Forbidden patterns

The following patterns are explicitly forbidden:

- Contract failure routed as warnings only.
- Contract violation masked into `allowed=True`.
- Lineage result influencing final decision authority.
- Cross-module consistency mutating `allowed`.
- Multiple final decision owners.
- Shadow-layer override of `ValidationCore._merge()`.
- Contract semantics interpreted outside `ContractRegistry`.
- Trace-level and event-level lineage semantics silently collapsed.

## 4. Enforcement mechanism

Enforcement is TEST-BASED only.

There are no runtime guardrails, new runtime services, schema changes, or
additional production enforcement layers in this lock.

Source of truth:

- `backend/tests/test_validation_architecture_v2_enforcement.py`
- `backend/tests/test_validation_surface_contract.py`
- `backend/tests/test_lineage_semantic_boundary.py`
- `backend/tests/test_controlled_pilot_trace.py`

CI is the enforcement layer. Any change that violates the frozen architecture
must fail through the regression test suite before it reaches controlled pilot
execution.

## 5. Version freeze statement

This architecture represents Validation System v2 frozen semantics.

Any change to contract evaluation, final decision authority, lineage authority,
pre/runtime decision behavior, or cross-module consistency authority requires
re-evaluation through the Controlled Pilot protocol before execution.
