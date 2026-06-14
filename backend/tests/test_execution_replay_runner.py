import csv
import json
from pathlib import Path

from scripts.execution_replay.execution_replay_runner import (
    SUMMARY_FILENAME,
    build_execution_replay_report,
    run_execution_replay,
)

FORBIDDEN_SOURCE_TOKENS = (
    "fit(",
    "predict(",
    "GridSearch",
    "RandomForest",
    "xgboost",
    "from scripts.behavior_validation.execution_reality_model_v1 import",
    "from scripts.behavior_validation.regime_survival_optimization_v1 import",
)


def test_execution_replay_is_deterministic():
    inputs = _inputs()

    first = build_execution_replay_report(**inputs)
    second = build_execution_replay_report(**inputs)

    assert first == second
    assert first["records_replayed"] > 0
    assert first["metrics"]["trades"] > 0


def test_execution_replay_records_required_fields_and_survivor_decisions():
    report = build_execution_replay_report(**_inputs())
    trade_records = [
        record for record in report["replay_records"] if int(record["decision"]) != 0
    ]

    assert report["artifact_consistency"]["every_record_has_required_replay_fields"]
    assert all(record["is_survivor_regime"] for record in trade_records)
    assert all(record["signal"] == record["decision"] for record in trade_records)
    assert all(
        record["entry"] > 0.0 and record["exit"] > 0.0 for record in trade_records
    )


def test_execution_replay_reports_required_trade_distribution_metrics():
    report = build_execution_replay_report(**_inputs())
    metrics = report["metrics"]

    assert report["trades"] == metrics["trades"]
    assert report["win_rate"] == metrics["win_rate"]
    assert report["profit_factor"] == metrics["profit_factor"]
    assert report["gross_pnl"] == metrics["gross_pnl"]
    assert report["net_pnl"] == metrics["net_pnl"]
    assert report["max_drawdown"] == metrics["max_drawdown"]
    assert report["expectancy"] == metrics["expectancy"]
    assert "by_regime" in report["trade_distribution"]
    assert "by_symbol" in report["trade_distribution"]


def test_execution_replay_preserves_forbidden_logic_boundaries():
    source = Path(
        "backend/scripts/execution_replay/execution_replay_runner.py"
    ).read_text(encoding="utf-8")
    report = build_execution_replay_report(**_inputs())

    for token in FORBIDDEN_SOURCE_TOKENS:
        assert token not in source
    assert report["source_constraints"]["signal_generation_modified"] is False
    assert report["source_constraints"]["decision_logic_modified"] is False
    assert report["source_constraints"]["regime_model_modified"] is False
    assert report["source_constraints"]["survivor_selection_modified"] is False
    assert report["source_constraints"]["alpha_logic_modified"] is False
    assert report["source_constraints"]["learning_model_used"] is False
    assert report["source_constraints"]["optimization_used"] is False
    assert report["source_constraints"]["parameter_search_used"] is False
    assert report["source_constraints"]["tuning_used"] is False


def test_execution_replay_writes_required_artifact(tmp_path):
    dataset_dir = tmp_path / "expanded_dataset_v1"
    dataset_dir.mkdir()
    _write_dataset(dataset_dir)
    survivor_path = tmp_path / "regime_survival_optimization_v1.json"
    oos_path = tmp_path / "oos_survivor_validation_v1.json"
    inputs = _inputs()
    survivor_path.write_text(
        json.dumps(inputs["survivor_optimization"]),
        encoding="utf-8",
    )
    oos_path.write_text(json.dumps(inputs["oos_validation"]), encoding="utf-8")

    report = run_execution_replay(
        dataset_path=dataset_dir,
        survivor_optimization_path=survivor_path,
        oos_validation_path=oos_path,
        output_dir=tmp_path,
    )

    assert (tmp_path / SUMMARY_FILENAME).exists()
    assert report["input_rows"] == 12
    assert report["artifact_consistency"]["dataset_rows_match_oos"] is True


def _inputs() -> dict[str, object]:
    return {
        "data": _rows(),
        "survivor_optimization": {
            "survival_score_per_regime": {
                "HIGH_UP_STABLE": {
                    "is_viable": True,
                    "slippage_cost": 0.001,
                    "transition_impact": 0.001,
                },
                "MID_UP_STABLE": {
                    "is_viable": True,
                    "slippage_cost": 0.001,
                    "transition_impact": 0.001,
                },
                "LOW_UP_STABLE": {
                    "is_viable": True,
                    "slippage_cost": 0.001,
                    "transition_impact": 0.001,
                },
            }
        },
        "oos_validation": {
            "input_rows": 12,
            "split": {
                "test_start": "2024-01-01T01:00:00Z",
                "test_end": "2024-01-01T04:00:00Z",
            },
            "test_phase": {
                "retained_survivor_regimes": [
                    "HIGH_UP_STABLE",
                    "MID_UP_STABLE",
                    "LOW_UP_STABLE",
                ]
            },
        },
    }


def _rows() -> tuple[dict[str, object], ...]:
    rows = []
    for symbol in ("BTCUSDT", "ETHUSDT"):
        for index in range(6):
            rows.append(
                {
                    "event_id": f"{symbol}-2024-01-01T0{index}:00:00Z",
                    "row_number": len(rows) + 1,
                    "timestamp": f"2024-01-01T0{index}:00:00Z",
                    "symbol": symbol,
                    "open": 100.0 + index,
                    "high": 101.0 + index,
                    "low": 99.0 + index,
                    "close": 100.0 + index,
                    "volume": 1000.0,
                    "simulation_status": "accepted",
                }
            )
    return tuple(rows)


def _write_dataset(dataset_dir: Path) -> None:
    by_symbol: dict[str, list[dict[str, object]]] = {"BTCUSDT": [], "ETHUSDT": []}
    for row in _rows():
        by_symbol[str(row["symbol"])].append(row)
    for symbol, rows in by_symbol.items():
        with (dataset_dir / f"{symbol}_candles.csv").open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "timestamp",
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "simulation_status",
                ),
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        "timestamp": row["timestamp"],
                        "symbol": row["symbol"],
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"],
                        "simulation_status": row["simulation_status"],
                    }
                )
