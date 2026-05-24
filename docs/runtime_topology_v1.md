# Runtime Topology v1 — Stage 1 / Phase 1A / Task S1-01

**Status:** initial freeze of the **observed** runtime
**Date:** 2026-05-24
**Scope:** describes the runtime exactly as it exists today on the operator's host. Nothing aspirational. Anything not present in the codebase is listed in §8 (gaps), not in the body.

This document is the operational control surface definition required by the Stage 1 roadmap. It is the canonical reference that subsequent tasks (Compose foundation, watchdog, unified health, retention) must conform to or explicitly amend.

---

## 0. Truth source for this document

Every claim below is derivable from one of:

- `ops/systemd-user/*.service`
- `ops/systemd-user/*.timer`
- `ops/rl_ops_summary.sh`
- `system.py` (repo-root CLI)
- `backend/app/main.py` (FastAPI app)
- `backend/scripts/rl_*.py`
- on-disk artifact directories

If a claim is not derivable from the above, it is in §8, not here.

---

## 1. Process inventory

The runtime is currently driven by **systemd --user** (per-operator units). There is no Docker Compose stack yet; that is a Stage 1 / Phase 1A.2 deliverable, not a current fact.

### 1.1 Long-running services (`Type=simple`, `Restart=always`)

| Unit                                  | Process                                                                                | Bound to            |
|---------------------------------------|----------------------------------------------------------------------------------------|---------------------|
| `cryptoalpha-backend.service`         | `poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000`                           | TCP `:8000`         |
| `cryptoalpha-snapshots.service`       | `python -u scripts/rl_snapshots_collect.py --url http://127.0.0.1:8000/api/rl/status --interval 60` | file               |
| `cryptoalpha-recommender.service`     | `python -u scripts/rl_promotion_recommender.py --api-base http://127.0.0.1:8000 ...`   | journald (stdout)   |

### 1.2 Periodic oneshots (`Type=oneshot` + timer)

| Unit                                            | Cadence                | Effect                                                                                  |
|-------------------------------------------------|------------------------|-----------------------------------------------------------------------------------------|
| `cryptoalpha-duty-check.service` + `.timer`     | `OnUnitActiveSec=20min`| `curl http://127.0.0.1:8000/api/ops/duty-check` (with `X-Operator-Key` if set)          |
| `cryptoalpha-recommender-events.service` + `.timer` | `OnUnitActiveSec=5min` | greps last 10 min of recommender journal for `PROMOTE_/ROLLBACK_/NOT_RECOMMENDED`       |
| `cryptoalpha-recommender-alerts.service` + `.timer` | `OnUnitActiveSec=5min` | dedup alert via `~/.cache/cryptoalpha/rl_alert_last.txt`, emit `cryptoalpha-rl-alert` to journald at priority `alert` |
| `cryptoalpha-rl-ops-summary.service` + `.timer`     | `OnUnitActiveSec=12h`  | `ops/rl_ops_summary.sh` heartbeat into journald                                         |

### 1.3 CLI-triggered (operator on-demand) — `system.py`

| Subcommand                            | Underlying command                                                                                       |
|---------------------------------------|----------------------------------------------------------------------------------------------------------|
| `system.py pr`                        | `backend/tools/production_hardening_pipeline_v1.py --kinds pack`                                         |
| `system.py nightly [--update-baseline]` | `backend/tools/production_hardening_pipeline_v1.py --kinds live,pack`                                  |
| `system.py observe --window 7d`       | `backend/tools/stability_report_v1.py`                                                                   |
| `system.py status`                    | reads `artifacts/ci/{pr,nightly}/*.json`, `artifacts/observability/stability_report_v1.json`, `artifacts/ci/history.jsonl` |
| `system.py ui [--host --port]`        | `backend/tools/system_dashboard_server_v1.py`                                                            |
| `system.py regenerate-causal --session-ref` | `backend/tools/regenerate_causal_map_v1.py`                                                        |

### 1.4 Frontend / UI

`frontend/` and `ui/` exist as repo subtrees. Their runtime invocation is not wired into systemd today; UI is launched manually via `system.py ui` or directly. **Not part of the supervised topology yet.**

---

## 2. Communication model

