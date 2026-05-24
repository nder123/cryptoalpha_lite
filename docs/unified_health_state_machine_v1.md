# Unified Health State Machine v1 — Stage 1 / Phase 1B / Task S1-03

**Status:** initial freeze (contract only; implementation lands in S1-04 watchdog)
**Date:** 2026-05-24
**Depends on:** `docs/runtime_topology_v1.md`, `docs/runtime_bootstrap_contract_v1.md`
**Closes:** GAP-H1 (contract level)
**Out of scope:** distributed consensus, event bus, Prometheus-first design, complex alert routing

---

## 0. What this document is

A **formal operational algebra** for the runtime: a finite set of states, a partial transition function, an aggregation rule that maps the probe vector defined in S1-02 §5.1 into exactly one state, hysteresis rules to prevent flapping, an evidence schema for every transition, and operator notification thresholds.

It is *not* a UI taxonomy. It is *not* a probe list. It is the algebra against which the watchdog (S1-04), the SAFE_MODE implementation, and every future operator-facing artifact must be implemented.

The kernel contract `kernel_contract_freeze_v1.md` is unaffected. This document lives entirely in the operator plane.

---

## 1. States (finite set `H`)

```
H = { BOOTSTRAPPING, HEALTHY, DEGRADED, RECOVERING, STALLED, SAFE_MODE, CRITICAL }
|H| = 7
```

### 1.1 Definitions

| State           | Meaning                                                                                                  | Trading | Telemetry | Reconciliation |
|-----------------|----------------------------------------------------------------------------------------------------------|---------|-----------|----------------|
| `BOOTSTRAPPING` | Bootstrap sequence (S1-02 §1) is in progress; not all services are up yet                                | off     | partial   | off            |
| `HEALTHY`       | Every critical probe passes; every non-critical probe passes; freshness within bounds                    | on      | on        | on             |
| `DEGRADED`     | Every critical probe passes; at least one non-critical probe fails persistently; runtime coherent       | on (per policy) | on  | on             |
| `RECOVERING`    | Runtime detected and acknowledged a failure; recovery actions in flight; outcome not yet observed       | off     | on        | on             |
| `STALLED`       | A critical observability or decision plane is non-responsive but not crashed; coherence not yet broken  | off     | partial   | on if possible |
| `SAFE_MODE`     | Trading explicitly disabled per I-S1..I-S7 (S1-02 §7); reconciliation/telemetry/recovery continue       | **off**| on        | on             |
| `CRITICAL`      | Coherence threatened, exchange sync impossible, replay inconsistency, or state divergence              | off     | best-effort | best-effort  |

### 1.2 Cardinality property

At any wall-clock instant, the runtime is in **exactly one** state. The state is a pure function of the probe vector and the prior state (for hysteresis). It is not a vector. It is not a set.

---

## 2. Probe vector (input)

Re-uses the 7 probes from `docs/runtime_bootstrap_contract_v1.md §5.1` and extends with three S1-03-only inputs needed for the state algebra:

### 2.1 Existing probes (S1-02)

| Probe id | Source                                                          | Critical? |
|----------|-----------------------------------------------------------------|-----------|
| `P1` | `cryptoalpha-backend.service` active                                | yes       |
| `P2` | `GET /api/health` 2xx ≤ 5 s                                         | yes       |
| `P3` | `cryptoalpha-snapshots.service` active                              | no        |
| `P4` | `cryptoalpha-recommender.service` active                            | no        |
| `P5` | last snapshot ≤ 5 min old                                           | no        |
| `P6` | env file present and mode ≤ 0600                                    | yes       |
| `P7` | disk free ≥ 200 MiB on repo and state dir                           | yes       |

### 2.2 New probes (S1-03)

| Probe id | Source                                                                          | Critical? |
|----------|---------------------------------------------------------------------------------|-----------|
| `P8` | exchange API consecutive successful calls in last 60 s ≥ 1 (when `RUNTIME_MODE ≠ OFFLINE`) | yes for LIVE/PAPER |
| `P9` | reconciliation discrepancy: |internal_view − exchange_view| ≤ tolerance         | yes for LIVE/PAPER |
| `P10`| coherence: most recent `portfolio_invariant` lens run shows zero coherence-class break (per `kernel_contract_freeze_v1.md` §4, excluding `price_completeness`) | yes |

