from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from scripts.behavior_validation.baseline_generators import (
    generate_naive_momentum,
    generate_random_decisions,
)
from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.edge_validation_runner import _evaluate_mode
from scripts.behavior_validation.evaluation_runner import _generate_decisions
from scripts.behavior_validation.feature_transform import generate_signal_v2
from scripts.behavior_validation.statistical_edge_runner import (
    DEFAULT_SEEDS,
    _mean,
    _variance,
)

REGIMES = {
    "low": "low_vol",
    "mid": "mid_vol",
    "high": "high_vol",
}
ROBUST_STABILITY_THRESHOLD = 0.25


def run_regime_robustness_validation(
    dataset_path: Path | str,
    *,
    output_dir: Path | None = None,
    seeds: Sequence[int] = DEFAULT_SEEDS,
) -> dict[str, object]:
    data = normalize_dataset(load_historical_data(dataset_path))
    signals = generate_signal_v2(data)
    regimes = {
        regime_name: _evaluate_regime(
            signals=_signals_for_regime(signals, source_regime=source_regime),
            seeds=seeds,
        )
        for source_regime, regime_name in REGIMES.items()
    }
    stability = _regime_stability(regimes)
    report = {
        "regimes": regimes,
        "stability": stability,
        "classification": _classification(regimes, stability),
    }
    _write_report(output_dir or _default_output_dir(), report)
    return report


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regime robustness validation")
    parser.add_argument("historical_data", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_regime_robustness_validation(
        args.historical_data,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _evaluate_regime(
    *,
    signals: Sequence[dict[str, object]],
    seeds: Sequence[int],
) -> dict[str, float]:
    runs = tuple(_run_modes(signals, seed=seed) for seed in seeds)
    system_scores = tuple(_hit_rate(run, "system") for run in runs)
    return {
        "system": _mean(system_scores),
        "naive": _mean(tuple(_hit_rate(run, "naive") for run in runs)),
        "random": _mean(tuple(_hit_rate(run, "random") for run in runs)),
        "variance": _variance(system_scores),
    }


def _run_modes(
    signals: Sequence[dict[str, object]],
    *,
    seed: int,
) -> dict[str, dict[str, object]]:
    return {
        "random": _evaluate_mode(
            signals=signals,
            decisions=generate_random_decisions(signals, seed=seed),
        ),
        "naive": _evaluate_mode(
            signals=signals,
            decisions=generate_naive_momentum(signals),
        ),
        "system": _evaluate_mode(
            signals=signals,
            decisions=_generate_decisions(signals),
        ),
    }


def _signals_for_regime(
    signals: Sequence[dict[str, object]],
    *,
    source_regime: str,
) -> tuple[dict[str, object], ...]:
    return tuple(
        signal for signal in signals if signal.get("volatility_regime") == source_regime
    )


def _regime_stability(regimes: dict[str, dict[str, float]]) -> float:
    system_scores = tuple(regime["system"] for regime in regimes.values())
    return _variance(system_scores) ** 0.5


def _classification(regimes: dict[str, dict[str, float]], stability: float) -> str:
    winning_regimes = sum(
        1 for regime in regimes.values() if regime["system"] > regime["naive"]
    )
    if winning_regimes >= 2 and stability <= ROBUST_STABILITY_THRESHOLD:
        return "stable"
    if winning_regimes >= 1:
        return "partial"
    return "unstable"


def _hit_rate(run: dict[str, dict[str, object]], mode: str) -> float:
    return _float_value(run[mode].get("hit_rate"))


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "regime_robustness_v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
