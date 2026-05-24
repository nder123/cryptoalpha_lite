# Operational Timeline Engine v1 — Stage 1 / Phase 1B / Task S1-07

**Status:** initial freeze (engine + CLI + endpoint)
**Date:** 2026-05-24
**Depends on:** `docs/watchdog_recovery_v1.md`, `docs/safe_mode_enforcement_v1.md`, `docs/retention_cleanup_v1.md`, `docs/chaos_recovery_drills_v1.md`
**Closes:** GAP-H1 (operator-facing projection — investigation surface, not dashboards)
**Implementation:** `backend/runtime/timeline/`
**Test surface:** `backend/tests/test_timeline.py`

This task converts the existing evidence streams (`runtime_health_transitions.jsonl`,
`trading_gate_evidence.jsonl`, optional `retention_history.jsonl`) into a single
chronologically-ordered investigation tool. **Not** a UI. Not a dashboard.
A replayable causal-ordered timeline engine for incident reconstruction.

---

## 0. Design axiom

```
visualization is a downstream concern;
investigation is the upstream invariant
```

The timeline engine produces structured events that any visualizer (CLI, web,
operator notebook) can consume. v1 ships the engine + a JSON/text CLI + a
read-only HTTP endpoint. UI is explicitly out of scope.

The engine is **stateless and read-only**. It never writes back to its sources.
It can be invoked while the watchdog/runtime is running without coordination.

---

## 1. Unified event schema

```json
{
  "schema": "operational_timeline_event.v1",
  "ts": 1779379200.0,
  "ts_iso": "2026-05-24T16:00:00+00:00",
  "source": "transitions" | "trading_gate" | "retention" | "...",
  "kind": "state:HEALTHY->DEGRADED" | "gate:execution_denied" | "retention:pass(rot=1,del=3)",
  "severity": "info" | "notice" | "warning" | "alert" | "crit",
  "payload": { ... raw record ... }
}
```

Severity mapping is canonical:

| Source        | Trigger                                  | Severity   |
|---------------|------------------------------------------|------------|
| transitions   | target=HEALTHY/BOOTSTRAPPING             | info       |
| transitions   | target=DEGRADED/RECOVERING               | notice     |
| transitions   | target=STALLED                           | warning    |
| transitions   | target=SAFE_MODE                         | alert      |
| transitions   | target=CRITICAL                          | crit       |
| trading_gate  | event=execution_denied                   | alert      |
| trading_gate  | event=execution_admitted                 | info       |
| retention     | rotated > 0 OR deleted > 0               | notice     |
| retention     | no-op pass                               | info       |

---

## 2. Sources

`backend/runtime/timeline/events.py` provides parsers:

- `parse_transitions(path)` — `runtime_health_transitions.jsonl`
- `parse_trading_gate_evidence(path)` — `trading_gate_evidence.jsonl`
- `parse_retention_summary(path)` — optional `retention_history.jsonl` sidecar
- `parse_generic_jsonl(path, source, ts_field, kind_prefix)` — extension hook
  for any future stream

Each parser:

- silently skips malformed lines (no abort);
- silently skips records with no parseable timestamp;
- accepts both unix-seconds (number) and ISO-8601 strings (with or without Z);
- never holds the file open beyond iteration scope.

---

## 3. Merger

`engine.merge(sources: TimelineSources) -> Iterator[TimelineEvent]`:

- chronologically merges all source streams with `heapq.merge`;
- stable ordering on equal timestamps (by source, then insertion id);
- streaming — never materializes the full timeline in memory;
- safe for the API endpoint to consume directly.

`TimelineSources.for_repo(repo_root)` is the canonical factory.

---

## 4. Filters

```python
filter_by_window(events, since=ts, until=ts)         # inclusive
filter_by_severity(events, min_severity="warning")   # threshold
filter_by_source(events, sources=("transitions",))   # whitelist
```

All filters are pure generators. Composable in any order.

---

## 5. Incident correlation

```python
correlate_incident(
    events,
    anchor_ts: float,
    window_before_sec: float = 300.0,
    window_after_sec: float = 300.0,
) -> Incident
```

Returns:

```json
{
  "schema": "operational_incident.v1",
  "anchor": {"ts": ..., "kind": "...", "source": "..."},
  "window": {"before_sec": 300, "after_sec": 300, "events_count": N},
  "events": [...all events in window...],
  "causal_chain": [...likely causes + anchor + likely consequences, sorted by ts...]
}
```

### 5.1 Causal heuristic

An event before the anchor is a **likely cause** if:

- its severity ≥ anchor's severity, OR
- it is a transition with severity ∈ {warning, alert, crit}, OR
- it is a `trading_gate` `execution_denied` record.

An event after the anchor is a **likely consequence** if:

- it is a transition (any), OR
- it is a `trading_gate` `execution_denied` record.

The anchor itself is the event in the window whose `ts` is closest to the
requested `anchor_ts`, ties broken by source priority (transitions > gate >
retention) then severity priority.

This is a **heuristic**, not a proof. Its purpose is to surface the most
operationally relevant context, not to formally derive causality. The full
window is always returned alongside the chain so the operator can override.

---

## 6. CLI

```bash
poetry run python -m runtime.timeline [options]

  --since ISO8601|unix      lower bound (inclusive)
  --until ISO8601|unix      upper bound (inclusive)
  --min-severity LEVEL      info|notice|warning|alert|crit
  --source NAME             repeatable; whitelist
  --incident ISO8601|unix   build incident report around anchor
  --window-before SEC       (default 300)
  --window-after SEC        (default 300)
  --json                    emit JSON instead of text
  --limit N                 cap output (0 = unlimited)
```

Plain text output:

```
2026-05-24T16:00:00+00:00  [crit   ]  transitions    state:DEGRADED->CRITICAL
2026-05-24T16:00:01+00:00  [alert  ]  trading_gate   gate:execution_denied
```

Incident text output emits anchor + chain. JSON output is the full Incident
record.

---

## 7. HTTP endpoint

`GET /api/ops/timeline` — read-only projection. Query parameters mirror the
CLI: `since`, `until`, `min_severity`, `source` (comma-separated for multiple),
`incident`, `window_before`, `window_after`, `limit` (default 500, hard cap to
prevent unbounded responses).

Two response modes:

- `mode=stream` — flat `events[]` list; `truncated=true` when `limit` was hit.
- `mode=incident` — full `Incident` shape from §5.

The endpoint returns 200 on missing source files (empty stream). Never 5xx
for read-only operation; matches the staleness/availability pattern of
`/api/ops/health-state` and `/api/ops/runtime-policy`.

---

## 8. Test surface

`backend/tests/test_timeline.py` — 16 tests:

- timestamp parsing (unix/int/ISO-8601/Z-suffix/garbage);
- transitions parser (severity mapping, malformed lines, missing files);
- trading_gate parser (denial → alert);
- merge ordering (chronological + stable);
- filters (window inclusive, severity threshold, source whitelist);
- incident correlation: synthetic incident with HEALTHY → DEGRADED → CRITICAL
  → SAFE_MODE + denials, anchor=SAFE_MODE entry, chain must include the
  prior CRITICAL transition AND subsequent denials, sorted chronologically;
- empty-window incident; serialization schema check; equal-ts stability.

All tests use `tmp_path`; no fixture touches the live `artifacts/` directory.

---

## 9. Boundary preservation

Added:

- `backend/runtime/timeline/__init__.py` (new)
- `backend/runtime/timeline/events.py` (new)
- `backend/runtime/timeline/engine.py` (new)
- `backend/runtime/timeline/cli.py` (new)
- `backend/runtime/timeline/__main__.py` (new)
- `backend/tests/test_timeline.py` (new — 16 cases)
- one new endpoint in `backend/app/api/routes.py` (read-only)

NOT modified:

- `atp/`, `backend/stress/`, lens lattice, kernel contract or errata
- `backend/runtime/watchdog/*` — timeline reads its outputs, never the other way around
- `backend/runtime/retention/*` — same
- `backend/app/services/trading_gate.py` — same

The engine has zero coupling to its sources beyond their on-disk schemas.
Replacing any source with a different writer is a documentation change.

---

## 10. What this task does NOT do

- no UI, no dashboards, no charting (downstream concern);
- no journald native ingestion (out of scope; v2 candidate via
  `journalctl --user -o json` adapter);
- no formal causal proofs — the chain is a heuristic;
- no persistence — every invocation re-merges from source files;
- no streaming subscription / SSE / websocket (v1 is pull-only).

---

## 11. Freeze rules

- adding a new source → §2 amended; severity mapping in §1 updated;
- changing severity for any source → §1 amended in same change; existing
  consumers must be notified;
- adding a CLI flag → §6 amended; corresponding endpoint query param in §7;
- changing the incident causal heuristic → §5.1 amended; new test fixture
  required;
- changing the event schema → bump `operational_timeline_event.vN` and v1
  consumers must continue to parse v1 events.
