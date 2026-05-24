# Stage 1 Freeze Spec v1

**Status:** frozen baseline
**Date:** 2026-05-24
**Scope:** Production Operationalization (S1-01 through S1-08)
**Cardinality:** L0 execution → L5 causal timeline; 6 frozen layers; 162 passing tests
**Re-entry:** any modification to a frozen artifact requires explicit re-entry against this document per §10.

This document promotes Stage 1 from "in-development operational runtime" to a
**stable baseline** for `cryptoalpha_lite`. After this freeze, any further
work is either:

- Stage 1 errata (small, additive, preserves every invariant in §3–§8); or
- Stage 2+ versioned evolution (separate freeze document; explicit re-entry).

The kernel contract `kernel_contract_freeze_v1.md` is unaffected and orthogonal
to this spec. They commute: Stage 1 lives entirely in the operator plane and
never touches `atp/` or `backend/stress/`.

---

## 0. What this freeze fixes

Stage 1 has produced a **6-layer operational control plane**:

```
L0 execution        backend/app/exchange/bybit_adapter.py
                    backend/app/services/execution_engine.py
L1 gating           backend/app/services/trading_gate.py
                    backend/app/services/runtime_health_reader.py
L2 state machine    backend/runtime/watchdog/
L3 retention        backend/runtime/retention/
L4 chaos drills     backend/runtime/chaos/
L5 causal timeline  backend/runtime/timeline/
```

Plus the supervisor: `ops/systemd-user/*.service` and `*.timer`, the bootstrap
scripts in `scripts/`, and the policy contracts in `docs/`.

What this freeze produces beyond the individual sub-freezes:

- a single navigable index of every frozen artifact;
- explicit cross-references between sub-contracts;
- a single set of invariants no Stage 1+ change may break;
- a single re-entry procedure that supersedes per-document procedures when
  they overlap.

---

## 1. Frozen artifacts — index

### 1.1 Documents (operator plane)

| Document                                          | Owner concern                                 | Sub-task |
|---------------------------------------------------|-----------------------------------------------|----------|
| `docs/runtime_topology_v1.md`                     | what processes exist, how they communicate    | S1-01    |
| `docs/runtime_bootstrap_contract_v1.md`           | env contract, dirs, restart authority, secrets| S1-02    |
| `docs/unified_health_state_machine_v1.md`         | 7 states, δ, hysteresis, evidence schema      | S1-03    |
| `docs/watchdog_recovery_v1.md`                    | recovery action table, budgets, single-writer | S1-04    |
| `docs/safe_mode_enforcement_v1.md`                | gate matrix, choke points, I-S1..I-S7         | S1-05    |
| `docs/retention_cleanup_v1.md`                    | rotation, quota, never-prune, bounded pass    | S1-06    |
| `docs/operational_timeline_v1.md`                 | event schema, merger, causal heuristic        | S1-07    |
| `docs/chaos_recovery_drills_v1.md`                | drill harness, drill set, bugs discovered     | S1-08    |
| `docs/stage1_freeze_v1.md` (this document)        | baseline declaration & re-entry rules         | —        |

### 1.2 Code modules (operator plane)

