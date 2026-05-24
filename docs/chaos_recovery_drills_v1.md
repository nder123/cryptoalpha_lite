# Chaos Recovery Drills v1 — Stage 1 / Phase 1C / Task S1-08

**Status:** initial freeze (harness + 15 drills)
**Date:** 2026-05-24
**Depends on:** `docs/unified_health_state_machine_v1.md`, `docs/watchdog_recovery_v1.md`, `docs/safe_mode_enforcement_v1.md`
**Closes:** validated survivability gap (recovery semantics move from "design" to "drill-verified")
**Implementation:** `backend/runtime/chaos/harness.py`
**Test surface:** `backend/tests/test_chaos_drills.py`

This task converts the recovery layer from declared into **adversarially validated**.
Every drill is a formal scenario that asserts one recovery invariant. The harness
mocks every external side effect (systemctl, journald, SAFE_MODE flag write,
exchange API) so drills run in `< 1 s` total — they can ride the regular test
suite indefinitely.

---

## 0. Design axiom

```
recovery is unverified until it is drill-bounded
```

A specified recovery semantics that is never exercised under adversarial input
is a hope, not an invariant. v1 drills cover every transition-class invariant
of `unified_health_state_machine_v1.md` plus every budget of `watchdog_recovery_v1.md`.

The harness is intentionally **unit-test class**, not "integration-test class":

- no real systemd unit must be alive;
- no real exchange contact;
- no journald, no fs side effects outside `tmp_path`;
- drills are deterministic on probe sequence + clock + override sequence.

This keeps drill running cost negligible on i3 / 7.5 GiB RAM.

---

## 1. Harness contract

`runtime.chaos.harness.run_drill(...)`:

| Parameter            | Purpose                                                    |
|----------------------|------------------------------------------------------------|
| `tmp_root`           | scratch directory (pytest `tmp_path`); artifact lives here |
| `probe_sequence`     | list of probe vectors; replayed once per iteration         |
| `overrides_sequence` | optional list of `runtime_overrides.json` snapshots        |
| `runtime_mode`       | `OFFLINE` / `SHADOW` / `PAPER` / `LIVE`                    |
| `clock_step_sec`     | how much the synthetic clock advances per iteration        |

Returns `DrillResult` with:

- `final_state` — last state per artifact / transitions log
- `transitions` — list of every `runtime_health_transitions.jsonl` entry
- `restart_attempts` — list of `unit` names the watchdog tried to restart
- `safe_mode_entries` — list of reasons for which `set_safe_mode` was invoked
- `artifact_state` / `artifact_valid` — final `runtime_health.json` parse result
- `iterations` — exact number of probe-vector reads made

The harness drives `runtime.watchdog.loop.run` unchanged with these dependency-
injected callables: probe collector, overrides reader, restart executor, safe-
mode executor, clock, sleeper. No watchdog code is bypassed; the loop's
decision logic is exactly the production logic.

---

## 2. Drill set (v1)

| Id  | Scenario                                                             | Invariant validated                                                                                                  |
|-----|----------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| D1  | single P10 fail                                                      | Tier 2 — coherence break is **immediate CRITICAL**, no hysteresis (state machine §3.1)                              |
| D2  | sustained P5 fail after a green tick                                 | Tier 7 — DEGRADED after `K_soft=3`, then snapshots restart action selected                                          |
| D3  | continuous P5 fail across 30 iterations (1 s steps)                  | Restart budget — `cryptoalpha-snapshots.service` ≤ 3 restarts per 30 min window                                     |
| D4  | LIVE + sustained P8 fail at 60 s/step                                | Tier 4 — STALLED, then escalation to CRITICAL after `T_stall_to_critical=600s`                                       |
| D5  | operator sets `trading_enabled=false` mid-run                        | Tier 1 — SAFE_MODE entry is immediate (no hysteresis)                                                                |
| D6  | δ closure: `SAFE_MODE → HEALTHY`                                     | I-S6 — forbidden direct transition rejected by `assert_allowed`                                                      |
| D7  | sustained P2 fail (API health)                                        | Tier 3 → CRITICAL → recovery action emits `enter_safe_mode`                                                          |
| D8  | 100 iterations, P4 + P5 both failing                                 | Bounded recovery — total restarts ≤ 3 per unit; backend never auto-restarted                                         |
| D9  | sustained P1 fail (backend down)                                     | `FORBIDDEN_AUTORESTART` — backend is NEVER auto-restarted under any chaos                                            |
| D10 | parameterized × 4: all-green, P5-fail, P10-fail, P2-fail             | Artifact integrity — every transition is `runtime_health_transition.v1` schema with valid from/to/trigger            |
| D11 | single-blip P5 surrounded by green ticks                             | Hysteresis — counter resets on green tick; no DEGRADED produced                                                      |
| D12 | adversarial mixed sequence (P5/P10/P2 interleaved)                   | δ closure — every transition produced lies inside `ALLOWED_TRANSITIONS`                                              |