`P8`, `P9`, `P10` are evaluated by the backend itself and exposed via a single new endpoint `GET /api/ops/health-state` (delivered in S1-04). Until that endpoint exists, the state machine evaluates `P8=P9=P10=unknown`, which the algebra treats as the most conservative pessimistic value per §3.

### 2.3 Probe value domain

Each probe returns one of `{pass, fail, unknown}`. `unknown` is treated as `fail` for critical probes and as `pass` for non-critical probes, except where §3 explicitly overrides.

---

## 3. Aggregation rule (probe vector → state)

Aggregation is **stratified**: each tier is evaluated in order; the first matching tier determines the state. This eliminates ambiguity and makes the algebra deterministic.

```
Tier 1.  Manual override                       → BOOTSTRAPPING | SAFE_MODE
Tier 2.  Hard coherence break                  → CRITICAL
Tier 3.  Critical infrastructure failure       → CRITICAL
Tier 4.  Reconciliation impossible             → STALLED  (may escalate to CRITICAL — see §4)
Tier 5.  Observability plane stalled           → STALLED
Tier 6.  Recovery in progress (sticky)         → RECOVERING
Tier 7.  Non-critical degradation              → DEGRADED
Tier 8.  Everything green                      → HEALTHY
```

### 3.1 Tier predicates (precise)

- **Tier 1 — BOOTSTRAPPING.** `runtime_overrides.json: bootstrap_in_progress = true` OR `bootstrap.sh` is still inside steps 1–9.
- **Tier 1 — SAFE_MODE.** `runtime_overrides.json: trading_enabled = false` AND (`safe_mode_reason` is set OR `RUNTIME_MODE ∈ {LIVE, PAPER}`). Note: SAFE_MODE is **never** auto-exited per I-S6.
- **Tier 2 — CRITICAL (coherence).** `P10 = fail`. Any coherence-class divergence triggers immediate CRITICAL regardless of other probes.
- **Tier 3 — CRITICAL (infrastructure).** Any of `P1`, `P2`, `P6`, `P7` is `fail` for ≥ `K_critical` consecutive evaluations (default `K_critical = 3`).
- **Tier 4 — STALLED (reconciliation).** `RUNTIME_MODE ∈ {LIVE, PAPER}` AND `P8 = fail` for ≥ `K_stall` consecutive evaluations (default `K_stall = 5`). If this persists ≥ `T_stall_to_critical` (default 10 min), escalate to CRITICAL.
- **Tier 5 — STALLED (observability).** `P3 = fail` OR `P5 = fail` for ≥ `K_stall` consecutive evaluations.
- **Tier 6 — RECOVERING (sticky).** Prior state ∈ `{DEGRADED, STALLED}` AND recovery action emitted in last `T_recovery_window` (default 60 s) AND outcome not yet observable.
- **Tier 7 — DEGRADED.** Any non-critical probe is `fail` for ≥ `K_soft` consecutive evaluations (default `K_soft = 3`).
- **Tier 8 — HEALTHY.** All probes pass, all critical probes pass, no Tier 1–7 condition met.

### 3.2 Mode awareness

In `RUNTIME_MODE = OFFLINE`, `P8` and `P9` are forced to `pass` (no exchange contact expected). In `RUNTIME_MODE = SHADOW`, `P9` is forced to `pass` (no orders, nothing to reconcile). The aggregator must read `RUNTIME_MODE` from the env at every evaluation.

---

## 4. Transition function

Transitions are a partial function `δ : H × ProbeVector → H`. Only the pairs below are valid.

### 4.1 Allowed transitions

