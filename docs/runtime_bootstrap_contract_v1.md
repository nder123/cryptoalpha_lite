# Runtime Bootstrap Contract v1 — Stage 1 / Phase 1A.2 / Task S1-02

**Status:** initial freeze
**Date:** 2026-05-24
**Depends on:** `docs/runtime_topology_v1.md`
**Closes:** GAP-T1 (already removed), groundwork for GAP-B1, GAP-E1, GAP-R1, GAP-S1
**Hardware target:** single-node, i3-class CPU, ~7.5 GiB RAM
**Supervisor of record:** `systemd --user`. Docker is **packaging-optional**, never orchestration authority.

---

## 0. Architectural axiom

```
systemd --user  =  supervisor (mandatory)
docker compose  =  packaging   (optional)
```

`docker compose` may carry **auxiliary** services (Postgres, Prometheus, Grafana). It must **never** assume responsibility for the API plane, the snapshots collector, the recommender, or any oneshot timer. Putting the supervisor inside Docker on a single-node i3 host is a pure liability. This is non-negotiable for v1.

---

## 1. Bootstrap order (mandatory sequence)

```
1.  env contract        — ~/.config/cryptoalpha/env exists & has required vars
2.  directories         — repo dirs + ~/.cache/cryptoalpha, ~/.local/state/cryptoalpha
3.  Python deps         — poetry install in backend/
4.  database / state    — sqlite (or future postgres) reachable & migrated
5.  systemd unit link   — symlinks installed under ~/.config/systemd/user/
6.  supervisor reload   — systemctl --user daemon-reload
7.  service start       — backend → snapshots → recommender (in order)
8.  health validation   — runtime_health.sh returns 0
9.  timer enablement    — duty-check, recommender-{events,alerts}, rl-ops-summary
10. ready               — runtime declares bootstrap-complete via journald
```

Steps 1–6 are **idempotent and reversible**. Steps 7–10 are **observable**: every transition writes to journald with tag `cryptoalpha-bootstrap`. Bootstrap is *successful* iff `scripts/runtime_health.sh` returns 0 within 120 s of step 7.

---

## 2. Environment contract

### 2.1 Authoritative source

`~/.config/cryptoalpha/env`. Loaded by every service via `EnvironmentFile=-%h/.config/cryptoalpha/env` and by `ops/rl_ops_summary.sh`.

### 2.2 Variables

A `.env.template` is committed at repo root and kept in sync with this section. `bootstrap.sh` copies it to `~/.config/cryptoalpha/env` on first run if absent.

| Variable                       | Required  | Used by                                        | Notes                                          |
|--------------------------------|-----------|------------------------------------------------|------------------------------------------------|
| `OPERATOR_API_KEY`             | yes       | duty-check, rl-ops-summary, dashboard          | shared secret operator ↔ backend               |
| `EXCHANGE_API_KEY`             | yes (live)| backend                                        | live trading credential — never in repo        |
| `EXCHANGE_API_SECRET`          | yes (live)| backend                                        | live trading credential — never in repo        |
| `EXCHANGE_TESTNET`             | no        | backend                                        | `1` to force testnet                           |
| `RUNTIME_MODE`                 | yes       | backend                                        | one of `OFFLINE`, `SHADOW`, `PAPER`, `LIVE`    |
| `RUNTIME_DATA_DIR`             | no        | backend, scripts                               | default `~/.local/state/cryptoalpha`           |
| `RUNTIME_ARTIFACTS_QUOTA_MB`   | no        | retention worker (Phase 1D)                    | default `4096` (4 GiB)                         |
| `RUNTIME_LOG_QUOTA_MB`         | no        | retention worker (Phase 1D)                    | default `512`                                  |
| `RUNTIME_LOG_LEVEL`            | no        | backend                                        | default `INFO`                                 |

### 2.3 Secrets contract

- secrets are **never** committed (`.env*` in `.gitignore`);
- secrets are **never** logged at any level;
- a missing required secret causes `bootstrap.sh` to fail at step 1 with explicit message;
- rotating a secret = edit env file, then `systemctl --user restart cryptoalpha-backend.service`.

---

## 3. Directory contract

| Path                                 | Owner              | Purpose                                       | Quota (Phase 1D)             |
|--------------------------------------|--------------------|-----------------------------------------------|------------------------------|
| `<repo>/artifacts/`                  | tooling            | CI / chaos / observability artifacts          | `RUNTIME_ARTIFACTS_QUOTA_MB` |
| `<repo>/snapshots/`                  | scripted runs      | replay snapshots                              | shared with `artifacts/`     |
| `<repo>/execution_journal.jsonl`     | backend            | append-only execution journal                 | rotated, see §6              |
| `<repo>/chaos_logs.txt`              | chaos scripts      | chaos run output                              | rotated, see §6              |
| `<repo>/runtime_overrides.json`      | operator + backend | runtime configuration overrides               | unbounded by design          |
| `~/.config/cryptoalpha/env`          | operator           | environment file                              | n/a                          |
| `~/.cache/cryptoalpha/`              | services           | ephemeral state (alert dedup, etc.)           | self-bounded                 |
| `~/.local/state/cryptoalpha/`        | backend            | mutable state (DB, locks, support bundles)    | self-bounded                 |
| `~/.config/systemd/user/`            | bootstrap          | symlinks to `<repo>/ops/systemd-user/*`       | n/a                          |

