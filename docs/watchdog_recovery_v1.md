# Watchdog & Recovery Orchestration v1 — Stage 1 / Phase 1C / Task S1-04

**Status:** initial freeze (contract + reference implementation)
**Date:** 2026-05-24
**Depends on:** `docs/runtime_topology_v1.md`, `docs/runtime_bootstrap_contract_v1.md`, `docs/unified_health_state_machine_v1.md`
**Closes:** GAP-W1, GAP-S1 (implementation), GAP-H1 (writer side)
**Implementation:** `backend/runtime/watchdog/`
**Process unit:** `ops/systemd-user/cryptoalpha-watchdog.service`

---

## 0. Authority and scope

The watchdog is the **operational state executor**, not a restart daemon. Its authority is bounded.

### 0.1 Allowed (operator plane)

- read probes from systemd, the API plane, the filesystem;
- evaluate the state machine defined in `docs/unified_health_state_machine_v1.md`;
- write `artifacts/runtime_health.json` (atomic);
- append to `artifacts/runtime_health_transitions.jsonl`;
- emit journald events with tag `cryptoalpha-watchdog`;
- restart, stop, or start `cryptoalpha-*` units **except** `cryptoalpha-watchdog.service` itself;
- toggle `runtime_overrides.json: trading_enabled` (entry into SAFE_MODE only — exit is operator-only per I-S6);
- emit operator notifications per `unified_health_state_machine_v1.md §7`.

### 0.2 Forbidden (kernel plane and beyond)

- mutate `atp/` state in any way;
- write to `execution_journal.jsonl`;
- bypass `risk/` or `execution/` decisions;
- mutate strategy, policy, or RL state;
- exit SAFE_MODE automatically (closes I-S6);
- restart itself.

The kernel contract `kernel_contract_freeze_v1.md` is unaffected by anything the watchdog does.

---

## 1. Single-writer invariant (frozen)

Two artifacts have **exactly one** authorized writer in the entire runtime:

| Artifact                                            | Writer                                  |
|-----------------------------------------------------|-----------------------------------------|
| `artifacts/runtime_health.json`                     | `cryptoalpha-watchdog.service`          |
| `artifacts/runtime_health_transitions.jsonl`        | `cryptoalpha-watchdog.service`          |

Any other process attempting to write either file is a contract violation. Read access is unrestricted.

The API endpoint `GET /api/ops/health-state` is a **read-only projection** of `artifacts/runtime_health.json`. It is not source of truth. If the file is missing or unparsable, the endpoint returns `{state: "UNKNOWN", stale: true}`.

---

## 2. Loop semantics

```
loop:
  1. collect probe vector P
  2. compute candidate state H' = aggregate(P, prior_state, counters, mode, overrides)
  3. if H' == prior_state: update probes-only, sleep, continue
  4. validate transition (prior_state → H') is allowed (§4.1 of state machine doc)
  5. emit transition record (atomic: jsonl append + json rename + journald)
  6. dispatch recovery actions per §3 (bounded)
  7. update operator notification dedup state
  8. sleep(RUNTIME_HEALTH_INTERVAL_SEC)
```

The loop is single-threaded and synchronous. It MUST be killable by `SIGTERM` within `TimeoutStopSec=10`.

---

## 3. Recovery action table

Each state declares a small, frozen set of allowed recovery actions. The watchdog dispatches at most **one** action per loop iteration to bound side effects.

| State          | Allowed action                             | Cost  | Budget                                   |
|----------------|--------------------------------------------|-------|------------------------------------------|
| `HEALTHY`      | none                                       | n/a   | n/a                                      |
| `BOOTSTRAPPING`| none (bootstrap.sh owns this state)        | n/a   | n/a                                      |
| `DEGRADED`     | `restart_unit(cryptoalpha-snapshots.service)` if P5 fail | low   | ≤ 3 restarts / 30 min                    |
| `DEGRADED`     | `restart_unit(cryptoalpha-recommender.service)` if P4 fail | low | ≤ 3 restarts / 30 min                    |
| `RECOVERING`   | observe-only (wait for resolution)         | none  | bounded by `RUNTIME_HEALTH_T_RECOVER_MAX_SEC` |
| `STALLED`      | `restart_unit(<stalled non-critical unit>)` | low  | ≤ 2 restarts / 15 min per unit           |
| `STALLED`      | escalate to CRITICAL after `T_stall_to_critical` | n/a | timer-driven                             |
| `SAFE_MODE`    | none — observe only, ensure trading_enabled=false | none | n/a                                |
| `CRITICAL`     | enter SAFE_MODE (set trading_enabled=false), notify operator | high | once per CRITICAL entry          |

Forbidden actions in every state:

- restarting `cryptoalpha-backend.service` automatically (operator-only — backend restart can lose in-flight reconciliation);
- restarting `cryptoalpha-watchdog.service` (would orphan the loop);
- writing to `runtime_overrides.json` outside the SAFE_MODE entry path;
- any action while `trading_enabled = true` if it would cancel orders or mutate exchange state (watchdog never touches the exchange).

---

## 4. Recovery budgets (frozen defaults)

Budgets prevent restart storms and operator spam.

| Budget                                              | Default          |
|-----------------------------------------------------|------------------|
| max restarts of `cryptoalpha-snapshots.service`     | 3 per 30 min     |
| max restarts of `cryptoalpha-recommender.service`   | 3 per 30 min     |
| max restarts of any other `cryptoalpha-*` unit      | 2 per 15 min     |
| max recovery attempts in single RECOVERING cycle    | `N_recover_max=6` (mirrors §4.3 of state machine doc) |
| max time in RECOVERING                              | `T_recover_max=10 min`                         |
| operator alert dedup window (per state)             | 5 min            |

