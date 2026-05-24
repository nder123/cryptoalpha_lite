# Retention & Cleanup Automation v1 — Stage 1 / Phase 1D / Task S1-06

**Status:** initial freeze (contract + implementation)
**Date:** 2026-05-24
**Depends on:** `docs/runtime_bootstrap_contract_v1.md §6`, `docs/watchdog_recovery_v1.md`, `docs/safe_mode_enforcement_v1.md`
**Closes:** GAP-R1 (implementation), GAP-A1 (support bundle still in S1-02 §9)
**Implementation:** `backend/runtime/retention/`
**Process unit:** `ops/systemd-user/cryptoalpha-retention.{service,timer}` (oneshot every 30 min)

This task converts the retention *policy* frozen in S1-02 §6.1 into a *running*
operational survivability layer. Without it, single-node ATP eventually hits
inode growth, fsync latency, SQLite checkpoint pressure, journald amplification,
and degraded startup scans — independent of any specific bug.

---

## 0. Architectural choice

The retention worker is a **periodic oneshot**, not a long-running daemon. On
i3 / 7.5 GiB RAM this matters:

- zero RAM footprint between passes;
- bounded CPU spike per pass (Nice=10, IOSchedulingClass=idle);
- failure of one pass affects only that pass, never blocks the API plane;
- trivially observable through `systemctl --user list-timers`.

The worker NEVER:

- runs concurrently with itself (systemd serializes oneshots per unit);
- exceeds its per-pass byte/file/time budgets;
- deletes files declared NEVER_PRUNE;
- silently removes anything.

---

## 1. Policy (frozen)

All rules live in `backend/runtime/retention/policy.py`. Three categories.

### 1.1 Rotation rules

Size-based rotation with gzip compression. Active file truncated after rotation.

| `rule_id`                       | Path                                                | Rotate at | Keep rotations |
|---------------------------------|-----------------------------------------------------|-----------|----------------|
| `chaos_logs`                    | `chaos_logs.txt`                                    | 50 MiB    | 5              |
| `execution_journal`             | `execution_journal.jsonl`                           | 100 MiB   | 10             |
| `rl_status_snapshots`           | `backend/rl_status_snapshots.jsonl`                 | 50 MiB    | 10             |
| `runtime_health_transitions`    | `artifacts/runtime_health_transitions.jsonl`        | 20 MiB    | 10             |
| `trading_gate_evidence`         | `artifacts/trading_gate_evidence.jsonl`             | 20 MiB    | 10             |

Rotation naming: `<file>.1.gz` (newest) ... `<file>.N.gz` (oldest). On each
rotation:

1. existing `<file>.1.gz` → `<file>.2.gz`, etc., in reverse order;
2. any rotation with index > `keep_rotations` is deleted;
3. current `<file>` is gzipped to `<file>.1.gz`;
4. current `<file>` is truncated to 0 bytes (kept, not removed).

### 1.2 Directory quotas

Total-size cap with oldest-first deletion. Mtime-based ordering.

| `rule_id`        | Path        | Cap            | Keep daily | Keep weekly | Keep monthly |
|------------------|-------------|----------------|-----------|------------|--------------|
| `artifacts_quota`| `artifacts` | 4 GiB (default)| 7         | 4          | 3            |

(`keep_*` parameters are accepted by the policy schema for future periodic
snapshotting; the v1 implementation enforces only the byte cap.)

### 1.3 Never-prune (audit trail)

The worker refuses to delete or rotate anything matching these paths:

| `rule_id`                | Path                                       |
|--------------------------|--------------------------------------------|
| `ci_history_audit`       | `artifacts/ci/history.jsonl`               |
| `runtime_health_current` | `artifacts/runtime_health.json`            |
| `runtime_overrides`      | `runtime_overrides.json`                   |
| `docs_dir`               | `docs/` (entire subtree)                   |

A protected file encountered during quota enforcement is appended to
`PruneResult.skipped_protected` and logged. The pass continues with the next
candidate.

---

## 2. Bounded pass (frozen budget)

`BoundedPass` defaults in `policy.PASS_BUDGET`:

| Field                    | Default       | Purpose                                    |
|--------------------------|---------------|--------------------------------------------|
| `max_files_to_delete`    | 200           | hard cap per pass                          |
| `max_bytes_to_delete`    | 2 GiB         | hard cap per pass                          |
| `max_seconds`            | 60            | wall-clock terminates pass                 |
| `max_files_to_rotate`    | 20            | bound rotation work per pass               |