`bootstrap.sh` MUST create every path that does not already exist, mode `0700` for `~/.config/cryptoalpha/` and `~/.local/state/cryptoalpha/`.

---

## 4. Restart authority

Authority over each operation is exclusive.

| Operation                                       | Authority                                              | Mechanism                                |
|-------------------------------------------------|--------------------------------------------------------|------------------------------------------|
| Restart `cryptoalpha-backend.service`           | systemd (`Restart=always`) **or** operator             | `systemctl --user restart`               |
| Restart `cryptoalpha-snapshots.service`         | systemd (`Restart=always`) **or** operator             | `systemctl --user restart`               |
| Restart `cryptoalpha-recommender.service`       | systemd (`Restart=always`) **or** operator             | `systemctl --user restart`               |
| Stop trading (enter SAFE_MODE)                  | backend (auto, see §7) **or** operator                 | `runtime_overrides.json: trading_enabled=false` + journald `SAFE_MODE_ENTERED` |
| Resume trading                                  | **operator only** (v1 — no auto-resume)                | `runtime_overrides.json: trading_enabled=true` |
| Trigger support bundle                          | operator                                               | `scripts/support_bundle.sh`              |
| Rotate / prune artifacts                        | retention worker (Phase 1D) under operator policy      | journald-logged, never silent            |
| Modify env file                                 | operator                                               | manual edit                              |
| Disable a unit                                  | operator                                               | `systemctl --user disable --now`         |

**v1 explicitly disallows auto-resume of trading after SAFE_MODE.** Operator must close the loop. False positives cost operator time; false negatives cost capital.

---

## 5. Health validation contract

`scripts/runtime_health.sh` is the single canonical health probe — used by `bootstrap.sh` (step 8), the operator manually, and the future watchdog (Phase 1C, will wrap not replace).

### 5.1 Probes

| # | Probe                                                                | Critical? | Failure means                |
|---|----------------------------------------------------------------------|-----------|------------------------------|
| 1 | `cryptoalpha-backend.service` `active (running)`                     | yes       | API plane down               |
| 2 | `curl -fsS http://127.0.0.1:8000/api/health` → 2xx within 5 s        | yes       | API not responsive           |
| 3 | `cryptoalpha-snapshots.service` `active (running)`                   | no        | observation plane stalled    |
| 4 | `cryptoalpha-recommender.service` `active (running)`                 | no        | decision plane stalled       |
| 5 | last line of `backend/rl_status_snapshots.jsonl` ≤ 5 min old         | no        | snapshots producer stuck     |
| 6 | `~/.config/cryptoalpha/env` exists and is mode `0600` or stricter    | yes       | secrets exposed or missing   |
| 7 | repo and `~/.local/state/cryptoalpha/` ≥ 200 MiB free                | yes       | disk pressure                |

Exit codes: `0` HEALTHY, `1` CRITICAL (any critical probe failed), `2` DEGRADED (only non-critical failed). Mapping is encoded in the script and amended only via this document.

---

## 6. Bounded retention (groundwork)

Implementation is Phase 1D. v1 freezes the **policy**.

### 6.1 Default policy

| Artifact class                        | Keep                                          | Cap                          |
|---------------------------------------|-----------------------------------------------|------------------------------|
| `chaos_logs.txt`                      | rotate at 50 MiB, gzip, keep 5 rotations      | 250 MiB                      |
| `execution_journal.jsonl`             | rotate at 100 MiB, gzip, keep 10 rotations    | 1 GiB                        |
| `backend/rl_status_snapshots.jsonl`   | rotate at 50 MiB, gzip, keep 10 rotations     | 500 MiB                      |
| `artifacts/<YYYY-MM-DD>/...`          | keep 7 daily, 4 weekly, 3 monthly             | `RUNTIME_ARTIFACTS_QUOTA_MB` |
| `artifacts/ci/history.jsonl`          | never rotate (small, audit trail)             | n/a                          |
| `snapshots/*.json`                    | keep 30 daily; older → `snapshots/archive/`   | shared quota                 |
| journald `--user`                     | systemd default                               | host policy                  |

### 6.2 Mandatory properties

- **never silent**: every prune writes one journald line with tag `cryptoalpha-retention`;
- **observable**: `support_bundle.sh` captures last 30 days of retention events;
- **auditable**: total-bytes-pruned counter exposed via `/api/ops/retention` (Phase 1D);
- **bounded**: each pass terminates in finite time and bounded bytes.

### 6.3 Immediate v1 mitigation

The current 163 MiB `chaos_logs.txt` already exceeds §6.1 cap. v1 mitigation:

- `support_bundle.sh` MUST NOT include `chaos_logs.txt` in full;
- `bootstrap.sh` warns (does not fail) if `chaos_logs.txt > 100 MiB`;
- operator may manually truncate / archive until retention worker exists.

