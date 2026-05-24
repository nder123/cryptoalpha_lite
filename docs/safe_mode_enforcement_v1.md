# SAFE_MODE Enforcement v1 — Stage 1 / Phase 1C / Task S1-05

**Status:** initial freeze (contract + reference integration)
**Date:** 2026-05-24
**Depends on:** `docs/unified_health_state_machine_v1.md`, `docs/watchdog_recovery_v1.md`
**Closes:** GAP-S1 (I-S1 implementation), I-S2..I-S5 (preserve recon/telemetry/recovery during SAFE_MODE)

This task converts SAFE_MODE from "a flag in JSON" into a **runtime-wide
execution contract** enforced at every order-emitting choke point.

---

## 0. Authority and scope

The runtime health state, owned by the watchdog (S1-04), is the **sole authority**
that determines whether trading-class actions are permitted. Every order-emitting
code path MUST consult that authority before any external side effect.

The kernel contract `kernel_contract_freeze_v1.md` is unaffected. This task lives
entirely in the operator/execution plane.

---

## 1. Runtime Authority Reader

`backend/app/services/runtime_health_reader.py` exposes a thread-safe read-only
projection of `artifacts/runtime_health.json`:

- `RuntimeHealthReader.read()` → `RuntimeHealthSnapshot` with fields:
  `state`, `since`, `previous_state`, `transition_id`, `reasons`, `probes`,
  `recovery_mode`, `trading_enabled`, `runtime_mode`, `stale`, `stale_reason`,
  `transition_age_sec`, `coherence_break_count`, `safe_mode_active`.
- Falls back to last-good snapshot when the file is briefly missing during the
  watchdog's atomic rename. Returns `state="UNKNOWN"` only when nothing has ever
  been read successfully.
- `get_default_reader()` — module-level singleton (lazy).
- `set_default_reader_for_tests(reader)` — explicit test injection.

The reader makes **no decisions** and **never raises** on I/O.

---

## 2. Trading Gate

`backend/app/services/trading_gate.py`:

- `is_trading_allowed(reader=None, allow_restricted=False) -> GateDecision`:
  pure read; never raises; use to branch.
- `assert_trading_allowed(component, attempted_action, reader=None,
  allow_restricted=False, evidence_sink=None) -> GateDecision`:
  raises `TradingNotAllowed` on denial. Always emits evidence (admit or deny).
- `derive_policy(snapshot) -> RuntimePolicy`: maps health → `{trading_allowed,
  strategy_allowed, reconciliation_allowed, observability_allowed}`.

### 2.1 Decision matrix (frozen)

| State          | Trading            | Strategy   | Reconciliation | Observability |
|----------------|--------------------|------------|----------------|---------------|
| `HEALTHY`      | allowed            | allowed    | allowed        | allowed       |
| `DEGRADED`     | allowed            | allowed    | allowed        | allowed       |
| `RECOVERING`   | restricted (default deny) | denied | allowed        | allowed       |
| `BOOTSTRAPPING`| denied             | denied     | allowed        | allowed       |
| `STALLED`      | denied             | denied     | allowed        | allowed       |
| `SAFE_MODE`    | **denied**         | denied     | **allowed (I-S2)** | **allowed (I-S3)** |
| `CRITICAL`     | denied             | denied     | best-effort    | best-effort   |
| `UNKNOWN`/stale| denied             | denied     | (operator)     | allowed       |

`RECOVERING` is `restricted`: `is_trading_allowed(allow_restricted=True)` permits
it; default is denial. This is the only state where a caller may opt-in.

### 2.2 Failure semantics

- denial path: `TradingNotAllowed` raised; evidence appended to
  `artifacts/trading_gate_evidence.jsonl` (one line per denial).
- admit path: best-effort log, no jsonl persistence (high-volume).
- never silent. Never returns "allowed" on parse error.

---

## 3. Hard SAFE_MODE enforcement (integration sites)

### 3.1 Primary choke points (this task)

- **`BybitExchangeAdapter.submit`** (`backend/app/exchange/bybit_adapter.py`) —
  last line of defense before `BybitClient.place_order`. Calls
  `assert_trading_allowed(component="bybit_adapter", ...)`.
- **`ExecutionEngine._should_admit_to_submit`** (`backend/app/services/execution_engine.py`) —
  queue admission gate. Calls `is_trading_allowed()` and refuses admission
  when denied (logs warning; request stays in queue, will be expired).

### 3.2 Required follow-up sites (declared, not yet integrated here)

These code paths MUST also call `assert_trading_allowed(...)` before emitting
orders or mutating exposure. They are explicitly listed so future PRs can
close them one by one without re-discovery:

- `backend/app/services/position_manager.*` — any open/close position path
- `backend/app/services/auto_exposure_manager.py`
- `backend/app/services/rl_autopilot.py`
- `backend/app/services/shadow_trading_orchestrator.py` — optional (shadow path
  is observation; integration documents intent)
- `backend/app/services/risk_guard.py` — already a gate; should additionally
  consult `is_trading_allowed()` before authorizing exposure increase

Each future PR adding integration MUST also extend
`backend/tests/test_safe_mode_integration.py` with a test that proves the
denial reaches that path.

### 3.3 Defense in depth

The two primary gates are independent. The `bybit_adapter` gate fires even if
the upstream admission gate is bypassed (e.g. a future code path that calls
the adapter directly). This is intentional: integrity > performance.