```
                       operator
                          │
                          ▼
          ┌──── system.py (CLI, repo root) ────┐
          │                                     │
          │                                     │
          ▼                                     ▼
     backend/tools/*                    HTTP /api/* on :8000
     (one-shot processes)               (FastAPI / uvicorn)
                                              │
                                              │ HTTP poll (60 s)
                                              ▼
                              cryptoalpha-snapshots ──────► backend/rl_status_snapshots.jsonl
                                              │
                                              │ HTTP poll (60 s)
                                              ▼
                              cryptoalpha-recommender ────► journald
                                                                  │
                              ┌───────────────────────────────────┤
                              │                                   │
                              ▼                                   ▼
                  cryptoalpha-recommender-events       cryptoalpha-recommender-alerts
                  (journald digest, 5 min)             (journald dedup → priority=alert)

                              ▲
                              │ /api/ops/duty-check
                              │
                  cryptoalpha-duty-check (20 min)
```

### 2.1 Channels in use

| Channel                | Producer → Consumer                                                                  |
|------------------------|--------------------------------------------------------------------------------------|
| **HTTP localhost:8000**| backend ⟷ snapshots / recommender / duty-check / `system.py status`                  |
| **filesystem**         | backend ↔ `artifacts/`, `snapshots/`, `execution_journal.jsonl`, `runtime_overrides.json` |
| **journald (user)**    | every long-running service writes stdout/stderr; oneshots read it via `journalctl --user` |
| **state files (~/.cache/cryptoalpha/)** | alert dedup (`rl_alert_last.txt`)                                          |
| **env file**           | `~/.config/cryptoalpha/env` (`EnvironmentFile=-...`), shared by services and `ops/rl_ops_summary.sh` |
| **exchange API / WS**  | called from inside backend process (no separate worker today)                        |

### 2.2 Channels NOT in use

- no IPC / shared memory
- no message broker
- no inter-container network (no containers)
- no separate websocket worker process

---

## 3. Failure domains

### 3.1 Domain map

| Domain                         | Members                                                                                                  | Blast radius                                |
|--------------------------------|----------------------------------------------------------------------------------------------------------|---------------------------------------------|
| **API plane**                  | `cryptoalpha-backend.service` + uvicorn worker process                                                   | every other unit (all depend on `:8000`)    |
| **Observation plane**          | `cryptoalpha-snapshots.service`                                                                          | RL snapshot continuity only                 |
| **Decision plane**             | `cryptoalpha-recommender.service`                                                                        | RL promotion signals only                   |
| **Alerting plane**             | `cryptoalpha-recommender-{events,alerts}.service`, `cryptoalpha-duty-check.service`, `cryptoalpha-rl-ops-summary.service` | operator visibility only           |
| **Storage plane**              | `artifacts/`, `snapshots/`, `execution_journal.jsonl`, `backend/rl_status_snapshots.jsonl`, `chaos_logs.txt` | recoverability of evidence               |
| **Operator credentials plane** | `~/.config/cryptoalpha/env` (`OPERATOR_API_KEY`, etc.)                                                   | duty-check & rl-ops-summary auth            |

### 3.2 Severity classification (current, observed)

- **Local degradation** — snapshots stalls, recommender stalls, single oneshot timer fail. API plane keeps serving.
- **Recoverable** — backend crash → systemd restarts (`Restart=always`, `RestartSec=3`, `StartLimitBurst=20 / 60s`).
- **Critical** — API plane unavailable for longer than `StartLimitBurst` window: every dependent oneshot starts erroring, recommender enters its `ExecStartPre` retry loop (120 × 1 s).
- **Operator-required** — env file missing, port 8000 occupied by another process, exchange credentials revoked, journald disabled. Currently no automated detection.

### 3.3 Known broken references in `[Unit]` directives

The following unit names appear in `After=` / `Wants=` clauses but **do not exist** in `ops/systemd-user/`:

- `cryptoalpha-docker-deps.service` — referenced by `cryptoalpha-backend.service`
- `cryptoalpha-runtime-patch.service` — referenced by `cryptoalpha-recommender.service`

systemd silently tolerates references to absent units (they are treated as not-yet-loaded, not as hard errors), so this does not block startup today, but it is an **operational debt** item: either the units must be created and frozen here, or the references must be removed.

→ Tracked in §8 as **GAP-T1**.

---

## 4. Restart semantics

### 4.1 Effective policy per unit

