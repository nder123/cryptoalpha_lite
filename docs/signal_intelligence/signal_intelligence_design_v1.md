# Signal Intelligence Design v1

This document defines the Phase 2 Signal Intelligence Layer design package. It is
design-only and does not modify Validation Architecture v2, Architecture Lock v2,
or Extension Contract v1.

## A. Purpose

The Signal Intelligence Layer is a future non-authoritative intelligence layer
that may consume validation outputs and external signal context to produce
annotations and scores for later strategy work.

It may:

- Observe validation outputs, execution context, market context, and
  observability signals.
- Classify non-authoritative signal categories.
- Score signal strength, confidence, and quality.
- Annotate traces, events, and future strategy inputs with signal metadata.

It may NOT:

- Change contract decisions.
- Override `ValidationCore`.
- Mutate lineage verdicts.
- Become a second decision owner.
- Interpret `CONTRACT_RULES`.
- Modify final `allowed` outcomes.

## B. Signal Taxonomy

Candidate signal classes are categories only. This design does not implement
calculations, models, scoring formulas, or runtime behavior.

| Signal class | Responsibility |
| --- | --- |
| Market regime signals | Classify broad market state such as trend, range, stress, or transition context. |
| Volatility signals | Describe volatility conditions, expansion/contraction state, and risk context. |
| Liquidity signals | Describe available depth, spread quality, slippage risk, and execution capacity context. |
| Execution quality signals | Describe execution outcomes, fill quality, latency context, and post-trade quality observations. |
| Observability signals | Describe trace completeness, telemetry health, drift indicators, and validation visibility quality. |

All signal classes are non-authoritative. They may enrich downstream
interpretation but cannot decide allow/deny.

## C. Authority Boundaries

Authority boundaries are fixed:

```text
Signal Layer
  -> may produce scores, classifications, and annotations

Validation Layer
  -> owns allow/deny through ValidationCore

Contract Layer
  -> owns semantic correctness through ContractRegistry
```

No authority overlap is allowed.

- Signal Intelligence may observe `ValidationResult` but may not mutate it.
- Signal Intelligence may score observations but may not convert scores into
  validation decisions.
- Signal Intelligence may annotate lineage context but may not change
  `event_lineage` or `event_contract` verdicts.
- Signal Intelligence may feed a future strategy layer but may not bypass
  Validation Architecture v2.

## D. Data Flow

Conceptual future flow:

```text
event
  -> validation
  -> signal observation
  -> signal scoring
  -> future strategy layer
```

Design constraints:

- Validation runs before signal scoring authority is considered.
- Contract failures remain terminal in Validation Architecture v2.
- Signal scores are downstream observations, not validation overrides.
- No runtime changes are introduced by this design.

## E. Future Integration Points

Future modules may attach as non-authoritative consumers:

- Regime classifier: observes market and validation context, annotates regime
  labels, and scores regime confidence.
- Score aggregator: combines non-authoritative signal scores into a downstream
  intelligence summary.
- PnL analytics: observes fills, outcomes, and telemetry to annotate performance
  context.
- Strategy engine: consumes validated decisions and signal intelligence in a
  future phase without changing validation authority.

These are integration points only. This document does not implement modules,
APIs, schemas, scoring logic, strategy logic, market models, or runtime behavior.

## F. Risks

| Risk | Description | Boundary control |
| --- | --- | --- |
| Signal inflation | Too many weak signals can create false confidence. | Scores remain non-authoritative and downstream-only. |
| Authority drift | Signal scores may be treated as validation decisions. | `ValidationCore` remains the only allow/deny authority. |
| Duplicated decision ownership | Future strategy or signal modules may compute competing final decisions. | Extension Contract v1 forbids second decision owners. |
| Hidden contract interpretation | Signal modules may infer or re-check contract semantics. | `ContractRegistry` remains the only contract interpreter. |

Phase 2 may define intelligence concepts only. Any future implementation must
preserve Validation Architecture v2 and pass the controlled pilot governance
suite before execution.
