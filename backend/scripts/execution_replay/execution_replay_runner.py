from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.market_state_labeling_v1 import label_market_states

SUMMARY_FILENAME = "execution_replay_v1.json"
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
DEFAULT_SURVIVOR_OPTIMIZATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_survival_optimization_v1.json"
)
DEFAULT_OOS_VALIDATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "oos_survivor_validation_v1.json"
)


def run_execution_replay(
    *,
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    survivor_optimization_path: Path | str = DEFAULT_SURVIVOR_OPTIMIZATION_PATH,
    oos_validation_path: Path | str = DEFAULT_OOS_VALIDATION_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    survivor_optimization = _load_json_object(survivor_optimization_path)
    oos_validation = _load_json_object(oos_validation_path)
    report = build_execution_replay_report(
        data=data,
        survivor_optimization=survivor_optimization,
        oos_validation=oos_validation,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_execution_replay_report(
    *,
    data: Sequence[Mapping[str, object]],
    survivor_optimization: Mapping[str, object],
    oos_validation: Mapping[str, object],
) -> dict[str, object]:
    labels = label_market_states(tuple(dict(row) for row in data))
    labels_by_event_id = {str(label["event_id"]): label for label in labels}
    survivor_regimes = _survivor_regimes(oos_validation)
    replay_records = _replay_records(
        data=data,
        labels_by_event_id=labels_by_event_id,
        survivor_regimes=survivor_regimes,
        survivor_optimization=survivor_optimization,
        oos_validation=oos_validation,
    )
    trades = tuple(record for record in replay_records if int(record["decision"]) != 0)
    metrics = _trade_metrics(trades)
    return {
        "input_rows": len(data),
        "replay_scope": _replay_scope(oos_validation),
        "survivor_regimes": survivor_regimes,
        "survivor_regime_count": len(survivor_regimes),
        "records_replayed": len(replay_records),
        "replay_records": replay_records,
        "metrics": metrics,
        "trades": metrics["trades"],
        "win_rate": metrics["win_rate"],
        "profit_factor": metrics["profit_factor"],
        "gross_pnl": metrics["gross_pnl"],
        "net_pnl": metrics["net_pnl"],
        "max_drawdown": metrics["max_drawdown"],
        "expectancy": metrics["expectancy"],
        "trade_distribution": _trade_distribution(trades),
        "artifact_consistency": _artifact_consistency(
            data=data,
            labels=labels,
            oos_validation=oos_validation,
            survivor_optimization=survivor_optimization,
            survivor_regimes=survivor_regimes,
            replay_records=replay_records,
        ),
        "source_constraints": {
            "input_artifacts": (
                "dataset_expansion_v1",
                "regime_survival_optimization_v1",
                "oos_survivor_validation_v1",
            ),
            "signal_generation_modified": False,
            "decision_logic_modified": False,
            "regime_model_modified": False,
            "survivor_selection_modified": False,
            "alpha_logic_modified": False,
            "learning_model_used": False,
            "optimization_used": False,
            "parameter_search_used": False,
            "tuning_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run execution replay harness v1")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--survivor-optimization",
        type=Path,
        default=DEFAULT_SURVIVOR_OPTIMIZATION_PATH,
    )
    parser.add_argument(
        "--oos-validation",
        type=Path,
        default=DEFAULT_OOS_VALIDATION_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_execution_replay(
        dataset_path=args.dataset,
        survivor_optimization_path=args.survivor_optimization,
        oos_validation_path=args.oos_validation,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _replay_records(
    *,
    data: Sequence[Mapping[str, object]],
    labels_by_event_id: Mapping[str, Mapping[str, object]],
    survivor_regimes: Sequence[str],
    survivor_optimization: Mapping[str, object],
    oos_validation: Mapping[str, object],
) -> tuple[dict[str, float | int | str | bool], ...]:
    rows_by_symbol = _rows_by_symbol(data)
    test_start = str(_mapping(oos_validation.get("split")).get("test_start"))
    test_end = str(_mapping(oos_validation.get("split")).get("test_end"))
    survivor_set = set(survivor_regimes)
    replay_records: list[dict[str, float | int | str | bool]] = []
    for symbol, rows in rows_by_symbol.items():
        for index, row in enumerate(rows[:-1]):
            timestamp = str(row["timestamp"])
            if timestamp < test_start or timestamp > test_end:
                continue
            next_row = rows[index + 1]
            label = labels_by_event_id[str(row["event_id"])]
            regime = _state_key(_mapping(label.get("state")))
            signal = _signal(regime, survivor_set)
            decision = _decision(signal)
            entry = _float_value(row.get("close"))
            exit_price = _float_value(next_row.get("close"))
            gross_pnl = (
                decision * ((exit_price - entry) / entry) if decision and entry else 0.0
            )
            regime_costs = _regime_costs(survivor_optimization, regime)
            slippage = regime_costs["slippage"] if decision else 0.0
            cost = regime_costs["cost"] if decision else 0.0
            net_pnl = gross_pnl - cost - slippage if decision else 0.0
            replay_records.append(
                {
                    "event_id": str(row["event_id"]),
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "regime": regime,
                    "is_survivor_regime": regime in survivor_set,
                    "signal": signal,
                    "decision": decision,
                    "entry": entry if decision else 0.0,
                    "exit": exit_price if decision else 0.0,
                    "cost": cost,
                    "slippage": slippage,
                    "gross_pnl": gross_pnl,
                    "pnl": net_pnl,
                }
            )
    return tuple(replay_records)


def _signal(regime: str, survivor_regimes: set[str]) -> int:
    if regime not in survivor_regimes:
        return 0
    trend = _regime_part(regime, index=1)
    if trend == "UP":
        return 1
    if trend == "DOWN":
        return -1
    return 0


def _decision(signal: int) -> int:
    if signal > 0:
        return 1
    if signal < 0:
        return -1
    return 0


def _trade_metrics(
    trades: Sequence[Mapping[str, object]],
) -> dict[str, float | int]:
    pnl_values = tuple(_float_value(trade.get("pnl")) for trade in trades)
    gross_values = tuple(_float_value(trade.get("gross_pnl")) for trade in trades)
    wins = tuple(value for value in pnl_values if value > 0.0)
    losses = tuple(value for value in pnl_values if value < 0.0)
    gross_profit = sum(value for value in pnl_values if value > 0.0)
    gross_loss = abs(sum(value for value in pnl_values if value < 0.0))
    trade_count = len(trades)
    return {
        "trades": trade_count,
        "win_rate": len(wins) / trade_count if trade_count else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else 0.0,
        "gross_pnl": sum(gross_values),
        "net_pnl": sum(pnl_values),
        "max_drawdown": _max_drawdown(pnl_values),
        "expectancy": sum(pnl_values) / trade_count if trade_count else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
    }


def _trade_distribution(
    trades: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    by_regime: dict[str, list[float]] = defaultdict(list)
    by_symbol: dict[str, list[float]] = defaultdict(list)
    for trade in trades:
        pnl = _float_value(trade.get("pnl"))
        by_regime[str(trade.get("regime"))].append(pnl)
        by_symbol[str(trade.get("symbol"))].append(pnl)
    return {
        "by_regime": {
            regime: _distribution_metrics(values)
            for regime, values in sorted(by_regime.items())
        },
        "by_symbol": {
            symbol: _distribution_metrics(values)
            for symbol, values in sorted(by_symbol.items())
        },
    }


def _distribution_metrics(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "trades": len(values),
        "net_pnl": sum(values),
        "expectancy": sum(values) / len(values) if values else 0.0,
        "win_rate": (
            sum(1 for value in values if value > 0.0) / len(values) if values else 0.0
        ),
    }


def _max_drawdown(pnl_values: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnl_values:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return max_drawdown


def _regime_costs(
    survivor_optimization: Mapping[str, object],
    regime: str,
) -> dict[str, float]:
    metrics = _mapping(
        _mapping(survivor_optimization.get("survival_score_per_regime")).get(regime)
    )
    return {
        "cost": _float_value(metrics.get("transition_impact")),
        "slippage": _float_value(metrics.get("slippage_cost")),
    }


def _survivor_regimes(oos_validation: Mapping[str, object]) -> tuple[str, ...]:
    test_phase = _mapping(oos_validation.get("test_phase"))
    regimes = test_phase.get("retained_survivor_regimes")
    if isinstance(regimes, list):
        return tuple(str(regime) for regime in regimes)
    if isinstance(regimes, tuple):
        return tuple(str(regime) for regime in regimes)
    train_phase = _mapping(oos_validation.get("train_phase"))
    train_regimes = train_phase.get("survivor_regimes")
    if isinstance(train_regimes, list | tuple):
        return tuple(str(regime) for regime in train_regimes)
    return ()


def _replay_scope(oos_validation: Mapping[str, object]) -> dict[str, object]:
    split = _mapping(oos_validation.get("split"))
    return {
        "scope": "oos_test_window",
        "start": str(split.get("test_start")),
        "end": str(split.get("test_end")),
        "source": "oos_survivor_validation_v1",
    }


def _artifact_consistency(
    *,
    data: Sequence[Mapping[str, object]],
    labels: Sequence[Mapping[str, object]],
    oos_validation: Mapping[str, object],
    survivor_optimization: Mapping[str, object],
    survivor_regimes: Sequence[str],
    replay_records: Sequence[Mapping[str, object]],
) -> dict[str, bool]:
    split = _mapping(oos_validation.get("split"))
    survival_by_regime = _mapping(
        survivor_optimization.get("survival_score_per_regime")
    )
    return {
        "dataset_rows_match_oos": len(data)
        == int(_float_value(oos_validation.get("input_rows"))),
        "labels_match_dataset_rows": len(labels) == len(data),
        "survivors_match_oos_retained": survivor_regimes
        == _survivor_regimes(oos_validation),
        "survivors_exist_in_survival_artifact": all(
            regime in survival_by_regime for regime in survivor_regimes
        ),
        "replay_uses_oos_test_window": bool(split.get("test_start"))
        and bool(split.get("test_end")),
        "every_record_has_required_replay_fields": all(
            _record_has_required_fields(record) for record in replay_records
        ),
    }


def _record_has_required_fields(record: Mapping[str, object]) -> bool:
    return all(
        key in record
        for key in (
            "regime",
            "decision",
            "entry",
            "exit",
            "cost",
            "slippage",
            "pnl",
        )
    )


def _rows_by_symbol(
    data: Sequence[Mapping[str, object]],
) -> dict[str, tuple[Mapping[str, object], ...]]:
    rows: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in data:
        rows[str(row["symbol"])].append(row)
    return {
        symbol: tuple(sorted(symbol_rows, key=lambda row: str(row["timestamp"])))
        for symbol, symbol_rows in sorted(rows.items())
    }


def _state_key(state: Mapping[str, object]) -> str:
    return "_".join(
        (
            str(state.get("volatility")),
            str(state.get("trend")),
            str(state.get("stress")),
        )
    )


def _regime_part(regime: str, *, index: int) -> str:
    parts = regime.split("_")
    if index >= len(parts):
        return ""
    return parts[index]


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Execution replay requires JSON object artifacts")
    return payload


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "execution_replay"


if __name__ == "__main__":
    main()