| Unit                                  | Type      | Restart   | RestartSec | Other                                      |
|---------------------------------------|-----------|-----------|------------|--------------------------------------------|
| `cryptoalpha-backend.service`         | simple    | always    | 3 s        | `StartLimitIntervalSec=60 StartLimitBurst=20`, `KillMode=control-group`, `TimeoutStopSec=10`, `SendSIGKILL=yes` |
| `cryptoalpha-snapshots.service`       | simple    | always    | 3 s        | —                                          |
| `cryptoalpha-recommender.service`     | simple    | always    | 3 s        | `ExecStartPre` waits up to 120 s for `/api/health` |
| `cryptoalpha-duty-check.service`      | oneshot   | (n/a)     | (n/a)      | timer-driven                               |
| `cryptoalpha-recommender-events.service` | oneshot| (n/a)     | (n/a)      | timer-driven                               |
| `cryptoalpha-recommender-alerts.service` | oneshot| (n/a)     | (n/a)      | timer-driven                               |
| `cryptoalpha-rl-ops-summary.service`  | oneshot   | (n/a)     | (n/a)      | timer-driven                               |

### 4.2 Implicit guarantees

- **Auto-restart**: backend / snapshots / recommender; rate-limited only on backend.
- **No restart**: oneshots — a failed run prints to journald and waits for next timer tick. There is no per-attempt retry beyond that.
- **No degraded-mode entry**: nothing in the unit graph today flips runtime into a "trading disabled" state on backend stall. Trading-disable semantics are an unfreezed gap (→ GAP-D1).
- **No operator-required gating**: a backend crash loop will retry 20 × per 60 s and then enter `auto-restart` failure; nothing escalates to the operator beyond journald.

### 4.3 What is NOT yet defined

- a uniform `HEALTHY / DEGRADED / STALLED / RECOVERING / CRITICAL / SAFE_MODE` state machine for the runtime as a whole (Phase 1B);
- a watchdog that observes liveness from outside the API plane (Phase 1C);
- safe-mode trigger when reconciliation fails (Phase 1C).

---

## 5. Artifact ownership

Each artifact has exactly one writer in this topology. Any future producer must declare itself here.

| Artifact path (repo-relative)                       | Writer                                              | Reader(s)                                       | Retention today |
|-----------------------------------------------------|-----------------------------------------------------|-------------------------------------------------|-----------------|
| `backend/rl_status_snapshots.jsonl`                 | `cryptoalpha-snapshots.service`                     | `system.py status`, ad-hoc analysis             | unbounded       |
| `execution_journal.jsonl` (repo root)               | backend                                             | tooling, replay                                 | unbounded       |
| `runtime_overrides.json`                            | operator (manual) / backend (writes when amended)   | backend on startup                              | unbounded       |
| `artifacts/ci/pr/result.json`                       | `system.py pr`                                      | `system.py status`, CI gates                    | unbounded       |
| `artifacts/ci/nightly/ci_summary.json`              | `system.py nightly`                                 | `system.py status`                              | unbounded       |
| `artifacts/ci/history.jsonl`                        | `backend/tools/ci_history_append_v1.py` (via `system.py`) | `system.py status`                        | unbounded       |
| `artifacts/observability/stability_report_v1.json`  | `system.py observe`                                 | `system.py status`                              | unbounded       |
| `artifacts/<YYYY-MM-DD>/...`                        | various tooling                                     | various                                         | unbounded       |
| `snapshots/*.json`                                  | scripted experiments                                | replay tooling                                  | unbounded       |
| `chaos_logs.txt` (currently 163 MB)                 | chaos run scripts                                   | post-mortem only                                | unbounded       |
| journald `--user` entries                           | every long-running service                          | every oneshot, operator                         | systemd default |
| `~/.cache/cryptoalpha/rl_alert_last.txt`            | `cryptoalpha-recommender-alerts.service`            | itself                                          | overwritten     |
| `~/.config/cryptoalpha/env`                         | operator                                            | every unit, `ops/rl_ops_summary.sh`             | manual          |

**Observation:** retention is *unbounded* on every filesystem artifact today. `chaos_logs.txt` at 163 MB is symptomatic. This is a Phase 1D problem (not addressed in this freeze).

→ Tracked in §8 as **GAP-R1**.

---

## 6. Health surface (current)

The only structured health endpoint today is `GET /api/health` on the backend. Liveness signals consumed by oneshots:

- `GET /api/health` — used by `cryptoalpha-recommender.service ExecStartPre`
- `GET /api/ops/duty-check` — used by `cryptoalpha-duty-check.service`
- `GET /api/rl/status` — polled by `cryptoalpha-snapshots.service` and inspected by `ops/rl_ops_summary.sh`

There is **no aggregated health view** that says "the whole runtime is healthy / degraded / stalled". Each consumer infers state independently from its own narrow probe.

→ unified health is the Phase 1B deliverable. The state set declared in the roadmap (`HEALTHY / DEGRADED / STALLED / RECOVERING / CRITICAL / SAFE_MODE`) is **not yet implemented** in any unit, endpoint, or file.

---

## 7. Process graph (start-up dependencies, observed)

```
cryptoalpha-backend.service
    │   After=cryptoalpha-docker-deps.service        ← MISSING (GAP-T1)
    │
    ├──► cryptoalpha-snapshots.service               (After/Wants backend)
    │
    └──► cryptoalpha-recommender.service             (After/Wants backend, snapshots, runtime-patch ← MISSING)
              │   ExecStartPre: 120×1s curl /api/health
              │
              ├──► cryptoalpha-recommender-events.service   (timer 5 min, reads journald)
              ├──► cryptoalpha-recommender-alerts.service   (timer 5 min, reads journald)
              └──► cryptoalpha-rl-ops-summary.service       (timer 12 h, reads /api/* + journald)

cryptoalpha-duty-check.service                       (timer 20 min, After backend)
```

There is no enforced ordering between snapshots, recommender events, alerts, and rl-ops-summary beyond their independent `After=cryptoalpha-backend.service`.

---

## 8. Gaps explicitly NOT closed by this freeze

These are recorded so the next phases reference them by ID, not re-discover them.

| ID       | Gap                                                                                                               | Closes in     |
|----------|-------------------------------------------------------------------------------------------------------------------|---------------|
| **GAP-T1** | `cryptoalpha-docker-deps.service` and `cryptoalpha-runtime-patch.service` are referenced but absent              | Phase 1A.2 / Compose foundation, **or** unit removal |
| **GAP-D1** | No `Docker Compose` stack; runtime is host-systemd today                                                          | Phase 1A.2    |
| **GAP-B1** | No `bootstrap.sh / start.sh / health.sh / support_bundle.sh`                                                      | Phase 1A.3    |
| **GAP-E1** | No `.env.template`; env contract is implicit in `~/.config/cryptoalpha/env`                                       | Phase 1A.4    |
| **GAP-H1** | No unified health surface (state machine over the 6 declared states)                                              | Phase 1B      |
| **GAP-W1** | No watchdog process external to the API plane; `Restart=always` is the only liveness mechanism                    | Phase 1C      |
| **GAP-S1** | No safe-mode contract; nothing flips trading off automatically on stall / reconciliation failure                  | Phase 1C      |
| **GAP-R1** | No retention or rotation; `chaos_logs.txt` is 163 MB, `artifacts/` has 849 entries, all unbounded                 | Phase 1D      |
| **GAP-U1** | `frontend/` and `ui/` are not under supervision; UI lifecycle is operator-manual                                  | Phase 1B / 1C |
| **GAP-A1** | No defined "support bundle" archive contract                                                                      | Phase 1D      |

---

## 9. Freeze rules for this document

This freeze is **descriptive**, not prescriptive. It says what is, not what should be. Subsequent task documents may:

- add new units → must update §1, §2, §3, §4, §5;
- add new artifacts → must update §5;
- change a `[Unit]` directive → must update §3.3 and §7;
- introduce a state machine, watchdog, safe-mode → close the corresponding GAP-* and update §6.

Any change to the runtime that does not also amend this document is an **undocumented operational regression** by definition.

The kernel contract (`docs/kernel_contract_freeze_v1.md`) is unaffected by anything in this document. Stage 1 work is operator-plane only and never touches `atp/`, `backend/stress/`, or the lens lattice.

---

## 10. Next task

`Phase 1A.2 — Docker Compose foundation` and the closure of **GAP-T1**, **GAP-D1**, **GAP-B1**, **GAP-E1**.

The Compose stack must, at minimum, materialize the units enumerated in §1.1 and §1.2 as containers (or explicitly justify keeping them on host systemd), and produce the four bootstrap scripts named in **GAP-B1**.

Until then, the runtime topology of record is the one frozen in this document.