```
BOOTSTRAPPING  → HEALTHY            (bootstrap.sh step 10 success)
BOOTSTRAPPING  → CRITICAL           (bootstrap.sh step 8 exit 1)
BOOTSTRAPPING  → SAFE_MODE          (operator intervention during bootstrap)

HEALTHY        → DEGRADED           (Tier 7 met)
HEALTHY        → STALLED            (Tier 4 or 5 met)
HEALTHY        → CRITICAL           (Tier 2 or 3 met)
HEALTHY        → SAFE_MODE          (operator OR auto-trigger per S1-02 §7.2)

DEGRADED       → HEALTHY            (Tier 8, after K_recover consecutive HEALTHY evaluations)
DEGRADED       → RECOVERING         (recovery action emitted)
DEGRADED       → STALLED            (escalation)
DEGRADED       → CRITICAL           (escalation)
DEGRADED       → SAFE_MODE          (operator OR auto-trigger)

STALLED        → DEGRADED           (cause cleared partially)
STALLED        → RECOVERING         (recovery action emitted)
STALLED        → CRITICAL           (Tier 4 escalation timer elapsed, or Tier 2/3)
STALLED        → SAFE_MODE          (auto-trigger per S1-02 §7.2)

RECOVERING     → HEALTHY            (Tier 8, after K_recover consecutive HEALTHY evaluations)
RECOVERING     → DEGRADED           (partial success)
RECOVERING     → STALLED            (recovery insufficient)
RECOVERING     → CRITICAL           (recovery exhausted; see §4.3)
RECOVERING     → SAFE_MODE          (auto-trigger)

SAFE_MODE      → RECOVERING         (operator clears `trading_enabled = true` AND probes warrant it)
SAFE_MODE      → CRITICAL           (Tier 2 or 3 met while in SAFE_MODE)
SAFE_MODE      → SAFE_MODE          (idempotent — operator confirms staying)

CRITICAL       → SAFE_MODE          (operator-only)
CRITICAL       → RECOVERING         (operator-only, with explicit override flag + reason)
CRITICAL       → CRITICAL           (idempotent)
```

### 4.2 Forbidden transitions

The following are **never** legal and must be rejected by the implementation:

- `CRITICAL → HEALTHY` directly (must pass through RECOVERING with operator override)
- `SAFE_MODE → HEALTHY` directly (must pass through RECOVERING — closes I-S6)
- `STALLED → HEALTHY` directly (must pass through DEGRADED or RECOVERING)
- `BOOTSTRAPPING → DEGRADED | STALLED | RECOVERING` (bootstrap either succeeds → HEALTHY, or fails → CRITICAL/SAFE_MODE)
- any auto-transition that ends in HEALTHY from a state that crossed CRITICAL since last HEALTHY without an explicit operator-acknowledged recovery event

Forbidden transitions are not warnings. They are contract violations. The watchdog (S1-04) must refuse them.

### 4.3 Recovery exhaustion

`RECOVERING → CRITICAL` is mandatory when **any** of:

- recovery attempts in the current cycle ≥ `N_recover_max` (default `6`);
- elapsed time in `RECOVERING` ≥ `T_recover_max` (default 10 min);
- a coherence-class invariant break is observed during recovery (`P10 = fail`).

---

## 5. Hysteresis

Every state change requires evidence accumulation, not a single failing evaluation. This prevents flapping.

| Pattern                        | Required consecutive evaluations |
|--------------------------------|----------------------------------|
| HEALTHY → DEGRADED             | `K_soft = 3`                     |
| HEALTHY → STALLED              | `K_stall = 5`                    |
| HEALTHY → CRITICAL             | `K_critical = 3`                 |
| DEGRADED → HEALTHY             | `K_recover = 5`                  |
| RECOVERING → HEALTHY           | `K_recover = 5`                  |
| STALLED → CRITICAL (Tier 4)    | `T_stall_to_critical = 10 min`   |
| any → SAFE_MODE (operator)     | immediate (no hysteresis)        |
| any → CRITICAL (coherence P10) | immediate (no hysteresis)        |

The aggregator evaluates probes at a fixed cadence (default 10 s; tunable per env var `RUNTIME_HEALTH_INTERVAL_SEC`). `K_*` counts consecutive evaluations at that cadence.

Two transitions are explicitly **immediate** (no consecutive-N gate): operator-triggered SAFE_MODE entry and coherence breach (P10). The cost of a false positive on these is bounded; the cost of a false negative is unbounded.

---

## 6. Evidence schema

Every state transition writes exactly one structured record. The record is the *only* authoritative source for "why did we enter X" questions.

### 6.1 Record schema (v1)