| Module                                                    | Sub-task | Test file                                  |
|-----------------------------------------------------------|----------|--------------------------------------------|
| `backend/app/services/runtime_health_reader.py`           | S1-05    | `tests/test_safe_mode_enforcement.py`      |
| `backend/app/services/trading_gate.py`                    | S1-05    | `tests/test_safe_mode_enforcement.py`      |
| `backend/runtime/watchdog/states.py`                      | S1-04    | `tests/test_watchdog_states.py`            |
| `backend/runtime/watchdog/aggregator.py`                  | S1-04    | `tests/test_watchdog_aggregator.py`        |
| `backend/runtime/watchdog/recovery.py`                    | S1-04    | `tests/test_watchdog_recovery.py`          |
| `backend/runtime/watchdog/evidence.py`                    | S1-04    | `tests/test_watchdog_evidence.py`          |
| `backend/runtime/watchdog/probes.py`                      | S1-04    | (integration only — exercised by drills)   |
| `backend/runtime/watchdog/loop.py`                        | S1-04    | (integration via chaos drills)             |
| `backend/runtime/retention/policy.py`                     | S1-06    | `tests/test_retention.py`                  |
| `backend/runtime/retention/rotator.py`                    | S1-06    | `tests/test_retention.py`                  |
| `backend/runtime/retention/pruner.py`                     | S1-06    | `tests/test_retention.py`                  |
| `backend/runtime/retention/runner.py`                     | S1-06    | `tests/test_retention.py`                  |
| `backend/runtime/chaos/harness.py`                        | S1-08    | `tests/test_chaos_drills.py`               |
| `backend/runtime/timeline/events.py`                      | S1-07    | `tests/test_timeline.py`                   |
| `backend/runtime/timeline/engine.py`                      | S1-07    | `tests/test_timeline.py`                   |
| `backend/runtime/timeline/cli.py`                         | S1-07    | (smoke-tested via `python -m`)             |

### 1.3 Integration points (in existing files)

| File                                          | Change                                                        | Sub-task |
|-----------------------------------------------|---------------------------------------------------------------|----------|
| `backend/app/exchange/bybit_adapter.py`       | `assert_trading_allowed` at the start of `submit()`           | S1-05    |
| `backend/app/services/execution_engine.py`    | `is_trading_allowed` in `_should_admit_to_submit()`           | S1-05    |
| `backend/app/api/routes.py`                   | 3 new endpoints (`/ops/health-state`, `/ops/runtime-policy`, `/ops/timeline`) | S1-04, S1-05, S1-07 |
| `scripts/bootstrap.sh`                        | retention timer added to `TIMERS` list                        | S1-06    |

### 1.4 Supervisor units

| Unit                                                  | Type      | Sub-task |
|-------------------------------------------------------|-----------|----------|
| `ops/systemd-user/cryptoalpha-backend.service`        | simple    | pre-existing (cleaned in S1-02) |
| `ops/systemd-user/cryptoalpha-snapshots.service`      | simple    | pre-existing |
| `ops/systemd-user/cryptoalpha-recommender.service`    | simple    | pre-existing (cleaned in S1-02) |
| `ops/systemd-user/cryptoalpha-watchdog.service`       | simple    | S1-04    |
| `ops/systemd-user/cryptoalpha-retention.service`      | oneshot   | S1-06    |
| `ops/systemd-user/cryptoalpha-retention.timer`        | timer     | S1-06    |
| `ops/systemd-user/cryptoalpha-duty-check.{service,timer}` | oneshot+timer | pre-existing |
| `ops/systemd-user/cryptoalpha-recommender-events.{service,timer}` | oneshot+timer | pre-existing |
| `ops/systemd-user/cryptoalpha-recommender-alerts.{service,timer}` | oneshot+timer | pre-existing |
| `ops/systemd-user/cryptoalpha-rl-ops-summary.{service,timer}` | oneshot+timer | pre-existing |

### 1.5 Bootstrap & support scripts

| Script                              | Purpose                                            | Sub-task |
|-------------------------------------|----------------------------------------------------|----------|
| `scripts/bootstrap.sh`              | 10-step first-run sequence                         | S1-02    |
| `scripts/start_runtime.sh`          | start long-running units + health check            | S1-02    |
| `scripts/runtime_health.sh`         | 7-probe canonical health probe                     | S1-02    |
| `scripts/support_bundle.sh`         | operator support bundle (tar.zst)                  | S1-02    |

### 1.6 Configuration

| File                                | Purpose                                            |
|-------------------------------------|----------------------------------------------------|
| `.env.template`                     | env contract (9 variables, 2 required)             |
| `docker-compose.optional.yml`       | packaging-optional; never orchestration authority  |

---

## 2. Operational axioms (frozen)