When any of these is exceeded the pass returns with `budget_exhausted=True` and
records this in the journald summary. The next timer tick continues from where
the previous pass left off (state-free; each pass re-evaluates from scratch).

The whole pass `run_pass()` is guaranteed to terminate.

---

## 3. Process model

### 3.1 Unit pair

`cryptoalpha-retention.service`:

- `Type=oneshot`
- `Nice=10`, `IOSchedulingClass=idle` — never starves the API plane on i3
- `ExecStart=poetry run python -u -m runtime.retention`
- `After=cryptoalpha-backend.service`, `Wants=cryptoalpha-backend.service`

`cryptoalpha-retention.timer`:

- `OnBootSec=10min`
- `OnUnitActiveSec=30min`
- `RandomizedDelaySec=2min` — avoid lockstep with other timers
- `Persistent=true` — catches up if host was off when a tick was due

### 3.2 Bootstrap integration

`scripts/bootstrap.sh` step 9 enables `cryptoalpha-retention.timer` alongside
the other timers (`duty-check`, `recommender-events`, `recommender-alerts`,
`rl-ops-summary`). No manual action required for new installs.

### 3.3 CLI surface

`poetry run python -m runtime.retention` accepts:

- `--dry-run` — evaluate rules without writing or deleting anything; emits a
  summary describing what *would* happen;
- `--json` — emit machine-readable summary to stdout.

Use cases: pre-flight checks, debugging a misbehaving rotation, operator
forensics.

---

## 4. Observability (mandatory)

Every material action writes one structured journald entry with tag
`cryptoalpha-retention`:

| `event`               | Triggered by                                                   |
|-----------------------|-----------------------------------------------------------------|
| `rotation`            | a rotation actually performed (not no-op)                       |
| `quota_enforcement`   | any quota enforcement that deleted files or hit an error        |
| `pass_complete`       | once per pass, with full summary (rotations, totals, exhaustion)|

The summary record schema (`PassSummary.to_dict()`) is stable across v1:

```json
{
  "started_at": 1716553600.0,
  "finished_at": 1716553601.2,
  "duration_sec": 1.2,
  "rotations": [...],
  "quota_results": [...],
  "total_bytes_rotated": 0,
  "total_bytes_pruned": 0,
  "total_files_pruned": 0,
  "budget_exhausted": false,
  "dry_run": false
}
```

Per S1-02 §9, `support_bundle.sh` captures the last 7 days of `cryptoalpha-*`
journald, which inherently includes all retention events.

---

## 5. Test surface

`backend/tests/test_retention.py` — 14 tests:

- **Rotator** (6): rotation thresholds, gz contents, shift-and-drop semantics,
  no-op below threshold, safe behavior on missing file.
- **Pruner** (5): under-cap no-op, oldest-first deletion, never-prune protection,
  budget exhaustion stops mid-pass, `is_never_prune` matrix.
- **Runner** (4): dry-run writes nothing, real pass actually rotates, slow-clock
  termination, empty-repo emits empty summary.

All tests use `tmp_path`; no test touches the real `artifacts/` directory.

---

## 6. Boundary preservation

Added:

- `backend/runtime/retention/*.py` (new package; operator plane)
- `backend/tests/test_retention.py` (new)
- `ops/systemd-user/cryptoalpha-retention.{service,timer}` (new)
- one line in `scripts/bootstrap.sh` to include the new timer

NOT modified:

- `atp/` — kernel and lenses frozen.
- `backend/stress/` — falsifier untouched.
- `backend/runtime/watchdog/*` — watchdog unchanged.
- the kernel contract or any errata.
- the SAFE_MODE enforcement layer.

---

## 7. What this task does NOT do

- does not implement `keep_daily/keep_weekly/keep_monthly` periodic snapshots;
  the policy fields are reserved for future use, the v1 implementation enforces
  only the byte cap;
- does not rotate journald itself (that is host policy);
- does not perform SQLite checkpoint compaction (separate task if it ever becomes
  needed);
- does not delete or compact `frontend/node_modules/` or other gitignored
  build artifacts;
- does not call out to external storage — everything stays on local disk.

---

## 8. Freeze rules

- adding a new path under retention → §1 amended in same change;
- relaxing a NEVER_PRUNE entry → requires explicit re-entry;
- changing `BoundedPass` defaults → §2 amended; tests must remain green;
- adding a new event type → §4 amended; downstream readers must continue to
  parse v1 events;
- changing the timer cadence below 5 min or above 6 h → §3.1 amended.

The kernel contract is unaffected by anything in this document.