---

## 4. Runtime-wide freeze semantics

While in `SAFE_MODE`, the runtime preserves I-S1..I-S7:

- **I-S1** (no new orders): enforced by §3.1 gates.
- **I-S2** (reconciliation continues): `derive_policy(...).reconciliation_allowed = True`.
- **I-S3** (telemetry continues): snapshots, journald, ledger appends are not
  gated by health state — never call `assert_trading_allowed` from those paths.
- **I-S4** (recovery attempts continue): the watchdog loop is unaffected by its
  own SAFE_MODE conclusions; recovery dispatch keeps running per `select_action`.
- **I-S5** (entry observable): the watchdog writes one transition record on
  every entry; the gate writes one denial record per attempted execution.
- **I-S6** (exit operator-only): the watchdog never sets `trading_enabled=true`;
  the state machine forbids `SAFE_MODE → HEALTHY` directly.
- **I-S7** (exit observable): every exit transition writes a record.

Forbidden in SAFE_MODE:

- emitting orders;
- mutating exposure / leverage;
- promoting strategies;
- changing risk posture in a direction that would increase exposure.

Allowed in SAFE_MODE:

- reading state;
- writing telemetry;
- closing positions via operator command (operator-only path);
- recovery actions in scope of S1-04 §3.

---

## 5. Recovery semantics

Exit from SAFE_MODE follows the state machine §4.1: `SAFE_MODE → RECOVERING`
only, never directly to HEALTHY. The watchdog's `assert_allowed` enforces this
at the transition boundary; the gate enforces it at every execution boundary.

Operator action that flips `runtime_overrides.json: trading_enabled=true` while
the underlying probes are still bad will be observed by the next watchdog tick,
which will re-enter SAFE_MODE per Tier 1.

---

## 6. API projection

`GET /api/ops/runtime-policy` (added in `backend/app/api/routes.py`) returns:

```json
{
  "schema": "runtime_policy.v1",
  "state": "SAFE_MODE",
  "trading_allowed": false,
  "strategy_allowed": false,
  "reconciliation_allowed": true,
  "observability_allowed": true,
  "entered_at": "2026-05-24T13:00:00+03:00",
  "reason": "coherence_break",
  "stale": false
}
```

Read-only. Never raises 5xx for stale data. Mirrors the `runtime_health.json`
mtime liveness contract from S1-04 §7.

---

## 7. Evidence

### 7.1 Schema (`trading_gate_evidence.jsonl`, append-only)

```json
{
  "event": "execution_denied",
  "reason": "state_safe_mode",
  "state": "SAFE_MODE",
  "component": "bybit_adapter",
  "attempted_action": "submit_Market_Buy_BTCUSDT",
  "stale": false,
  "ts": 1716553600.123
}
```

Single-writer is the trading_gate module. Readers may tail safely.

### 7.2 Retention

Phase 1D will rotate this jsonl per S1-02 §6.1. Until then, append-only.

---

## 8. Test surface

- `backend/tests/test_safe_mode_enforcement.py` — reader (file missing,
  unparsable, last-good fallback, schema fields), gate (matrix per §2.1,
  raise-on-denial, evidence emission), policy projection (I-S2..I-S5
  preservation under SAFE_MODE/CRITICAL).
- `backend/tests/test_safe_mode_integration.py` — `BybitExchangeAdapter.submit`
  end-to-end: SAFE_MODE / CRITICAL / STALLED / missing artifact → raises;
  HEALTHY / DEGRADED → reaches stub client.

Both test files inject readers via `set_default_reader_for_tests` and reset
the module-level singleton in an autouse fixture, so they cannot leak state
across the rest of the suite.

---

## 9. What this task does NOT do

- does not gate every order-emitting path (see §3.2 follow-up checklist);
- does not implement operator-controlled exit UI (Phase 1B/UI);
- does not retain `trading_gate_evidence.jsonl` (Phase 1D);
- does not test the watchdog → gate end-to-end loop (separate chaos drill in
  S1-08).

---

## 10. Boundary preservation

Modified files:

- `backend/app/services/runtime_health_reader.py` (new)
- `backend/app/services/trading_gate.py` (new)
- `backend/app/exchange/bybit_adapter.py` (gate inserted; behavior is identical
  in HEALTHY/DEGRADED, denied otherwise)
- `backend/app/services/execution_engine.py` (admission gate inserted in
  `_should_admit_to_submit`)
- `backend/app/api/routes.py` (new endpoint `/api/ops/runtime-policy`)
- `backend/tests/test_safe_mode_enforcement.py` (new)
- `backend/tests/test_safe_mode_integration.py` (new)

NOT modified:

- `atp/` — kernel and lenses remain frozen.
- `backend/stress/` — falsifier remains an external observer.
- the kernel contract or its errata.
- the watchdog (`backend/runtime/watchdog/*`) — gate reads its output, never
  the other way around.

The 174 kernel/lens/stress tests must remain byte-equal in outcome.

---

## 11. Freeze rules

- adding a new gate site → §3.2 amended; integration test added in same change;
- changing the §2.1 matrix → requires explicit re-entry against this freeze
  (it directly encodes I-S1..I-S7);
- changing the evidence schema → bump `event` field schema and document v2;
  v1 readers must continue to parse v1 records;
- relaxing `RECOVERING` default-deny semantics → re-entry only.
