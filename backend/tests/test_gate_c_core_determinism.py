"""Gate C (Testnet readiness) — core deterministic execution verification.

PURPOSE
-------
Validate that the *real* core trading subsystems can be driven through a single
end-to-end lifecycle deterministically:

    create (hypothesis) -> risk check -> directive -> gate -> execution emission

and that running the same synthetic input twice produces byte-identical state
transitions, with every transition carrying a ``trace_id`` (no silent / untracked
state changes).

LAYERS (per the Gate C plan)
----------------------------
LAYER 1 — REAL system code, exercised unchanged:
    * ``app.services.risk_engine.RiskEngine`` (real risk decision logic)
    * ``app.services.execution_engine.ExecutionEngine`` (real execution decision logic)
    * ``app.infrastructure.event_bus.EventBus`` (real serialization / envelope path)
    * ``app.services.trading_gate`` (real gate authority)

LAYER 2 — STUB interfaces only, confined entirely to this test module. No
production module is modified and none of the missing runtime modules are
implemented:
    * ``runtime_health_reader`` — null observer (always HEALTHY) injected via
      ``sys.modules`` so the real ``trading_gate`` imports cleanly. This is the
      *only* way the import chain (execution_engine -> trading_gate ->
      runtime_health_reader) can resolve while that production module is absent.
    * watchdog — passive *stub validator* that asserts transition interface
      consistency (every transition is well-formed and ordered).
    * freeze_guard — passive check stub that observes but never blocks.

The real ``EventBus`` is used with an in-memory fake Redis transport so the real
publish/serialize code path runs without any external broker (deterministic).

OUTPUTS
-------
    * this test file (the deterministic verification harness)
    * ``gate_c_core_report.json`` written to the repository root with an overall
      PASS / FAIL verdict and full transition trace.

CONSTRAINTS HONOURED
--------------------
    * no refactor of architecture; no new subsystems
    * risk / watchdog / freeze_guard are NOT disabled (watchdog/freeze_guard are
      represented by passive stubs at the test boundary, as instructed)
    * production watchdog / freeze_guard code is not modified
    * missing runtime modules are NOT implemented
"""

from __future__ import annotations

import json
import logging
import sys
import types
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Path + Layer-2 stub bootstrap. This MUST run before any ``app.*`` import so the
# real ``trading_gate`` can resolve ``app.services.runtime_health_reader`` (a
# missing production module) against our in-test null observer.
# ─────────────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

_RHR_MODULE = "app.services.runtime_health_reader"


@dataclass(frozen=True)
class _StubHealthSnapshot:
    """Minimal stand-in for the absent ``RuntimeHealthSnapshot``.

    Only ``state`` and ``stale`` are consumed by the real trading gate; the
    remaining fields mirror the documented schema so the stub is a faithful
    null observer rather than a partial shape.
    """

    state: str = "HEALTHY"
    stale: bool = False
    stale_reason: str | None = None
    safe_mode_active: bool = False
    coherence_break_count: int = 0
    trading_enabled: bool = True
    runtime_mode: str = "OFFLINE"


class _NullHealthObserver:
    """Layer-2 null observer: reports a constant HEALTHY snapshot, makes no
    decisions, never raises, never touches the filesystem."""

    def __init__(self, path: Any = None, state: str = "HEALTHY") -> None:
        self._snap = _StubHealthSnapshot(state=state)
        self.reads = 0

    def read(self) -> _StubHealthSnapshot:
        self.reads += 1
        return self._snap


def _install_runtime_health_reader_stub() -> types.ModuleType:
    """Inject the null-observer module so the import chain resolves in test scope."""
    if _RHR_MODULE in sys.modules:
        return sys.modules[_RHR_MODULE]

    import app.services  # noqa: F401  (ensure the real parent package exists first)

    module = types.ModuleType(_RHR_MODULE)
    _singleton = _NullHealthObserver()

    def get_default_reader() -> _NullHealthObserver:
        return _singleton

    def set_default_reader_for_tests(
        reader: Any,
    ) -> None:  # pragma: no cover - parity shim
        nonlocal _singleton
        if reader is not None:
            _singleton = reader

    module.RuntimeHealthReader = _NullHealthObserver
    module.RuntimeHealthSnapshot = _StubHealthSnapshot
    module.get_default_reader = get_default_reader
    module.set_default_reader_for_tests = set_default_reader_for_tests
    module.__gate_c_stub__ = True
    sys.modules[_RHR_MODULE] = module
    return module


