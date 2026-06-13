from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.evaluation_runner import _generate_decisions
from scripts.behavior_validation.feature_transform import generate_signal_v2

REGIMES = ("low", "mid", "high")
TRANSACTION_COST = 0.0001
REGIME_PENALTIES = {
    "low": 0.00005,
    "mid": 0.0001,
    "high": 0.00015,
}


def run_economic_closure_validation(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    signals = generate_signal_v2(data)
    decisions = _generate_decisions(signals)
    future_return_by_event_id = _future_returns_by_event_id(data)
    signal_by_id = {str(signal["signal_id"]): signal for signal in signals}

    rewards = tuple(
        _reward(
            signal=signal_by_id[str(decision["source_signal_id"])],
            decision=decision,
            future_return=future_return_by_event_id.get(
                str(signal_by_id[str(decision["source_signal_id"])]["source_event_id"]),
                0.0,
            ),
        )
        for decision in decisions
        if str(decision["source_signal_id"]) in signal_by_id
    )
    report = _build_report(rewards)
    _write_report(output_dir or _default_output_dir(), report)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run economic closure validation")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_economic_closure_validation(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _reward(
    *,
    signal: dict[str, object],
    decision: dict[str, object],
    future_return: float,
) -> dict[str, float | str]:
    position = _float_value(decision.get("decision_score"))
    gross_pnl = position * future_return
    transaction_cost = TRANSACTION_COST * abs(position)
    regime = _regime(signal)
    regime_penalty = REGIME_PENALTIES[regime] * abs(position)
    net_pnl = gross_pnl - transaction_cost - regime_penalty
    return {
        "regime": regime,
        "gross_pnl": gross_pnl,
        "transaction_cost": transaction_cost,
        "regime_penalty": regime_penalty,
        "net_pnl": net_pnl,
    }


def _build_report(
    rewards: Sequence[dict[str, float | str]],
) -> dict[str, object]:
    total_pnl = sum(_float_value(reward.get("gross_pnl")) for reward in rewards)
    cost_adjusted_pnl = sum(_float_value(reward.get("net_pnl")) for reward in rewards)
    regime_pnl = _regime_pnl(rewards)
    return {
        "total_pnl": total_pnl,
        "regime_pnl": regime_pnl,
        "cost_adjusted_pnl": cost_adjusted_pnl,
        "edge_score": _ratio(cost_adjusted_pnl, len(rewards)),
    }


def _regime_pnl(
    rewards: Sequence[dict[str, float | str]],
) -> dict[str, float]:
    pnl_by_regime: dict[str, float] = defaultdict(float)
    for reward in rewards:
        regime = str(reward["regime"])
        pnl_by_regime[regime] += _float_value(reward.get("net_pnl"))
    return {regime: pnl_by_regime[regime] for regime in REGIMES}


def _future_returns_by_event_id(
    data: Sequence[dict[str, object]],
) -> dict[str, float]:
    rows_by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in data:
        rows_by_symbol[str(row["symbol"])].append(row)

    returns: dict[str, float] = {}
    for rows in rows_by_symbol.values():
        sorted_rows = sorted(rows, key=lambda row: str(row["timestamp"]))
        for current, next_row in zip(sorted_rows, sorted_rows[1:], strict=False):
            returns[str(current["event_id"])] = _future_return(
                current.get("close"),
                next_row.get("close"),
            )
    return returns


def _future_return(current_close: object, next_close: object) -> float:
    current = _float_value(current_close)
    if current == 0.0:
        return 0.0
    return (_float_value(next_close) - current) / current


def _regime(signal: dict[str, object]) -> str:
    regime = signal.get("volatility_regime")
    if regime in REGIMES:
        return str(regime)
    return "mid"


def _ratio(numerator: float, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "economic_closure_v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