```json
{
  "schema": "runtime_health_transition.v1",
  "transition_id": "uuid",
  "ts": "ISO8601 with timezone",
  "from": "HEALTHY",
  "to": "DEGRADED",
  "trigger": {
    "tier": 7,
    "predicate": "non_critical_probe_persistent_fail",
    "probes": {"P3": "pass", "P4": "pass", "P5": "fail"}
  },
  "consecutive_evaluations": 3,
  "elapsed_in_from_state_sec": 12480,
  "evidence": {
    "snapshot_last_age_sec": 412,
    "snapshot_threshold_sec": 300
  },
  "operator_acknowledged": false,
  "recovery_actions": []
}
```

### 6.2 Write targets

A transition record is written to **all three** of the following atomically (ordering: 1, 2, 3 — failures in 2 or 3 do not block 1):

1. **journald** with tag `cryptoalpha-health` (priority depends on `to`-state — see §7);
2. append to `artifacts/runtime_health_transitions.jsonl` (rotated per S1-02 §6.1);
3. update `artifacts/runtime_health.json` to reflect the new current state (§8).

### 6.3 Mandatory fields

A record missing any of `transition_id`, `ts`, `from`, `to`, `trigger`, `evidence` is malformed and must be rejected at write time. The watchdog will refuse to commit the transition.

### 6.4 Replayability requirement

The full sequence of transition records in `artifacts/runtime_health_transitions.jsonl` must be sufficient to reconstruct the state at any past wall-clock instant. The aggregator is therefore deterministic on `(transition_history, probe_history) → state`. Probe history is logged at a coarser cadence (sampled, not every tick) but transitions are logged exhaustively.

---

## 7. Operator notification policy

Notifications go through journald (operator reads via `journalctl`); the alerting plane already routes priority `alert` via `cryptoalpha-recommender-alerts.service`-style dedup. v1 extends that mechanism to health transitions.

### 7.1 Notification matrix

| Transition target | journald priority | Operator notified?                 |
|-------------------|-------------------|------------------------------------|
| HEALTHY           | `info`            | only if previous state was CRITICAL or SAFE_MODE |
| BOOTSTRAPPING     | `info`            | no (expected on cold start)        |
| DEGRADED          | `notice`          | only if duration in DEGRADED ≥ `T_notify_degraded` (default 15 min) |
| RECOVERING        | `notice`          | no (intermediate, transient)       |
| STALLED           | `warning`         | yes, with dedup window 5 min       |
| SAFE_MODE         | `alert`           | yes, immediate, no dedup           |
| CRITICAL          | `crit`            | yes, immediate, no dedup           |

### 7.2 Dedup contract

A dedup state file at `~/.cache/cryptoalpha/health_alert_last.txt` stores the last alerted `(to_state, sha256_of_trigger)` pair. A duplicate within the dedup window is suppressed (one journald `info`-priority "suppressed duplicate" record is still written for audit).

### 7.3 What is NOT notified

- HEALTHY → DEGRADED → HEALTHY within 5 min (transient blip);
- RECOVERING → HEALTHY (success is implicit; the prior alert chain already informed the operator);
- intermediate probe failures that do not cross hysteresis thresholds.

The policy is intentionally **silent on noise** and **loud on consequence**. False-quiet on transient blips is preferable to alert fatigue.

---

## 8. Runtime artifact: `artifacts/runtime_health.json`

The aggregator maintains a single JSON file containing the **current** state. Last-writer-wins; readers must tolerate brief inconsistency during write (or use the journald stream).

### 8.1 Schema (v1)

```json
{
  "schema": "runtime_health.v1",
  "state": "DEGRADED",
  "since": "2026-05-24T13:11:42+03:00",
  "previous_state": "HEALTHY",
  "transition_id": "uuid",
  "reasons": ["snapshot_lag", "exchange_stale"],
  "probes": {
    "P1": "pass", "P2": "pass", "P3": "pass",
    "P4": "pass", "P5": "fail", "P6": "pass", "P7": "pass",
    "P8": "fail", "P9": "unknown", "P10": "pass"
  },
  "recovery_mode": false,
  "trading_enabled": true,
  "runtime_mode": "PAPER",
  "operator_acknowledged": false,
  "next_evaluation_at": "2026-05-24T13:11:52+03:00",
  "evaluation_cadence_sec": 10
}
```

### 8.2 Fields