These five statements are the architectural ground truth of Stage 1. Every
sub-contract is consistent with them, and no Stage 1+ change may violate them.

- **A1. Single supervisor.** `systemd --user` is the only mandatory supervisor.
  Docker is packaging-optional. Putting the supervisor inside a container on
  a single-node i3 host is forbidden.
- **A2. Single-writer.** `artifacts/runtime_health.json` and
  `artifacts/runtime_health_transitions.jsonl` have exactly one writer:
  `cryptoalpha-watchdog.service`. Read access is unrestricted.
- **A3. Integrity > uptime.** Coherence breaks (P10 fail) trigger CRITICAL
  immediately, without hysteresis (state machine §3.1 Tier 2).
- **A4. Operator-only exit from SAFE_MODE.** I-S6 — no code path may set
  `trading_enabled` from `false` back to `true` automatically. The δ function
  forbids `SAFE_MODE → HEALTHY` directly.
- **A5. Bounded everything.** Restart budgets, retention passes, drill
  windows, recovery cycles all terminate in finite bytes/files/time.

---

## 3. Frozen contracts

### 3.1 State machine (full reference: `unified_health_state_machine_v1.md`)

```
H = { BOOTSTRAPPING, HEALTHY, DEGRADED, RECOVERING, STALLED, SAFE_MODE, CRITICAL }
|H| = 7
```

The full δ table and forbidden transitions are frozen in
`backend/runtime/watchdog/states.py` (`ALLOWED_TRANSITIONS`,
`FORBIDDEN_DIRECT_TRANSITIONS`). The aggregator tier order (1→8) and the
hysteresis defaults (`K_soft=3 K_critical=3 K_stall=5 K_recover=5
T_stall_to_critical=600s`) are frozen in `aggregator.py`.

### 3.2 Trading gate (full reference: `safe_mode_enforcement_v1.md`)

The 8-row decision matrix (§2.1 of `safe_mode_enforcement_v1.md`) is frozen.
`RECOVERING` is the only state with the `allow_restricted` opt-in path.

Choke points: `BybitExchangeAdapter.submit` (last line) +
`ExecutionEngine._should_admit_to_submit` (admission). Defense-in-depth is
intentional and frozen.

### 3.3 Recovery & restart budgets (full reference: `watchdog_recovery_v1.md`)

- `cryptoalpha-snapshots.service` / `recommender.service`: 3 restarts / 30 min
- any other `cryptoalpha-*` unit: 2 restarts / 15 min
- `FORBIDDEN_AUTORESTART`: `cryptoalpha-backend.service`,
  `cryptoalpha-watchdog.service`
- `N_recover_max=6`, `T_recover_max=600s` per recovery cycle

### 3.4 Retention (full reference: `retention_cleanup_v1.md`)

5 rotation rules, 1 directory quota (4 GiB on `artifacts/`), 4 NEVER_PRUNE
entries, `BoundedPass(max_files=200, max_bytes=2GiB, max_seconds=60,
max_files_to_rotate=20)`. Timer cadence 30 min, `IOSchedulingClass=idle`,
`Nice=10`.

### 3.5 Timeline (full reference: `operational_timeline_v1.md`)

`operational_timeline_event.v1` schema, severity mapping table, heapq-merge
streaming, incident correlator with causal heuristic (§5.1). Hard-cap of 500
events on the `/api/ops/timeline` endpoint by default.

### 3.6 Endpoints

| Endpoint                          | Behavior                                  | Schema                              |
|-----------------------------------|-------------------------------------------|-------------------------------------|
| `GET /api/ops/health-state`       | read-only artifact projection             | `runtime_health.v1`                 |
| `GET /api/ops/runtime-policy`     | derived gate/strategy/recon permissions   | `runtime_policy.v1`                 |
| `GET /api/ops/timeline`           | merged event stream OR incident report    | `operational_timeline.v1` / `operational_incident.v1` |

All three are read-only, return 200 with `stale=true` on missing data, never
5xx for stale conditions.

---