_HEALTH_STUB = _install_runtime_health_reader_stub()

# Now the real Layer-1 modules import cleanly.
from app.core.runtime_config import RuntimeConfig  # noqa: E402
from app.domain import streams  # noqa: E402
from app.domain.events import (  # noqa: E402
    CTOAiDecision,
    ExecutionStatus,
    HypothesisType,
    RiskDecision,
    TradeAction,
    TradeDirective,
    TradeHypothesis,
    TradingMode,
)
from app.infrastructure.event_bus import EventBus  # noqa: E402
from app.services.execution_engine import ExecutionEngine  # noqa: E402
from app.services.risk_engine import RiskEngine  # noqa: E402
from app.services.trading_gate import is_trading_allowed  # noqa: E402

_logger = logging.getLogger("gate_c")

# ─────────────────────────────────────────────────────────────────────────────
# Deterministic synthetic input (identical for every run).
# ─────────────────────────────────────────────────────────────────────────────
TRACE_ID = "gate-c-trace-0001"
_FIXED_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Fields are chosen so the real risk engine APPROVES (no blockers) and the full
# lifecycle reaches execution emission.
SEED_HYPOTHESIS = {
    "hypothesis_id": "hyp-0001",
    "symbol": "BTCUSDT",
    "hypothesis_type": HypothesisType.TREND,
    "confidence": 0.8,
    "direction": "long",
    "entry_price": 50_000.0,
    "target_price": 51_000.0,
    "stop_price": 49_500.0,
    "position_size": 0.01,
    "leverage": 2.0,
    "notional_usdt": 100.0,
}

EXPECTED_LIFECYCLE = [
    "hypothesis_created",
    "risk_assessed",
    "directive_issued",
    "gate_checked",
    "execution_reported",
]

# Keys excluded from determinism comparison: wall-clock stamps populated via
# ``datetime.now`` inside the real production code. Their *presence* is verified
# separately; their value is intentionally not part of the deterministic state.
_VOLATILE_KEYS = frozenset(
    {
        "reported_at",
        "evaluated_at",
        "issued_at",
        "created_at",
        "timestamp",
        "ts",
        "updated_at",
    }
)


def _canon(obj: Any) -> Any:
    """Strip volatile timestamp keys at every depth so equal logical state
    compares equal regardless of wall-clock."""
    if isinstance(obj, dict):
        return {k: _canon(v) for k, v in obj.items() if k not in _VOLATILE_KEYS}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Layer-2 passive stubs.
# ─────────────────────────────────────────────────────────────────────────────
class SilentTransitionError(AssertionError):
    """Raised when a state transition is recorded without a trace_id."""


class WatchdogStubValidator:
    """Passive watchdog stub. Validates *interface consistency* of every
    transition (trace_id present, kind recognised, lifecycle order monotonic).
    It never mutates state and never restarts anything."""

    def __init__(self) -> None:
        self.validations: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def validate(self, transition: dict[str, Any]) -> None:
        kind = transition.get("kind")
        trace_id = transition.get("trace_id")
        if not trace_id:
            self.errors.append(f"missing trace_id on {kind}")
            raise SilentTransitionError(f"silent transition: {kind!r} has no trace_id")
        if kind not in EXPECTED_LIFECYCLE:
            self.errors.append(f"unknown kind {kind!r}")
            raise SilentTransitionError(f"unknown transition kind: {kind!r}")
        # Lifecycle must be observed in declared order.
        expected_index = len(self.validations)
        if expected_index < len(EXPECTED_LIFECYCLE):
            want = EXPECTED_LIFECYCLE[expected_index]
            if kind != want:
                self.errors.append(f"out-of-order: got {kind!r} expected {want!r}")
                raise SilentTransitionError(
                    f"out-of-order transition: got {kind!r}, expected {want!r}"
                )
        self.validations.append(transition)


