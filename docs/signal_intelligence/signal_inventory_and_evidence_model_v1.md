# Signal Inventory and Evidence Model v1

This document defines Phase 2.1 terminology for signals and evidence. It is
design-only and does not implement scoring, strategy, trading logic, market
models, runtime behavior, or validation changes.

## A. Signal Definition

A signal is an observable fact.

Examples:

- Volatility increase.
- Liquidity reduction.
- Execution degradation.
- Regime transition.
- Validation anomaly.

A signal is not a decision.

A signal is not a trade.

Signals may describe observed system, market, execution, or validation context.
Signals do not allow, deny, override, or interpret any validation authority.

## B. Evidence Definition

Evidence is one or more signals that support a future interpretation.

Example:

Signals:

- Volatility rising.
- Liquidity falling.

Evidence:

- Unstable market conditions.

Evidence remains observational. It has no authority over contract decisions,
validation outcomes, lineage verdicts, or future execution decisions.

## C. Signal Lifecycle

Conceptual lifecycle:

```text
observation
  -> signal
  -> evidence
  -> future scoring layer
  -> future strategy layer
```

This lifecycle is descriptive only. It does not define implementation modules,
APIs, formulas, scoring models, strategy behavior, or trading logic.

## D. Evidence Authority Rules

Evidence may:

- Describe observed conditions.
- Annotate traces, events, validation outputs, or future signal records.
- Summarize related signals into non-authoritative context.

Evidence may not:

- Allow execution.
- Deny execution.
- Override `ValidationCore`.
- Interpret contracts.
- Modify `ValidationResult`.
- Mutate lineage verdicts.
- Become a second decision owner.

## E. Candidate Signal Catalog

Initial catalog only:

| Signal category | Responsibility |
| --- | --- |
| Regime | Observe broad market state or transition context. |
| Volatility | Observe volatility expansion, contraction, or instability context. |
| Liquidity | Observe spread, depth, slippage, and capacity context. |
| Execution quality | Observe fill quality, latency, degradation, and execution outcome context. |
| Observability health | Observe trace completeness, telemetry coverage, and monitoring health. |
| Validation anomalies | Observe validation irregularities without changing validation authority. |

No formulas, calculations, scoring functions, or market models are defined in
this catalog.

## F. Risks

| Risk | Description | Boundary control |
| --- | --- | --- |
| Evidence inflation | Too many weak or redundant signals can create false interpretive confidence. | Evidence remains observational and non-authoritative. |
| Duplicate signals | Multiple future modules may emit equivalent observations under different names. | Future catalogs should normalize terminology before implementation. |
| Hidden decision authority | Evidence summaries may be treated as allow/deny decisions. | `ValidationCore` remains the only final decision authority. |
| Score creep | Evidence may gradually acquire scoring semantics before the scoring layer is formally defined. | Phase 2.1 forbids scoring implementation and strategy behavior. |

The intended future path is:

```text
signal
  -> evidence
  -> future score
  -> future strategy
```

Validation Infrastructure v2 remains unchanged.
