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
from scripts.behavior_validation.evaluation_runner import (
    _generate_decisions,
    _generate_signals,
)


def run_diagnosis(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    data_check = check_data_variance(data)
    signal_check = check_signal_sensitivity(data)
    decision_check = check_decision_sensitivity(data)
    report = {
        "data": data_check["classification"],
        "signal": signal_check["classification"],
        "decision": decision_check["classification"],
        "details": {
            "data": data_check,
            "signal": signal_check,
            "decision": decision_check,
        },
    }
    _write_diagnosis(output_dir or _default_output_dir(), report)
    return report


def check_data_variance(data: Sequence[dict[str, object]]) -> dict[str, object]:
    symbol_returns = _returns_by_symbol(data)
    returns = tuple(
        absolute_return
        for values in symbol_returns.values()
        for absolute_return in values
    )
    volatility_proxy = _mean(returns)
    price_variance = _mean(tuple(value * value for value in returns))
    trend_strength_proxy = _mean(
        tuple(_trend_strength(rows) for rows in _rows_by_symbol(data).values())
    )

    return {
        "classification": _variance_classification(volatility_proxy),
        "price_variance": price_variance,
        "volatility_proxy": volatility_proxy,
        "trend_strength_proxy": trend_strength_proxy,
    }


def check_signal_sensitivity(data: Sequence[dict[str, object]]) -> dict[str, object]:
    baseline = _signal_signature(_generate_signals(data))
    shuffled = _signal_signature(_generate_signals(_shuffle_candles(data)))
    changed_ratio = _changed_ratio(baseline, shuffled)

    return {
        "classification": "sensitive" if changed_ratio > 0.0 else "insensitive",
        "changed_ratio": changed_ratio,
    }


def check_decision_sensitivity(data: Sequence[dict[str, object]]) -> dict[str, object]:
    signals = _generate_signals(data)
    baseline = _decision_signature(_generate_decisions(signals))
    perturbed = _decision_signature(_generate_decisions(_perturb_signals(signals)))
    changed_ratio = _changed_ratio(baseline, perturbed)

    return {
        "classification": _decision_classification(changed_ratio),
        "changed_ratio": changed_ratio,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run behavior edge diagnosis")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_diagnosis(args.historical_data, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


def _returns_by_symbol(
    data: Sequence[dict[str, object]]
) -> dict[str, tuple[float, ...]]:
    returns = {}
    for symbol, rows in _rows_by_symbol(data).items():
        sorted_rows = sorted(rows, key=lambda row: str(row["timestamp"]))
        closes = tuple(_float_value(row.get("close")) for row in sorted_rows)
        returns[symbol] = tuple(
            abs(_ratio(current - previous, previous))
            for previous, current in zip(closes, closes[1:], strict=False)
        )
    return returns


def _rows_by_symbol(
    data: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in data:
        rows[str(row["symbol"])].append(row)
    return {symbol: tuple(symbol_rows) for symbol, symbol_rows in sorted(rows.items())}


def _trend_strength(rows: Sequence[dict[str, object]]) -> float:
    sorted_rows = sorted(rows, key=lambda row: str(row["timestamp"]))
    closes = tuple(_float_value(row.get("close")) for row in sorted_rows)
    if len(closes) < 2:
        return 0.0

    net_move = abs(closes[-1] - closes[0])
    path_move = sum(
        abs(current - previous)
        for previous, current in zip(closes, closes[1:], strict=False)
    )
    return _ratio(net_move, path_move)


def _variance_classification(volatility_proxy: float) -> str:
    if volatility_proxy < 0.001:
        return "low_variance"
    if volatility_proxy < 0.01:
        return "medium"
    return "high"


def _decision_classification(changed_ratio: float) -> str:
    if changed_ratio == 0.0:
        return "dead"
    if changed_ratio < 0.25:
        return "stable"
    return "reactive"


def _shuffle_candles(
    data: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(reversed(data))


def _perturb_signals(
    signals: Sequence[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            **signal,
            "price_probe_delta": 0.001,
        }
        for signal in signals
    )


def _signal_signature(
    signals: Sequence[dict[str, object]],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            signal.get("source_event_id"),
            signal.get("symbol"),
            signal.get("timestamp"),
            signal.get("simulation_status"),
        )
        for signal in signals
    )


def _decision_signature(
    decisions: Sequence[dict[str, object]],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            decision.get("source_signal_id"),
            decision.get("symbol"),
            decision.get("timestamp"),
            decision.get("simulation_status"),
        )
        for decision in decisions
    )


def _changed_ratio(
    baseline: Sequence[tuple[object, ...]],
    candidate: Sequence[tuple[object, ...]],
) -> float:
    denominator = max(len(baseline), len(candidate))
    if denominator == 0:
        return 0.0

    changed = sum(
        1 for left, right in zip(baseline, candidate, strict=False) if left != right
    )
    changed += abs(len(baseline) - len(candidate))
    return changed / denominator


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_diagnosis(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "diagnosis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
