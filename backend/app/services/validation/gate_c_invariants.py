from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GateCState(str, Enum):
    CREATED = "CREATED"
    RISK_CHECKED = "RISK_CHECKED"
    DECIDED = "DECIDED"
    RECORDED = "RECORDED"


REQUIRED_LIFECYCLE = (
    GateCState.CREATED,
    GateCState.RISK_CHECKED,
    GateCState.DECIDED,
    GateCState.RECORDED,
)


@dataclass(frozen=True)
class GateCEvent:
    trade_id: str
    state: GateCState
    message_id: str
    source: str


@dataclass(frozen=True)
class GateCViolation:
    code: str
    message: str
    trade_id: str | None = None


@dataclass(frozen=True)
class GateCInvariantReport:
    violations: tuple[GateCViolation, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.violations


def validate_gate_c_invariants(events: list[GateCEvent]) -> GateCInvariantReport:
    violations: list[GateCViolation] = []
    violations.extend(_validate_lifecycles(events))
    violations.extend(_validate_event_bus_sequence(events))
    return GateCInvariantReport(tuple(violations))


def assert_gate_c_invariants(events: list[GateCEvent]) -> None:
    report = validate_gate_c_invariants(events)
    if not report.passed:
        details = "; ".join(v.message for v in report.violations)
        raise AssertionError(details)


def _validate_lifecycles(events: list[GateCEvent]) -> list[GateCViolation]:
    violations: list[GateCViolation] = []
    by_trade: dict[str, list[GateCEvent]] = {}
    for event in events:
        if not event.trade_id:
            violations.append(
                GateCViolation(
                    code="GATE_C_ORPHAN_EVENT",
                    message=f"orphan event {event.message_id}",
                )
            )
            continue
        by_trade.setdefault(event.trade_id, []).append(event)

    for trade_id, trade_events in by_trade.items():
        states = [event.state for event in trade_events]
        for required in REQUIRED_LIFECYCLE:
            if required not in states:
                violations.append(
                    GateCViolation(
                        code="GATE_C_MISSING_STATE",
                        message=f"{trade_id} missing {required.value}",
                        trade_id=trade_id,
                    )
                )
        positions = {state: states.index(state) for state in states}
        for left, right in zip(REQUIRED_LIFECYCLE, REQUIRED_LIFECYCLE[1:]):
            if (
                left in positions
                and right in positions
                and positions[left] > positions[right]
            ):
                violations.append(
                    GateCViolation(
                        code="GATE_C_STATE_ORDER",
                        message=f"{trade_id} has {right.value} before {left.value}",
                        trade_id=trade_id,
                    )
                )
        if GateCState.DECIDED in states and GateCState.RISK_CHECKED not in states:
            violations.append(
                GateCViolation(
                    code="GATE_C_DECISION_WITHOUT_RISK",
                    message=f"{trade_id} decided without risk check",
                    trade_id=trade_id,
                )
            )
    return violations


def _validate_event_bus_sequence(events: list[GateCEvent]) -> list[GateCViolation]:
    ordinals = [_message_ordinal(event.message_id) for event in events]
    if not ordinals:
        return [
            GateCViolation(
                code="GATE_C_EMPTY_EVENT_BUS",
                message="event bus has no lifecycle events",
            )
        ]
    expected = list(range(min(ordinals), max(ordinals) + 1))
    if sorted(ordinals) != expected:
        return [
            GateCViolation(
                code="GATE_C_EVENT_BUS_GAP",
                message=f"event bus sequence has gaps: {ordinals}",
            )
        ]
    return []


def _message_ordinal(message_id: str) -> int:
    try:
        return int(message_id.split("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid message_id: {message_id}") from exc
