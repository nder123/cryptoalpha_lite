# Extension Contract v1

This document defines the permitted extension boundary after Architecture Lock
v2. It describes how future system capabilities may evolve without changing the
controlled validation decision architecture.

## A. Frozen Core

The following components are immutable for Validation System v2:

- `ContractRegistry`
- `ValidationCore`
- `ValidationCore._merge()`
- `CONTRACT_RULES` schema
- `event_lineage` semantics
- `event_contract` semantics
- Architecture authority map

Frozen core components may not be reinterpreted, bypassed, or given secondary
owners by future extension work.

## B. Allowed Future Extensions

Future extensions may observe, annotate, and score system behavior. They may not
change validation authority or final decision semantics.

| Extension | May observe | May annotate | May score | May NOT |
| --- | --- | --- | --- | --- |
| Signal scoring layer | validation outputs, observations, market-derived signals | signal metadata and confidence context | non-authoritative signal strength | modify contract decisions, override `ValidationCore.allowed`, mutate lineage verdicts |
| Regime classification layer | market regime inputs and validation observations | regime labels and context | non-authoritative regime confidence | modify contract decisions, override `ValidationCore.allowed`, mutate lineage verdicts |
| Observability enrichment | traces, warnings, consistency metadata | logs, metrics, trace context | observability completeness and drift indicators | modify contract decisions, override `ValidationCore.allowed`, mutate lineage verdicts |
| Strategy layer | validated decisions and external strategy inputs | strategy intent and rationale | non-authoritative strategy preference | modify contract decisions, override `ValidationCore.allowed`, mutate lineage verdicts |
| PnL analytics layer | executions, fills, and outcome telemetry | analytics metadata and attribution | performance metrics and risk analytics | modify contract decisions, override `ValidationCore.allowed`, mutate lineage verdicts |

Allowed extensions are downstream consumers or side-channel observers. They are
not validation authorities.

## C. Forbidden Extensions

The following extension patterns are explicitly forbidden:

- Second decision owner.
- Contract interpreter duplication.
- Lineage-driven decision authority.
- Cross-module mutation of `allowed`.
- Runtime override of `ValidationCore._merge()`.
- Extension layer that rewrites contract failures as observations.
- Extension layer that changes `ValidationResult` schema.
- Extension layer that changes trace-level or event-level lineage semantics.

## D. Upgrade Path

Future evolution must follow this non-implementation roadmap:

- v2 = validation infrastructure (current)
- v3 = signal intelligence
- v4 = strategy layer
- v5 = production trading layer

Each phase may add capabilities only within its permitted extension boundary.
Advancing from v2 to v3+ requires preserving Architecture Lock v2 and this
Extension Contract v1 unless a new Controlled Pilot review explicitly replaces
them.