| Field                     | Meaning                                                                              |
|---------------------------|--------------------------------------------------------------------------------------|
| `state`                   | one of the 7 values in §1                                                            |
| `since`                   | wall-clock entry into `state`                                                        |
| `previous_state`          | the state held immediately before                                                    |
| `transition_id`           | uuid linking this artifact to the corresponding record in `runtime_health_transitions.jsonl` |
| `reasons`                 | short symbolic codes (e.g. `snapshot_lag`, `exchange_stale`, `coherence_break`, `disk_pressure`, `env_mode_loose`) |
| `probes`                  | the probe vector as last evaluated                                                   |
| `recovery_mode`           | true iff `state = RECOVERING` OR a recovery action emitted within last 60 s          |
| `trading_enabled`         | mirror of `runtime_overrides.json: trading_enabled`                                  |
| `runtime_mode`            | mirror of `RUNTIME_MODE` env var                                                     |
| `operator_acknowledged`   | true once operator has read/ack'd this transition (via API in S1-04)                 |
| `next_evaluation_at`      | when the aggregator will run next                                                    |
| `evaluation_cadence_sec`  | `RUNTIME_HEALTH_INTERVAL_SEC`                                                        |

### 8.3 Atomicity

The file is written via `write → fsync → rename` in `artifacts/`. Partial writes are forbidden. Readers seeing an unparsable file fall back to journald.

---

## 9. Tunables (frozen defaults)

The implementation must accept env-var overrides for these; the defaults are part of the contract until amended via this document.

| Env var                              | Default | Purpose                                    |
|--------------------------------------|---------|--------------------------------------------|
| `RUNTIME_HEALTH_INTERVAL_SEC`        | `10`    | aggregator cadence                         |
| `RUNTIME_HEALTH_K_SOFT`              | `3`     | consecutive evals to enter DEGRADED        |
| `RUNTIME_HEALTH_K_CRITICAL`          | `3`     | consecutive evals to enter CRITICAL (Tier 3)|
| `RUNTIME_HEALTH_K_STALL`             | `5`     | consecutive evals to enter STALLED         |
| `RUNTIME_HEALTH_K_RECOVER`           | `5`     | consecutive evals to exit DEGRADED/RECOVERING into HEALTHY |
| `RUNTIME_HEALTH_T_STALL_CRITICAL_SEC`| `600`   | STALLED → CRITICAL escalation               |
| `RUNTIME_HEALTH_T_RECOVER_MAX_SEC`   | `600`   | recovery exhaustion timer                  |
| `RUNTIME_HEALTH_N_RECOVER_MAX`       | `6`     | recovery attempt budget per cycle          |
| `RUNTIME_HEALTH_T_NOTIFY_DEGRADED_SEC`| `900`  | DEGRADED dwell time before operator notify |

---

## 10. What S1-03 does NOT deliver

The contract is frozen. The implementation lands in:

- **S1-04 — Watchdog & Recovery Orchestration** — implements the aggregator, the transition writer, the artifact updater, the operator-notification routing, and the `GET /api/ops/health-state` endpoint. The watchdog is the **only** process allowed to write `artifacts/runtime_health.json` and `runtime_health_transitions.jsonl`.
- **S1-05 — SAFE_MODE implementation** — closes I-S1..I-S7 in code, hooked into the state machine via Tier 1 entry and the explicit operator-only exit gate.
- **Phase 1D — retention** — rotation of `runtime_health_transitions.jsonl` per S1-02 §6.1.

---

## 11. Boundary preservation

This document does not touch:

- `atp/` — kernel and lenses remain frozen per `kernel_contract_freeze_v1.md`;
- `backend/stress/` — the falsifier remains an external observer;
- the kernel's invariant set `I-K1..8`, `I-L1..7` — they are referenced (via P10) but not amended.

The state machine is a pure operator-plane construct. It observes the kernel through one read-only lens (`portfolio_invariant`) and never invokes it as a writer.

---

## 12. Freeze rules

- adding a state → expands `H`; requires updating §1, §4 (transitions to/from), §7 (notification);
- adding a probe → updating §2, §3;
- changing a tier predicate → §3.1;
- changing a hysteresis threshold → §5 default in this document AND §9 env var name preserved;
- changing the artifact schema → bump `schema` field in §6.1 and §8.1 to `v2`; v1 readers must continue to parse `v1` records.

The kernel contract is unaffected by anything here. Any change to this state machine that does not also amend this document is an **undocumented operational regression** by definition.
