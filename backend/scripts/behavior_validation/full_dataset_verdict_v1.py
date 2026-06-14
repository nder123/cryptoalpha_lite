from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scripts.behavior_validation.economic_closure_runner import (
    run_economic_closure_validation,
)
from scripts.behavior_validation.evaluation_runner import run_historical_evaluation
from scripts.behavior_validation.regime_robustness_runner import (
    run_regime_robustness_validation,
)
from scripts.behavior_validation.system_v2_edge_runner import (
    run_system_v2_edge_validation,
)

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
OUTPUT_FILENAME = "full_dataset_verdict_v1.json"


def run_full_dataset_verdict(
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    target_output_dir = output_dir or _default_output_dir()
    evaluation = run_historical_evaluation(dataset_path, output_dir=target_output_dir)
    system_v2 = run_system_v2_edge_validation(
        dataset_path, output_dir=target_output_dir
    )
    regime = run_regime_robustness_validation(
        dataset_path, output_dir=target_output_dir
    )
    economic = run_economic_closure_validation(
        dataset_path, output_dir=target_output_dir
    )
    report = build_full_dataset_verdict(
        evaluation=evaluation,
        system_v2=system_v2,
        regime=regime,
        economic=economic,
    )
    _write_report(target_output_dir, report)
    return report


def build_full_dataset_verdict(
    *,
    evaluation: dict[str, object],
    system_v2: dict[str, object],
    regime: dict[str, object],
    economic: dict[str, object],
) -> dict[str, object]:
    metrics_v1 = _dict_value(evaluation, "metrics_v1")
    signals_per_symbol = _dict_value(metrics_v1, "signals_per_symbol")
    random_baseline = _dict_value(system_v2, "random")
    naive_baseline = _dict_value(system_v2, "naive")
    system_result = _dict_value(system_v2, "system")
    regime_breakdown = {
        "economic_pnl": _dict_value(economic, "regime_pnl"),
        "robustness": _dict_value(regime, "regimes"),
        "classification": regime.get("classification"),
        "stability": _float_value(regime.get("stability")),
    }
    return {
        "dataset_rows": _int_value(metrics_v1.get("signals_generated")),
        "symbols": len(signals_per_symbol),
        "edge_score": _float_value(economic.get("edge_score")),
        "cost_adjusted_pnl": _float_value(economic.get("cost_adjusted_pnl")),
        "random_baseline": random_baseline,
        "naive_baseline": naive_baseline,
        "system_result": {
            **system_result,
            "case": system_v2.get("case"),
            "stability": _dict_value(system_v2, "stability").get("system"),
        },
        "regime_breakdown": regime_breakdown,
        "verdict": _verdict(
            economic=economic,
            system_v2=system_v2,
            regime=regime,
        ),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build full dataset verdict v1")
    parser.add_argument(
        "historical_data",
        nargs="?",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_full_dataset_verdict(args.historical_data, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


def _verdict(
    *,
    economic: dict[str, object],
    system_v2: dict[str, object],
    regime: dict[str, object],
) -> str:
    edge_score = _float_value(economic.get("edge_score"))
    cost_adjusted_pnl = _float_value(economic.get("cost_adjusted_pnl"))
    system = _dict_value(system_v2, "system")
    random = _dict_value(system_v2, "random")
    naive = _dict_value(system_v2, "naive")
    system_hit_rate = _float_value(system.get("mean_hit_rate"))
    baseline_hit_rate = max(
        _float_value(random.get("mean_hit_rate")),
        _float_value(naive.get("mean_hit_rate")),
    )

    if edge_score <= 0.0 or cost_adjusted_pnl <= 0.0:
        return "NO_EDGE"
    if system_hit_rate <= baseline_hit_rate:
        return "NO_EDGE"
    if (
        system_v2.get("case") == "CASE_A_EDGE_EXISTS"
        and regime.get("classification") == "stable"
    ):
        return "STABLE_EDGE"
    return "WEAK_EDGE"


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / OUTPUT_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _dict_value(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key, {})
    if isinstance(value, dict):
        return value
    return {}


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return 0


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