## 4. Test surface (frozen)

| File                                          | Tests | Category                       |
|-----------------------------------------------|-------|--------------------------------|
| `tests/test_stress_harness.py`                | 15    | kernel-adjacent (pre-Stage 1)  |
| `tests/test_watchdog_states.py`               | 32    | δ closure                      |
| `tests/test_watchdog_aggregator.py`           | 14    | tier predicates + hysteresis   |
| `tests/test_watchdog_recovery.py`             | 13    | budgets + action table         |
| `tests/test_watchdog_evidence.py`             | 5     | artifact writer atomicity      |
| `tests/test_safe_mode_enforcement.py`         | 23    | reader + gate + policy         |
| `tests/test_safe_mode_integration.py`         | 7     | bybit_adapter end-to-end       |
| `tests/test_retention.py`                     | 14    | rotator + pruner + runner      |
| `tests/test_chaos_drills.py`                  | 15    | drill set D1..D12              |
| `tests/test_timeline.py`                      | 16    | merger + filters + correlator  |
| **Total**                                     | **154**| Stage 1 (excluding 8 unrelated) |

Plus 8 stress-harness cases pre-dating Stage 1 = **162 total**.

The frozen invariants are:

- **162/162 must pass** byte-equal after every Stage 1 errata.
- The 174 kernel/lens/stress tests of `kernel_contract_freeze_v1.md` must
  remain byte-equal (Stage 1 has never touched `atp/`).

---

## 5. Categories of correctness validated

The Stage 1 test surface establishes three orthogonal correctness classes:

| Class                       | Witness                                        |
|-----------------------------|------------------------------------------------|
| Functional correctness      | gate matrix, action table, endpoints           |
| Survivability correctness   | hysteresis, budgets, retention, drill set      |
| Causal correctness          | timeline merger, incident correlator           |

This is the union that makes the runtime "drill-validated, single-writer,
causally reconstructable".

---

## 6. Invariants no future Stage 1 change may break

- **I-Stage1-1.** δ table is closed under every aggregator output. Verified
  by drill D12.
- **I-Stage1-2.** `(SAFE_MODE, HEALTHY) ∉ ALLOWED_TRANSITIONS`. Verified by
  `test_watchdog_states.py` and drill D6.
- **I-Stage1-3.** `cryptoalpha-backend.service` is never auto-restarted by
  the watchdog under any chaos. Verified by drills D8, D9.
- **I-Stage1-4.** P10 coherence breach yields CRITICAL on the same tick
  (no hysteresis). Verified by drill D1 and `test_watchdog_aggregator.py`.
- **I-Stage1-5.** Trading gate denies in `{BOOTSTRAPPING, STALLED, SAFE_MODE,
  CRITICAL, UNKNOWN}` and allows in `{HEALTHY, DEGRADED}`. Verified by the
  full matrix in `test_safe_mode_enforcement.py`.
- **I-Stage1-6.** Retention pass terminates in `≤ PASS_BUDGET` regardless of
  artifact size or filesystem state. Verified by `test_retention.py`.
- **I-Stage1-7.** `runtime_health_transition.v1` schema is byte-stable across
  every transition record. Verified by drill D10 (×4 parameterizations).
- **I-Stage1-8.** Operational timeline causal chain ordering is chronological.
  Verified by `test_timeline.py::test_correlate_incident_finds_anchor_at_safe_mode`.

---

## 7. What Stage 1 explicitly does NOT include

- multi-instance / federation (Stage 2 candidate);
- ML, strategy logic, RL policy mutation (out of operational plane);
- Kubernetes, Kafka, distributed consensus (out of single-node scope);
- dashboards or web UI (timeline engine is the data layer only);
- journald-native ingestion in timeline (file-based JSONL only in v1);
- automated SAFE_MODE exit (I-S6 is intentional, never closing);
- backend auto-restart (intentional — exchange-side reconciliation risk);
- live exchange chaos drills (testnet/risk-budget concern, out of v1).

