"""Trading Gate — S1-05 §2, §3, §7.

Single authority that decides whether an execution-class action is allowed
given the current runtime health state. Every order-emitting code path MUST
call `assert_trading_allowed(...)` or check `is_trading_allowed(...)` before
making external side-effects.

Failure semantics: `TradingNotAllowed` is raised. Never silently ignored.
Every denial is logged with structured evidence.

Authoritative spec: docs/safe_mode_enforcement_v1.md.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.runtime_health_reader import (
    RuntimeHealthReader,
    RuntimeHealthSnapshot,
    get_default_reader,
)

_logger = logging.getLogger(__name__)


# Per S1-05 table:
#   HEALTHY/DEGRADED → allowed
#   RECOVERING → restricted (allowed only with explicit allow_restricted=True)
#   BOOTSTRAPPING/STALLED/SAFE_MODE/CRITICAL/UNKNOWN → denied
ALLOWED_STATES: frozenset[str] = frozenset({"HEALTHY", "DEGRADED"})
RESTRICTED_STATES: frozenset[str] = frozenset({"RECOVERING"})
DENIED_STATES: frozenset[str] = frozenset(
    {"BOOTSTRAPPING", "STALLED", "SAFE_MODE", "CRITICAL", "UNKNOWN"}
)


class TradingNotAllowed(RuntimeError):
    """Raised when an execution-class action is attempted while the runtime
    health state does not permit trading. Carries structured evidence."""

    def __init__(self, *, state: str, reason: str, component: str, attempted_action: str):
        self.state = state
        self.reason = reason
        self.component = component
        self.attempted_action = attempted_action
        super().__init__(
            f"trading denied: state={state} reason={reason} "
            f"component={component} action={attempted_action}"
        )

    def as_evidence(self) -> dict[str, Any]:
        return {
            "event": "execution_denied",
            "reason": self.reason,
            "state": self.state,
            "component": self.component,
            "attempted_action": self.attempted_action,
            "ts": time.time(),
        }


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    state: str
    reason: str
    stale: bool


def _evaluate(snapshot: RuntimeHealthSnapshot, *, allow_restricted: bool) -> GateDecision:
    state = snapshot.state
    if state in ALLOWED_STATES:
        return GateDecision(allowed=True, state=state, reason="state_allows_trading", stale=snapshot.stale)
    if state in RESTRICTED_STATES:
        if allow_restricted:
            return GateDecision(allowed=True, state=state, reason="restricted_explicitly_allowed", stale=snapshot.stale)
        return GateDecision(allowed=False, state=state, reason="state_restricted", stale=snapshot.stale)
    # DENIED_STATES (incl. UNKNOWN / stale fallback)
    return GateDecision(allowed=False, state=state, reason=f"state_{state.lower()}", stale=snapshot.stale)


def is_trading_allowed(
    *,
    reader: RuntimeHealthReader | None = None,
    allow_restricted: bool = False,
) -> GateDecision:
    """Pure read. Never raises. Use this when you want to branch without raising."""
    r = reader or get_default_reader()
    snap = r.read()
    return _evaluate(snap, allow_restricted=allow_restricted)


def assert_trading_allowed(
    *,
    component: str,
    attempted_action: str,
    reader: RuntimeHealthReader | None = None,
    allow_restricted: bool = False,
    evidence_sink=None,
) -> GateDecision:
    """Raise `TradingNotAllowed` if not allowed. Always emits a structured
    evidence record (whether allowed or denied), so the operational log has
    a full trace of gate consultations from every component."""
    decision = is_trading_allowed(reader=reader, allow_restricted=allow_restricted)
    payload: dict[str, Any] = {
        "event": "execution_denied" if not decision.allowed else "execution_admitted",
        "state": decision.state,
        "reason": decision.reason,
        "component": component,
        "attempted_action": attempted_action,
        "stale": decision.stale,
        "ts": time.time(),
    }
    _emit_evidence(payload, sink=evidence_sink)
    if not decision.allowed:
        raise TradingNotAllowed(
            state=decision.state,
            reason=decision.reason,
            component=component,
            attempted_action=attempted_action,
        )
    return decision


def _evidence_path() -> Path:
    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    return repo_root / "artifacts" / "trading_gate_evidence.jsonl"


def _emit_evidence(payload: dict[str, Any], *, sink=None) -> None:
    """Best-effort: log + append to jsonl. Failures never raise."""
    try:
        _logger.info("trading_gate %s", payload)
    except Exception:
        pass
    if sink is not None:
        try:
            sink(payload)
            return
        except Exception:
            pass
    # Only persist denials by default — allow admit events are high-volume.
    if payload.get("event") != "execution_denied":
        return
    try:
        path = _evidence_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


# ── Policy projection (for /api/ops/runtime-policy) ─────────────────────


@dataclass(frozen=True)
class RuntimePolicy:
    state: str
    trading_allowed: bool
    strategy_allowed: bool
    reconciliation_allowed: bool
    observability_allowed: bool
    entered_at: str | None
    reason: str
    stale: bool


def derive_policy(snapshot: RuntimeHealthSnapshot) -> RuntimePolicy:
    """Single mapping from health state to operational permissions.

    Reconciliation and observability are NEVER disabled by SAFE_MODE per
    invariants I-S2..I-S5. CRITICAL also keeps them best-effort.
    """
    trading_decision = _evaluate(snapshot, allow_restricted=False)
    strategy_allowed = trading_decision.allowed and snapshot.state in ALLOWED_STATES
    # Reconciliation/observability allowed in every state except a fully
    # unknown bootstrap-pre-watchdog scenario.
    recon_allowed = snapshot.state != "UNKNOWN" or snapshot.stale_reason == "watchdog_silent"
    obs_allowed = recon_allowed
    reason_codes = list(snapshot.reasons) if snapshot.reasons else []
    reason = reason_codes[0] if reason_codes else trading_decision.reason
    return RuntimePolicy(
        state=snapshot.state,
        trading_allowed=trading_decision.allowed,
        strategy_allowed=strategy_allowed,
        reconciliation_allowed=recon_allowed,
        observability_allowed=obs_allowed,
        entered_at=snapshot.since,
        reason=reason,
        stale=snapshot.stale,
    )