When a budget is exhausted, the watchdog escalates to the next state (typically CRITICAL) rather than continuing to retry. Exhaustion itself is a transition record with `trigger.predicate = "budget_exhausted"`.

---

## 5. Evidence contract

Every transition writes one record to all three of:

- `artifacts/runtime_health_transitions.jsonl` (append, fsync per record group)
- `artifacts/runtime_health.json` (write-temp + fsync + rename)
- journald via `systemd-cat -t cryptoalpha-watchdog`

Schema is exactly the one in `unified_health_state_machine_v1.md §6.1` and §8.1. The watchdog also includes its own `pid`, `loop_iteration`, and `since_last_transition_sec` fields for forensics.

A failed write to one target does NOT block the other two. Order of writes is jsonl → json → journald. journald is best-effort.

---

## 6. Process model

### 6.1 systemd unit

`ops/systemd-user/cryptoalpha-watchdog.service`:

- `Type=simple`
- `Restart=always`, `RestartSec=5`
- `StartLimitIntervalSec=60`, `StartLimitBurst=10`
- depends on `cryptoalpha-backend.service` (After/Wants)
- runs `python -u -m runtime.watchdog` from `backend/`
- inherits env from `~/.config/cryptoalpha/env`

### 6.2 Lifecycle

- starts after `bootstrap.sh` step 9 (timers section), as a 4th long-running unit
- on `SIGTERM`: writes one final transition record `<state> → SHUTTING_DOWN` (a transient internal state, not in `H`; serialized only as a journald event) and exits 0
- on `SIGKILL`: artifact may be stale; readers must check `mtime`

### 6.3 Single-instance enforcement

Only one watchdog instance per host is allowed. Enforced by:

- systemd unit semantics (single `Type=simple`);
- a PID lock file at `~/.local/state/cryptoalpha/watchdog.pid`;
- a refusal to start if another live PID holds the lock.

---

## 7. API endpoint (read-only projection)

`GET /api/ops/health-state` is added to `backend/app/api/ops.py`. Response:

```json
{
  "schema": "runtime_health.v1",
  "state": "...",
  "since": "...",
  "...": "...",
  "stale": false,
  "stale_reason": null
}
```

`stale=true` (with `stale_reason`) when:

- file missing → `stale_reason="file_missing"`
- file unparsable → `stale_reason="parse_error"`
- file `mtime` older than `2 × RUNTIME_HEALTH_INTERVAL_SEC` → `stale_reason="watchdog_silent"`

The endpoint never returns 5xx for stale data. It always returns 200 with `stale=true` so monitoring can distinguish "watchdog dead" from "API dead".

The endpoint requires `X-Operator-Key` header in production modes (LIVE/PAPER); free in OFFLINE/SHADOW. (Mirror of existing `cryptoalpha-duty-check` auth pattern.)

---

## 8. Test surface

Reference implementation lives in `backend/runtime/watchdog/`. Tests in `backend/tests/test_watchdog_*.py` cover at minimum:

- **states**: every `δ` allowed transition is reachable; every forbidden transition is rejected;
- **aggregator**: each tier predicate fires under its declared probe pattern; mode-awareness (`OFFLINE`/`SHADOW`) forces `P8`/`P9` to `pass`; immediate transitions (P10 break, operator SAFE_MODE) bypass hysteresis;
- **hysteresis**: HEALTHY → DEGRADED requires `K_soft` consecutive failing evals; HEALTHY → DEGRADED → HEALTHY-within-1-eval is suppressed;
- **recovery budget**: 4th restart of snapshots within 30 min is refused; budget exhaustion produces `budget_exhausted` transition.

Tests are pure: aggregator, transitions, and budget logic are extracted as pure functions / classes with injected dependencies. The actual systemd / curl / fs side effects are exercised only by the loop integration test (skipped in CI by default).

---

## 9. What this task does NOT close

- **GAP-S1 (full SAFE_MODE invariants in code)**: I-S2..I-S5 (reconciliation continues, telemetry continues, recovery attempts continue, observability of triggers) — the watchdog supplies the entry path, but the backend code paths that respect `trading_enabled=false` for I-S1 must be audited in S1-05.
- **Unified UI** for health state — Phase 1B finishing.
- **Retention** of `runtime_health_transitions.jsonl` — Phase 1D.
- **External-to-host watchdog** (e.g. cron-based watcher of the watchdog) — out of scope; single-node.

---

## 10. Boundary preservation

This task adds:

- `backend/runtime/watchdog/*.py` (new; operator plane)
- `backend/tests/test_watchdog_*.py` (new)
- `ops/systemd-user/cryptoalpha-watchdog.service` (new)
- one new endpoint in `backend/app/api/ops.py` (read-only projection)
- one new artifact path family under `artifacts/` (single-writer)

It does NOT modify:

- `atp/`
- `backend/stress/`
- the lens lattice
- any kernel test
- the kernel contract or its errata

All 174 kernel/lens/stress tests must continue to pass byte-equal after this task.

---

## 11. Freeze rules

- adding a recovery action → §3 amended in same change;
- changing a budget default → §4 amended;
- new probe entering aggregator → propagate to `unified_health_state_machine_v1.md §2`;
- changing the artifact schema → bump `schema` field in §5 to `v2`; v1 readers must continue to parse v1 records;
- adding endpoint behavior → §7 amended;
- changing the single-writer set in §1 → requires explicit re-entry against this freeze.