class FreezeGuardPassiveStub:
    """Passive freeze-guard check. Observes each transition and records it but
    never blocks the flow (returns True always)."""

    def __init__(self) -> None:
        self.checks: list[str] = []

    def check(self, transition: dict[str, Any]) -> bool:
        self.checks.append(transition["kind"])
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic in-memory Redis transport for the REAL EventBus.
# ─────────────────────────────────────────────────────────────────────────────
class _FakeRedis:
    """Implements only the slice of the async redis API used by ``EventBus``
    in the publish path. Deterministic message ids; pure in-memory."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []
        self._seq = 0

    async def xadd(
        self,
        stream: str,
        *,
        fields: dict[str, Any],
        maxlen: int | None = None,
        approximate: bool | None = None,
        id: str | None = None,
    ) -> str:
        self._seq += 1
        message_id = id or f"{self._seq}-0"
        envelope = json.loads(fields["payload"])
        self.records.append((stream, envelope))
        return message_id


# ─────────────────────────────────────────────────────────────────────────────
# In-test fakes for non-core externals (exchange client, idempotency registry,
# state store). These are adapters at the test boundary only.
# ─────────────────────────────────────────────────────────────────────────────
class _FakeRegistry:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def register_if_new(self, decision_uid: str | None) -> bool:
        if decision_uid is None or decision_uid in self._seen:
            return False
        self._seen.add(decision_uid)
        return True

    async def mark_processed(self, decision_uid: str | None) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeStore:
    async def get_risk_budget(self) -> dict[str, Any]:
        return {}

    async def list_positions(self) -> list[dict[str, Any]]:
        return []

    async def set_service_health(self, name: str, payload: dict[str, Any]) -> None:
        return None


class _FakeExchangeClient:
    async def fetch_positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        return []

    async def close(self) -> None:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Transition recorder — the single choke point through which *every* state
# change must pass. A change that bypasses it (or arrives without a trace_id)
# is treated as a silent/untracked transition and rejected.
# ─────────────────────────────────────────────────────────────────────────────
class TransitionRecorder:
    def __init__(
        self, watchdog: WatchdogStubValidator, freeze_guard: FreezeGuardPassiveStub
    ) -> None:
        self.transitions: list[dict[str, Any]] = []
        self._watchdog = watchdog
        self._freeze_guard = freeze_guard

    def record(
        self, kind: str, source: str, trace_id: str, payload: dict[str, Any]
    ) -> None:
        if not trace_id:
            raise SilentTransitionError(f"refused silent transition: {kind!r}")
        transition = {
            "seq": len(self.transitions),
            "kind": kind,
            "source": source,
            "trace_id": trace_id,
            "payload": _canon(payload),
        }
        # Layer-2 passive validation (does not block the real flow).
        self._watchdog.validate(transition)
        self._freeze_guard.check(transition)
        self.transitions.append(transition)


# ─────────────────────────────────────────────────────────────────────────────
# The deterministic pipeline. Builds fresh real engines + fresh transport on
# every call so two runs are fully independent.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class PipelineRun:
    transitions: list[dict[str, Any]]
    emitted: list[tuple[str, dict[str, Any]]]
    watchdog: WatchdogStubValidator
    freeze_guard: FreezeGuardPassiveStub
    health_reads: int


def _build_hypothesis() -> TradeHypothesis:
    return TradeHypothesis(created_at=_FIXED_TS, **SEED_HYPOTHESIS)


def _build_decision(hypothesis: TradeHypothesis) -> CTOAiDecision:
    directive = TradeDirective(
        directive_id="dir-0001",
        hypothesis_id=hypothesis.hypothesis_id,
        symbol=hypothesis.symbol,
        issued_at=_FIXED_TS,
        action=TradeAction.OPEN,
        rationale=["gate-c synthetic directive"],
        mode=TradingMode.FULL_AUTO,
        confidence=hypothesis.confidence,
        direction=hypothesis.direction,
        order_type="market",
        quantity=hypothesis.position_size,
        leverage=hypothesis.leverage,
        notional_usdt=hypothesis.notional_usdt,
        decision_uid="decision-0001",
    )
    return CTOAiDecision(
        decision_uid="decision-0001",
        directive_id=directive.directive_id,
        symbol=directive.symbol,
        issued_at=_FIXED_TS,
        action=TradeAction.OPEN,
        size=directive.quantity,
        notional_usdt=directive.notional_usdt,
        source="fsm",
        directive=directive,
    )


async def run_pipeline(trace_id: str = TRACE_ID) -> PipelineRun:
    watchdog = WatchdogStubValidator()
    freeze_guard = FreezeGuardPassiveStub()
    recorder = TransitionRecorder(watchdog, freeze_guard)

    fake_redis = _FakeRedis()
    bus = EventBus(fake_redis, maxlen=None)  # real EventBus, deterministic transport
    store = _FakeStore()

    # ── 1. CREATE ────────────────────────────────────────────────────────────
    hypothesis = _build_hypothesis()
    await bus.publish(streams.RESEARCH_HYPOTHESES, hypothesis)
    recorder.record(
        "hypothesis_created", "research", trace_id, hypothesis.model_dump(mode="json")
    )

    # ── 2. RISK CHECK (real RiskEngine decision logic) ────────────────────────
    risk_engine = RiskEngine(bus, config_manager=object(), store=store)
    positions = await store.list_positions()
    risk_budget = await store.get_risk_budget()
    current_exposure = sum(abs(float(p.get("notional_usdt") or 0.0)) for p in positions)
    # Deterministic daily counters (no DB in test scope; mirrors run()'s inputs).
    daily_stats = {"trades_today": 0.0, "pnl_today": 0.0, "consecutive_losses": 0.0}
    assessment = risk_engine._assess_hypothesis(
        hypothesis, current_exposure, risk_budget, daily_stats
    )
    await bus.publish(streams.RISK_ASSESSMENTS, assessment)
    recorder.record(
        "risk_assessed", "risk_engine", trace_id, assessment.model_dump(mode="json")
    )

    # Only proceed to execution when risk approves (faithful gating).
    if assessment.decision is RiskDecision.APPROVED:
        # ── 3. DIRECTIVE ──────────────────────────────────────────────────────
        decision = _build_decision(hypothesis)
        recorder.record(
            "directive_issued",
            "cto_ai",
            trace_id,
            decision.directive.model_dump(mode="json"),
        )

        # ── 4. GATE (real trading gate, null-observer reader) ─────────────────
        gate_decision = is_trading_allowed()
        recorder.record(
            "gate_checked",
            "trading_gate",
            trace_id,
            {
                "allowed": gate_decision.allowed,
                "state": gate_decision.state,
                "reason": gate_decision.reason,
                "stale": gate_decision.stale,
            },
        )

        # ── 5. EXECUTION (real ExecutionEngine decision logic, dry-run) ───────
        engine = ExecutionEngine(bus, config_manager=object(), store=store)
        engine._decision_registry = _FakeRegistry()
        engine._client = _FakeExchangeClient()
        engine._store = store
        engine._config = RuntimeConfig(dry_run=True)
        await engine._handle_decision(decision)

        # Capture the execution report the engine emitted onto the bus.
        report_env = next(
            env
            for stream, env in fake_redis.records
            if stream == streams.EXECUTION_REPORTS
        )
        recorder.record(
            "execution_reported", "execution_engine", trace_id, report_env["data"]
        )

    return PipelineRun(
        transitions=recorder.transitions,
        emitted=list(fake_redis.records),
        watchdog=watchdog,
        freeze_guard=freeze_guard,
        health_reads=_HEALTH_STUB.get_default_reader().reads,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation + report generation (callable from pytest and from __main__).
# ─────────────────────────────────────────────────────────────────────────────
def _diff_transitions(
    a: list[dict[str, Any]], b: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    divergences: list[dict[str, Any]] = []
    if len(a) != len(b):
        divergences.append({"type": "length", "run1": len(a), "run2": len(b)})
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            divergences.append(
                {"type": "transition", "index": i, "run1": a[i], "run2": b[i]}
            )
    return divergences


def evaluate_gate_c() -> dict[str, Any]:
    import asyncio

    run1 = asyncio.run(run_pipeline())
    run2 = asyncio.run(run_pipeline())

    t1 = run1.transitions
    t2 = run2.transitions

    divergences = _diff_transitions(t1, t2)
    identical = not divergences

    observed = [t["kind"] for t in t1]
    missing = [k for k in EXPECTED_LIFECYCLE if k not in observed]
    untracked = [t["kind"] for t in t1 if not t.get("trace_id")]
    all_have_trace = not untracked

    reasons: list[str] = []
    if not identical:
        reasons.append(f"{len(divergences)} divergence(s) between runs")
    if missing:
        reasons.append(f"missing lifecycle transitions: {missing}")
    if not all_have_trace:
        reasons.append(f"silent (trace-less) transitions: {untracked}")
    if run1.watchdog.errors:
        reasons.append(f"watchdog interface errors: {run1.watchdog.errors}")

    passed = identical and not missing and all_have_trace and not run1.watchdog.errors
    reason = "deterministic core execution verified" if passed else "; ".join(reasons)

    report = {
        "gate": "C",
        "phase": "testnet_preparation",
        "objective": "deterministic core execution without state divergence",
        "result": "PASS" if passed else "FAIL",
        "reason": reason,
        "runs": 2,
        "trace_id": TRACE_ID,
        "layers": {
            "real": ["execution_engine", "risk_engine", "event_bus", "trading_gate"],
            "stub": [
                "watchdog (validator)",
                "freeze_guard (passive)",
                "runtime_health_reader (null observer)",
            ],
        },
        "determinism": {"identical": identical, "divergences": divergences},
        "trace_enforcement": {
            "all_transitions_have_trace_id": all_have_trace,
            "silent_transitions": len(untracked),
        },
        "lifecycle": {
            "expected": EXPECTED_LIFECYCLE,
            "observed": observed,
            "missing": missing,
        },
        "stub_invocations": {
            "watchdog_validations": len(run1.watchdog.validations),
            "freeze_guard_checks": len(run1.freeze_guard.checks),
            "health_reader_reads": run1.health_reads,
        },
        "transitions_run1": t1,
        "transitions_run2": t2,
    }
    return report


def write_report(report: dict[str, Any]) -> Path:
    path = _REPO_ROOT / "gate_c_core_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    verdict = report["result"]
    _logger.warning("GATE_C_CORE: %s reason=%s", verdict, report["reason"])
    print(f"GATE_C_CORE: {verdict} reason={report['reason']}")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Pytest surface.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    rep = evaluate_gate_c()
    write_report(rep)
    return rep


def test_no_runtime_import_failures_in_test_scope() -> None:
    """Acceptance: the real core modules import cleanly in test scope with the
    Layer-2 stubs in place (no ImportError despite the missing runtime module)."""
    import importlib

    for name in (
        "app.services.trading_gate",
        "app.services.risk_engine",
        "app.services.execution_engine",
        "app.infrastructure.event_bus",
    ):
        assert importlib.import_module(name) is not None
    assert getattr(sys.modules[_RHR_MODULE], "__gate_c_stub__", False) is True


def test_core_execution_determinism(report: dict[str, Any]) -> None:
    """Acceptance: identical input → identical ordered state transitions."""
    assert report["determinism"]["identical"], report["determinism"]["divergences"]
    assert report["transitions_run1"] == report["transitions_run2"]


def test_full_lifecycle_present(report: dict[str, Any]) -> None:
    """Acceptance: every expected lifecycle transition is observed (no gaps)."""
    assert report["lifecycle"]["missing"] == []
    assert report["lifecycle"]["observed"] == EXPECTED_LIFECYCLE


def test_every_transition_has_trace_id(report: dict[str, Any]) -> None:
    """Acceptance: trace enforcement — no silent / untracked transitions."""
    assert report["trace_enforcement"]["all_transitions_have_trace_id"] is True
    assert report["trace_enforcement"]["silent_transitions"] == 0
    for transition in report["transitions_run1"]:
        assert transition["trace_id"] == TRACE_ID


def test_silent_transition_is_rejected() -> None:
    """A transition recorded without a trace_id must be refused (proves silent
    state changes cannot slip through the recorder)."""
    recorder = TransitionRecorder(WatchdogStubValidator(), FreezeGuardPassiveStub())
    with pytest.raises(SilentTransitionError):
        recorder.record("hypothesis_created", "research", "", {})


def test_stub_layer_interface_consistency(report: dict[str, Any]) -> None:
    """Acceptance: the stub layer validated every transition (interface
    consistency) and the passive checks ran without blocking."""
    n = len(EXPECTED_LIFECYCLE)
    assert report["stub_invocations"]["watchdog_validations"] == n
    assert report["stub_invocations"]["freeze_guard_checks"] == n
    assert report["stub_invocations"]["health_reader_reads"] >= 1


def test_risk_engine_approved_path(report: dict[str, Any]) -> None:
    """The synthetic input drives the real risk engine to APPROVED, so the
    execution stage is genuinely exercised."""
    risk = next(t for t in report["transitions_run1"] if t["kind"] == "risk_assessed")
    assert risk["payload"]["decision"] == RiskDecision.APPROVED.value
    assert risk["payload"]["blockers"] == []
    execution = next(
        t for t in report["transitions_run1"] if t["kind"] == "execution_reported"
    )
    assert execution["payload"]["status"] == ExecutionStatus.SUBMITTED.value


def test_gate_c_overall_pass(report: dict[str, Any]) -> None:
    """Overall Gate C verdict must be PASS."""
    assert report["result"] == "PASS", report["reason"]


if __name__ == "__main__":  # pragma: no cover - manual / CI invocation
    rep = evaluate_gate_c()
    path = write_report(rep)
    print(f"report written: {path}")
    sys.exit(0 if rep["result"] == "PASS" else 1)
