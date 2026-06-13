# Signal Layer Stabilization Contract v1

This document freezes the purity and isolation rules for future signal-layer
work. It is design/governance only and introduces no runtime behavior, scoring,
strategy, or validation changes.

## A. Core Principle

Signals are never decisions.

Signals are never preferences.

Signals are never actions.

Signals describe observable facts only. They do not select, authorize, deny,
rank, prefer, or execute anything.

## B. Signal Purity Rule

A signal must be:

- Observable.
- Atomic.
- Non-interpreted.

Forbidden signal forms:

- "signal indicates buy"
- "signal suggests denial"
- "signal implies action"

A valid signal states what was observed, not what should be done.

## C. Evidence Constraint

Evidence may:

- Aggregate signals.
- Describe state.

Evidence may not:

- Change the decision layer.
- Compete with `ValidationCore`.
- Influence `allowed`.
- Convert observations into authority.

Evidence remains observational even when it aggregates multiple signals.

## D. Signal Isolation Rule

A signal MUST NOT reference:

- Contracts.
- `allowed` / `denied`.
- Lineage decisions.
- `validation_core` output.

Signals must remain isolated from validation authority. They may describe
observable external or system-local facts, but they may not embed validation
state or decision semantics.

## E. Temporal Rule

Signals are time-local observations.

Signals must not encode future expectation.

Forbidden temporal forms:

- "risk will increase"
- "system will fail"
- "market will collapse"

Allowed temporal forms:

- "volatility increased"
- "latency spiked"

The signal layer records what has been observed, not what is predicted.

## F. Signal Composition Rule

Allowed:

- Combining signals into evidence.

Forbidden:

- Deriving scoring logic.
- Assigning weights.
- Ranking signals.

Composition may organize observations, but it may not create scoring authority
or strategy preference.

## G. Forbidden Leakage Patterns

The following leakage patterns are forbidden:

- Signal -> decision shortcut.
- Signal -> implicit trade logic.
- Signal -> contract interpretation.
- Signal -> hidden strategy.
- Signal -> validation override.
- Signal -> action preference.

Any future signal-layer work must preserve signal purity, evidence
observational status, and Validation Architecture v2 authority boundaries.
