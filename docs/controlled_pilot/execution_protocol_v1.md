# Controlled Pilot Execution Protocol v1

## A. Execution scope

### Allowed inputs

- A bounded synthetic or testnet-bounded event set.
- Events that conform to the canonical event envelope:
  `event_type`, `trace_id`, `parent_id`, `timestamp`, `source_module`.
- Decision payloads routed through `ValidationCore.evaluate`.
- Contract evaluation routed through `ContractRegistry.evaluate`.
- Lineage projections that keep trace-level and event-level semantics explicit.

### Forbidden inputs

- Unbounded live market event streams.
- Events with missing trace identifiers.
- Decisions that bypass `ValidationCore.evaluate`.
- Contract semantics interpreted outside `ContractRegistry`.
- Mixed lineage projections where `parent_id` semantics are ambiguous.
- Runtime side effects, order placement, storage mutation, or external execution.

### Expected throughput model

- Single bounded trace per wrapper invocation.
- Deterministic synthetic payload size.
- No concurrent execution requirement.
- No throughput optimization target in pilot protocol v1.

## B. Runtime assumptions

### Determinism expectations

- The same bounded input must produce the same contract, lineage, consistency,
  and final decision traces.
- Validation layers must emit stable output shapes.
- The pilot wrapper must not depend on external network, exchange, storage, or
  wall-clock business logic.

### Latency tolerance

- Pilot v1 is correctness-gated, not latency-optimized.
- Any timeout or interruption in the bounded trace is treated as `FAILED`.
- Latency observations are informational until an explicit service-level target
  is defined.

### Failure handling model

- `BLOCKER` hard requirement failures halt pilot admission or execution.
- `DEGRADED` soft observability gaps require explicit operator acknowledgement.
- `OBSERVATIONAL ONLY` signals are recorded but do not halt pilot execution.
- Unexpected exceptions produce `FAILED`.

## C. Monitoring requirements

### Required logs

- Trace log: input event trace identifiers and parent links.
- Lineage log: trace-level lineage result and event-level lineage result.
- Decision log: contract result and final `ValidationCore.evaluate` result.

### Required metrics

- Pass/fail rate for bounded pilot traces.
- Contract violation count.
- Trace-level lineage violation count.
- Event-level lineage violation count.
- Cross-module consistency pass/fail count.
- Drift signals: any change in deterministic output shape for the same input.

### Mandatory artifacts

- Execution trace JSON emitted by `scripts/run_controlled_pilot.py`.
- Readiness JSON emitted by `scripts/check_controlled_pilot_readiness.py`.
- CI evidence for the controlled pilot validation suite.

## D. Stop conditions

AUTO-HALT IF:

- `ContractRegistry` fails or returns invalid contract output for the bounded
  trace.
- Lineage divergence becomes ambiguous rather than explicit.
- Cross-module consistency produces conflicting verdicts.
- `ValidationCore.evaluate` does not produce a final decision.
- The pilot wrapper raises an unexpected exception.

## CONTROLLED PILOT OBSERVABILITY CONTRACT v1

### What must be logged

- Contract trace: contract interpreter result and violation list.
- Lineage trace: trace-level and event-level lineage results.
- Decision trace: final validation decision and any warnings/reasons.
- Consistency trace: individual cross-module consistency check verdicts.

### What must be traceable

- Every event in the bounded input set must have a trace identifier.
- Every event-level lineage node must expose `event_id`, `trace_id`, and
  `parent_id`.
- Every final decision must be attributable to a `ValidationCore.evaluate`
  invocation.
- Every contract decision must be attributable to `ContractRegistry.evaluate`.

### Loss of observability

Loss of observability occurs when any required trace artifact is missing,
non-deterministic, malformed, or cannot be associated with the bounded pilot
input. In pilot v1, loss of observability is at least `DEGRADED`; if it prevents
operator reconstruction of contract, lineage, consistency, or final decision
state, it is a `BLOCKER`.