---

## 7. SAFE_MODE contract (groundwork only)

Full state machine = S1-03 (Phase 1B). v1 freezes the **invariants** any future implementation must honor.

### 7.1 SAFE_MODE invariants

- **I-S1.** No new orders. Every order-emitting code path consults the SAFE_MODE flag first.
- **I-S2.** Reconciliation continues. Losing reconciliation in SAFE_MODE is strictly worse than not entering it.
- **I-S3.** Telemetry continues — snapshots, journald, ledger appends keep flowing.
- **I-S4.** Recovery attempts continue.
- **I-S5.** Entry observable — exactly one journald event tag `cryptoalpha-safemode`, structured `{reason, timestamp, source}`.
- **I-S6.** Exit operator-only in v1. No code path may flip `trading_enabled` back to `true` automatically.
- **I-S7.** Exit observable — same event with `event=exit`.

### 7.2 Triggers (declared, not implemented)

S1-03 implementation MUST enter SAFE_MODE on at least:

- exchange API consecutive failures > N over window W;
- reconciliation discrepancy persisting > T;
- own state divergence (any coherence-class divergence from `divergence_report` lens);
- watchdog-detected stall in snapshots or recommender;
- explicit operator command via `runtime_overrides.json`.

Exact thresholds are tuned in S1-03; what is frozen here is that **at minimum** these five triggers exist.

---

## 8. Packaging layer (Docker — optional)

`docker-compose.optional.yml` is committed alongside this document. In v1 it makes **auxiliary** dependencies reproducible. Properties:

- not invoked by any systemd unit;
- not required for `bootstrap.sh` to succeed;
- explicit operator action: `docker compose -f docker-compose.optional.yml up -d <svc>`;
- the file lists optional services as commented-out blocks (Postgres, Prometheus, Grafana). v1 leaves them inactive — adding them is a deliberate operator decision per service.

Adding orchestration (k8s, swarm) is out of scope for the entire Stage 1 roadmap.

---

## 9. Bootstrap scripts contract

Four scripts at `scripts/`. Exit-code semantics:

| Script                            | Exit 0                          | Exit 1                          | Exit 2                          |
|-----------------------------------|---------------------------------|---------------------------------|---------------------------------|
| `scripts/bootstrap.sh`            | bootstrap complete, healthy     | precondition failed (env/deps)  | services started but unhealthy  |
| `scripts/start_runtime.sh`        | all long-running units active   | systemd command failed          | unit started but unhealthy      |
| `scripts/runtime_health.sh`       | HEALTHY                         | CRITICAL                        | DEGRADED                        |
| `scripts/support_bundle.sh`       | bundle written, path printed    | I/O / permission failure        | bundle truncated due to caps    |

All four MUST:

- be `set -euo pipefail`;
- emit progress to stderr with `[script_name]` prefix;
- write structured journald entries via `systemd-cat -t cryptoalpha-<script>` for material steps;
- be idempotent where applicable;
- never read or print secrets to stdout/stderr.

`support_bundle.sh` produces `~/.local/state/cryptoalpha/support_bundle_<YYYYMMDD-HHMMSS>.tar.zst` containing:

- last 7 days of journald entries for `cryptoalpha-*` units;
- `runtime_overrides.json`;
- last 1000 lines of `execution_journal.jsonl`;
- last 1000 lines of `backend/rl_status_snapshots.jsonl`;
- `runtime_health.sh -v` output;
- `systemctl --user list-units 'cryptoalpha*' --all --no-pager`;
- `df -h` of repo and state dir.

It MUST NOT include the env file, secrets, or `chaos_logs.txt` in full.

---

## 10. What this contract does NOT cover

- **GAP-H1** unified health state machine — Phase 1B / S1-03.
- **GAP-W1** external watchdog — Phase 1C.
- **GAP-S1** SAFE_MODE *implementation* (only contract here) — Phase 1C.
- **GAP-R1** retention *implementation* (only policy here) — Phase 1D.
- **GAP-U1** UI under supervision — Phase 1B/1C.
- **GAP-A1** support bundle invariants beyond §9 — Phase 1D.

GAP-T1 closed by removing dead `After=/Wants=` references in `cryptoalpha-backend.service` and `cryptoalpha-recommender.service`. GAP-D1 acknowledged via §0/§8. GAP-B1 and GAP-E1 closed by this document plus its scripts and `.env.template`.

---

## 11. Freeze rules

- adding a new env var → §2.2 amended in same change;
- adding a new directory → §3 amended;
- changing health probes → §5.1 amended and `runtime_health.sh` exit-code semantics preserved;
- changing retention policy → §6.1 amended;
- changing SAFE_MODE invariants → §7.1 requires explicit re-entry against this freeze;
- adding to support bundle → §9 amended; bundle MUST stay below ~100 MiB compressed.

The kernel contract `kernel_contract_freeze_v1.md` is unaffected by anything in this document. Stage 1 is operator-plane only and never touches `atp/`, `backend/stress/`, or the lens lattice.