---

## 3. Findings produced by this task

### 3.1 Aggregator fix (now in code)

D2 and D10[seq1] initially failed: the watchdog got stuck in BOOTSTRAPPING.
Per the state machine §4.1, BOOTSTRAPPING exits are `{HEALTHY, CRITICAL,
SAFE_MODE}` only — but the Tier 8 aggregator path returned `prior_state`
unconditionally when not in `{HEALTHY, DEGRADED, STALLED, RECOVERING}`,
leaving BOOTSTRAPPING sticky for any non-CRITICAL probe pattern.

Fix shipped in `runtime/watchdog/aggregator.py`: Tier 8 now also emits

```text
BOOTSTRAPPING + non-CRITICAL probe → HEALTHY  (predicate = "bootstrap_complete")
```

This is the only legal non-failure exit for BOOTSTRAPPING. Soft fails detected
on the same tick do not block the exit — the next tick from HEALTHY will trip
DEGRADED via Tier 7 if persistence warrants it. This preserves all hysteresis
guarantees while making the bootstrap exit terminating.

All 146 Stage-1 tests pass after the fix.

### 3.2 Confirmed invariants (no false positives)

- `(SAFE_MODE, HEALTHY) ∈ FORBIDDEN_DIRECT_TRANSITIONS` — I-S6 enforced;
- `cryptoalpha-backend.service` and `cryptoalpha-watchdog.service` ∈
  `FORBIDDEN_AUTORESTART` — even under sustained P1 fail the backend is
  never restarted by the watchdog (D9);
- recovery budget for each unit is hard-capped to 3 restarts per 30 min and
  never breached across 100 iterations of continuous failure (D3, D8);
- artifact schema is `runtime_health.v1` and every transition record carries
  `runtime_health_transition.v1` schema with non-empty `from`/`to`/`trigger`;
- δ closure holds across an adversarial mixed sequence (D12).

---

## 4. Operating procedure

Drills run as a regular pytest module:

```bash
poetry run pytest tests/test_chaos_drills.py -v
```

Wall-clock: `< 1 s` total (each drill ≤ 100 ms). No fixtures touch real
artifacts. Safe to run on the production-runtime host without precaution.

If a drill fails, by construction one of the following is true:

1. the watchdog deviated from the contract (`unified_health_state_machine_v1.md`
   or `watchdog_recovery_v1.md`);
2. a budget or hysteresis tunable was changed without amending the drill;
3. δ was extended to allow a new transition without updating
   `FORBIDDEN_DIRECT_TRANSITIONS`.

Each cause requires explicit re-entry against the corresponding freeze
document — drills are not relaxed first.

---

## 5. What this task does NOT cover

- live exchange contact under chaos (would require testnet + risk budget;
  out of single-node scope for v1);
- multi-process race conditions (single-instance enforcement via PID lock is
  the only concurrency guard; not adversarially validated here);
- disk failure modes (`P7` returns `unknown` on errors, treated as `pass` for
  non-critical — adequate but not drilled here);
- journald write failures (best-effort in `evidence.py`; not drilled).

These remain candidate scenarios for v2 drills.

---

## 6. Boundary preservation

Added:

- `backend/runtime/chaos/__init__.py` (new)
- `backend/runtime/chaos/harness.py` (new)
- `backend/tests/test_chaos_drills.py` (new — 15 test cases)
- one fix in `backend/runtime/watchdog/aggregator.py` (BOOTSTRAPPING exit; see §3.1)

NOT modified:

- `atp/`, `backend/stress/`, lens lattice
- `backend/runtime/retention/*` — unaffected
- `backend/app/services/trading_gate.py` — unaffected
- kernel contract or any errata

The 174 kernel/lens/stress tests must remain byte-equal in outcome. The
aggregator change is additive (a new path); existing watchdog tests pass
unchanged because none of them started in BOOTSTRAPPING — they all explicitly
seeded HEALTHY/DEGRADED/etc.

---

## 7. Freeze rules

- adding a drill → §2 amended in same change;
- weakening any drill assertion → forbidden; remove the drill if no longer
  applicable, do not soften it;
- new transition class in δ → drill MUST be added to D10/D12 (closure tests);
- changing recovery budgets in `policy.py` (retention) or `recovery.py`
  (watchdog) → corresponding drill thresholds must be updated in the same
  change;
- adding a probe to the watchdog → at least one drill must exercise it.