Each of these is a candidate Stage 2 task. None is required for Stage 1 to
be considered closed.

---

## 8. Hardware envelope (frozen)

Stage 1 has been designed and validated to remain inside:

| Resource         | Bound                                   |
|------------------|-----------------------------------------|
| CPU              | i3-class single node                    |
| RAM              | ~7.5 GiB                                |
| Storage          | local disk, bounded by retention policy |
| Network          | local + exchange API; no distributed bus|
| Process count    | 3 long-running + 5 oneshot timers       |
| Memory residency | watchdog ~30 MiB, retention 0 between passes |
| API plane        | single uvicorn on `:8000`               |

Any future task that requires expanding this envelope is Stage 2+ by
definition.

---

## 9. Closure conditions (all satisfied)

- [x] every sub-task S1-01..S1-08 has a freeze document in `docs/`
- [x] every long-running unit has `Restart=always` + a `StartLimitBurst`
- [x] every artifact mutating action has structured journald evidence
- [x] every gate denial has structured evidence
- [x] every state transition is replayable from `runtime_health_transitions.jsonl`
- [x] every recovery action is bounded
- [x] every retention pass is bounded
- [x] every drill is deterministic on probe sequence + clock
- [x] every endpoint is read-only and 200-on-stale
- [x] aggregator BOOTSTRAPPING escape hatch exists and is drill-validated
- [x] `kernel_contract_freeze_v1.md` is byte-equal to its v1 state
- [x] 162/162 Stage 1 tests pass

---

## 10. Re-entry rules (override per-document procedures when overlap)

Any change to Stage 1 follows one of three paths.

### 10.1 Errata (small, additive, preserves invariants)

Allowed without re-entry **iff** all of:

- no document in §1.1 is rewritten (only amended in same change);
- no invariant in §6 is broken;
- no axiom in §2 is broken;
- test count in §4 stays equal or grows;
- the 174 kernel tests stay byte-equal in outcome.

Errata are recorded inline in the relevant sub-document under an `## Errata`
section. No new top-level document is required.

### 10.2 Stage 1 amendment (`v1.1`)

Required when an errata cannot fit — e.g., adding a new gate site that needs
its own integration test, or extending the timeline event schema additively.

- bump the affected sub-document to `vN+1`;
- update the cross-reference in this freeze document;
- add corresponding tests; the **162 baseline + new tests** must pass;
- this freeze document is NOT renamed; it grows §1 and §6 in-place.

### 10.3 Stage 2 (`stage2_freeze_v1.md`)

Required when:

- any axiom in §2 must be relaxed; or
- any invariant in §6 must be relaxed; or
- the hardware envelope §8 must be exceeded; or
- multi-instance / federation is introduced; or
- the single-writer invariant (A2) is broken.

Stage 2 is a **new freeze document**, not a successor of this one. They
co-exist; this v1 freeze remains the baseline. Tags / branches separate the
two.

---

## 11. Tag

This freeze is anchored at the repository state where:

- `162/162` Stage 1 tests pass
- aggregator BOOTSTRAPPING escape hatch is present
- `routes.py` exposes 62 routes (3 of them new in S1-04/05/07)
- 5 `*.jsonl` artifact streams are under retention policy
- `chaos_logs.txt` (163 MiB at freeze time) is recognized as overflow candidate
  but not yet rotated (waits for first retention pass post-deploy)

A git tag is the operator's responsibility (`git tag stage1-v1`); this
document is the textual freeze.

---

## 12. Conclusion

Stage 1 closes the foundational operational layer of `cryptoalpha_lite`:

```
governance + recovery + retention + drill + replay
```

— assembled on a single i3 / 7.5 GiB host, supervised by `systemd --user`,
with no distributed infrastructure, no orchestration cluster, no heavy
observability mesh.

The runtime is now a **self-contained operational control plane** with
forensic capability. Any further work is either errata, versioned amendment,
or Stage 2 evolution — never continuation of Stage 1.

End of freeze.
