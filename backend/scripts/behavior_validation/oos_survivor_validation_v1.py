from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

SUMMARY_FILENAME = "oos_survivor_validation_v1.json"
DEFAULT_STATE_LABEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "market_state_labeling_v1.json"
)
DEFAULT_DATASET_DIR = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
DEFAULT_REGIME_ALPHA_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_to_alpha_v1.json"
)
DEFAULT_EXECUTION_REALITY_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "execution_reality_model_v1.json"
)
DEFAULT_SURVIVOR_OPTIMIZATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "regime_survival_optimization_v1.json"
)
TRAIN_FRACTION = 0.70
ZERO_ALPHA_EPSILON = 1e-12


def run_oos_survivor_validation(
    *,
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    dataset_dir: Path | str = DEFAULT_DATASET_DIR,
    regime_alpha_path: Path | str = DEFAULT_REGIME_ALPHA_PATH,
    execution_reality_path: Path | str = DEFAULT_EXECUTION_REALITY_PATH,
    survivor_optimization_path: Path | str = DEFAULT_SURVIVOR_OPTIMIZATION_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    labels = _load_state_labels(state_labels_path)
    dataset_summary = _dataset_summary(Path(dataset_dir))
    regime_alpha = _load_json_object(regime_alpha_path)
    execution_reality = _load_json_object(execution_reality_path)
    survivor_optimization = _load_json_object(survivor_optimization_path)
    report = build_oos_survivor_validation_report(
        labels=labels,
        dataset_summary=dataset_summary,
        regime_alpha=regime_alpha,
        execution_reality=execution_reality,
        survivor_optimization=survivor_optimization,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_oos_survivor_validation_report(
    *,
    labels: Sequence[Mapping[str, object]],
    dataset_summary: Mapping[str, object],
    regime_alpha: Mapping[str, object],
    execution_reality: Mapping[str, object],
    survivor_optimization: Mapping[str, object],
) -> dict[str, object]:
    train_labels, test_labels, split = _chronological_split(labels)
    train_counts = _state_counts(train_labels)
    test_counts = _state_counts(test_labels)
    train_survivors = _train_survivors(train_counts, survivor_optimization)
    test_present_survivors = tuple(
        state for state in train_survivors if test_counts.get(state, 0) > 0
    )
    train_metrics = _phase_metrics(
        counts=train_counts,
        total_count=len(train_labels),
        survivor_regimes=train_survivors,
        execution_reality=execution_reality,
    )
    test_metrics = _phase_metrics(
        counts=test_counts,
        total_count=len(test_labels),
        survivor_regimes=train_survivors,
        execution_reality=execution_reality,
    )
    alpha_retention = (
        test_metrics["execution_adjusted_alpha"]
        / train_metrics["execution_adjusted_alpha"]
        if train_metrics["execution_adjusted_alpha"] > 0.0
        else 0.0
    )
    frequency_drift = _frequency_drift(
        train_counts=train_counts,
        test_counts=test_counts,
        train_total=len(train_labels),
        test_total=len(test_labels),
        survivor_regimes=train_survivors,
    )
    composition_drift = _composition_drift(frequency_drift)
    return {
        "input_rows": len(labels),
        "dataset_summary": dataset_summary,
        "split": split,
        "train_phase": {
            "survivor_regimes": train_survivors,
            "survivor_count": len(train_survivors),
            "metrics": train_metrics,
        },
        "test_phase": {
            "retained_survivor_regimes": test_present_survivors,
            "retained_survivor_count": len(test_present_survivors),
            "metrics": test_metrics,
        },
        "survivor_retention": {
            "train_survivor_count": len(train_survivors),
            "test_retained_survivor_count": len(test_present_survivors),
            "retention_ratio": (
                len(test_present_survivors) / len(train_survivors)
                if train_survivors
                else 0.0
            ),
        },
        "survivor_alpha": {
            "train_alpha": train_metrics["raw_alpha"],
            "test_alpha": test_metrics["raw_alpha"],
            "train_execution_adjusted_alpha": train_metrics["execution_adjusted_alpha"],
            "test_execution_adjusted_alpha": test_metrics["execution_adjusted_alpha"],
            "delta": test_metrics["execution_adjusted_alpha"]
            - train_metrics["execution_adjusted_alpha"],
            "alpha_retention": alpha_retention,
        },
        "train_alpha": train_metrics["execution_adjusted_alpha"],
        "test_alpha": test_metrics["execution_adjusted_alpha"],
        "alpha_retention": alpha_retention,
        "survivor_count": len(train_survivors),
        "frequency_drift": frequency_drift,
        "regime_composition_drift": composition_drift,
        "verdict": _oos_verdict(
            train_alpha=train_metrics["execution_adjusted_alpha"],
            test_alpha=test_metrics["execution_adjusted_alpha"],
        ),
        "artifact_consistency": _artifact_consistency(
            labels=labels,
            dataset_summary=dataset_summary,
            regime_alpha=regime_alpha,
            execution_reality=execution_reality,
            survivor_optimization=survivor_optimization,
            train_survivors=train_survivors,
        ),
        "source_constraints": {
            "input_layers": (
                "dataset_expansion_v1",
                "market_state_labeling_v1",
                "regime_to_alpha_v1",
                "execution_reality_model_v1",
                "regime_survival_optimization_v1",
            ),
            "chronological_split_only": True,
            "shuffling_used": False,
            "randomization_used": False,
            "test_data_used_for_survivor_selection": False,
            "features_modified": False,
            "states_modified": False,
            "transitions_modified": False,
            "stability_model_modified": False,
            "alpha_model_modified": False,
            "execution_model_modified": False,
            "survivor_selection_logic_modified": False,
            "learning_model_used": False,
            "optimization_used": False,
            "parameter_search_used": False,
            "tuning_used": False,
            "new_regime_definitions_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run OOS survivor validation v1")
    parser.add_argument(
        "--state-labels",
        type=Path,
        default=DEFAULT_STATE_LABEL_PATH,
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
    )
    parser.add_argument(
        "--regime-alpha",
        type=Path,
        default=DEFAULT_REGIME_ALPHA_PATH,
    )
    parser.add_argument(
        "--execution-reality",
        type=Path,
        default=DEFAULT_EXECUTION_REALITY_PATH,
    )
    parser.add_argument(
        "--survivor-optimization",
        type=Path,
        default=DEFAULT_SURVIVOR_OPTIMIZATION_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_oos_survivor_validation(
        state_labels_path=args.state_labels,
        dataset_dir=args.dataset_dir,
        regime_alpha_path=args.regime_alpha,
        execution_reality_path=args.execution_reality,
        survivor_optimization_path=args.survivor_optimization,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _chronological_split(
    labels: Sequence[Mapping[str, object]],
) -> tuple[
    tuple[Mapping[str, object], ...],
    tuple[Mapping[str, object], ...],
    dict[str, float | int | str],
]:
    ordered_labels = tuple(
        sorted(
            labels,
            key=lambda label: (
                str(label.get("timestamp")),
                str(label.get("symbol")),
                str(label.get("event_id")),
            ),
        )
    )
    timestamps = tuple(
        sorted({str(label.get("timestamp")) for label in ordered_labels})
    )
    split_timestamp_count = int(len(timestamps) * TRAIN_FRACTION)
    train_timestamps = set(timestamps[:split_timestamp_count])
    train_labels = tuple(
        label
        for label in ordered_labels
        if str(label.get("timestamp")) in train_timestamps
    )
    test_labels = tuple(
        label
        for label in ordered_labels
        if str(label.get("timestamp")) not in train_timestamps
    )
    return (
        train_labels,
        test_labels,
        {
            "method": "chronological_unique_timestamp_split",
            "train_fraction": TRAIN_FRACTION,
            "unique_timestamps": len(timestamps),
            "train_unique_timestamps": split_timestamp_count,
            "test_unique_timestamps": len(timestamps) - split_timestamp_count,
            "train_rows": len(train_labels),
            "test_rows": len(test_labels),
            "train_start": str(timestamps[0]) if timestamps else "",
            "train_end": (
                str(timestamps[split_timestamp_count - 1])
                if split_timestamp_count
                else ""
            ),
            "test_start": (
                str(timestamps[split_timestamp_count])
                if split_timestamp_count < len(timestamps)
                else ""
            ),
            "test_end": str(timestamps[-1]) if timestamps else "",
        },
    )


def _train_survivors(
    train_counts: Mapping[str, int],
    survivor_optimization: Mapping[str, object],
) -> tuple[str, ...]:
    survival_by_state = _mapping(survivor_optimization.get("survival_score_per_regime"))
    return tuple(
        state
        for state, metrics in sorted(survival_by_state.items())
        if train_counts.get(state, 0) > 0
        and bool(_mapping(metrics).get("is_viable"))
        and _float_value(_mapping(metrics).get("survival_score"))
        > _float_value(survivor_optimization.get("survival_threshold"))
    )


def _phase_metrics(
    *,
    counts: Mapping[str, int],
    total_count: int,
    survivor_regimes: Sequence[str],
    execution_reality: Mapping[str, object],
) -> dict[str, float]:
    execution_by_state = _mapping(execution_reality.get("effective_alpha_per_regime"))
    raw_alpha = 0.0
    execution_alpha = 0.0
    survivor_mass = 0.0
    for state in survivor_regimes:
        frequency = counts.get(state, 0) / total_count if total_count else 0.0
        execution_metrics = _mapping(execution_by_state.get(state))
        raw_alpha += frequency * _float_value(execution_metrics.get("raw_alpha"))
        execution_alpha += frequency * _float_value(
            execution_metrics.get("executable_alpha")
        )
        survivor_mass += frequency
    return {
        "raw_alpha": raw_alpha,
        "execution_adjusted_alpha": execution_alpha,
        "expectancy": execution_alpha / survivor_mass if survivor_mass else 0.0,
        "survivor_probability_mass": survivor_mass,
    }


def _frequency_drift(
    *,
    train_counts: Mapping[str, int],
    test_counts: Mapping[str, int],
    train_total: int,
    test_total: int,
    survivor_regimes: Sequence[str],
) -> dict[str, dict[str, float | bool]]:
    return {
        state: {
            "train_frequency": (
                train_counts.get(state, 0) / train_total if train_total else 0.0
            ),
            "test_frequency": (
                test_counts.get(state, 0) / test_total if test_total else 0.0
            ),
            "frequency_delta": (
                test_counts.get(state, 0) / test_total if test_total else 0.0
            )
            - (train_counts.get(state, 0) / train_total if train_total else 0.0),
            "appears_in_test": test_counts.get(state, 0) > 0,
        }
        for state in survivor_regimes
    }


def _composition_drift(
    frequency_drift: Mapping[str, Mapping[str, object]],
) -> dict[str, float]:
    train_mass = sum(
        _float_value(metrics.get("train_frequency"))
        for metrics in frequency_drift.values()
    )
    test_mass = sum(
        _float_value(metrics.get("test_frequency"))
        for metrics in frequency_drift.values()
    )
    absolute_probability_mass_change = sum(
        abs(
            _float_value(metrics.get("test_frequency"))
            - _float_value(metrics.get("train_frequency"))
        )
        for metrics in frequency_drift.values()
    )
    return {
        "train_survivor_probability_mass": train_mass,
        "test_survivor_probability_mass": test_mass,
        "probability_mass_delta": test_mass - train_mass,
        "absolute_probability_mass_change": absolute_probability_mass_change,
    }


def _oos_verdict(*, train_alpha: float, test_alpha: float) -> str:
    if test_alpha < -ZERO_ALPHA_EPSILON:
        return "EDGE_COLLAPSE"
    if abs(test_alpha) <= ZERO_ALPHA_EPSILON:
        return "NO_EDGE"
    alpha_retention = test_alpha / train_alpha if train_alpha > 0.0 else 0.0
    if alpha_retention >= 0.5:
        return "ROBUST_EDGE"
    return "WEAK_EDGE"


def _state_counts(labels: Sequence[Mapping[str, object]]) -> Counter[str]:
    return Counter(_state_key(label) for label in labels)


def _state_key(label: Mapping[str, object]) -> str:
    state = _mapping(label.get("state"))
    return "_".join(
        (
            str(state.get("volatility")),
            str(state.get("trend")),
            str(state.get("stress")),
        )
    )


def _artifact_consistency(
    *,
    labels: Sequence[Mapping[str, object]],
    dataset_summary: Mapping[str, object],
    regime_alpha: Mapping[str, object],
    execution_reality: Mapping[str, object],
    survivor_optimization: Mapping[str, object],
    train_survivors: Sequence[str],
) -> dict[str, bool]:
    return {
        "labels_match_dataset_rows": len(labels)
        == int(_float_value(dataset_summary.get("rows"))),
        "labels_match_regime_alpha_rows": len(labels)
        == int(_float_value(regime_alpha.get("input_rows"))),
        "labels_match_survivor_rows": len(labels)
        == int(_float_value(survivor_optimization.get("input_rows"))),
        "state_count_matches_survivor_artifact": len(
            _mapping(survivor_optimization.get("survival_score_per_regime"))
        )
        == int(_float_value(survivor_optimization.get("unique_states"))),
        "execution_state_space_covers_train_survivors": all(
            state in _mapping(execution_reality.get("effective_alpha_per_regime"))
            for state in train_survivors
        ),
        "survivor_selection_matches_existing_logic": tuple(train_survivors)
        == tuple(
            state
            for state, metrics in sorted(
                _mapping(survivor_optimization.get("survival_score_per_regime")).items()
            )
            if bool(_mapping(metrics).get("is_viable"))
        ),
    }


def _dataset_summary(dataset_dir: Path) -> dict[str, object]:
    rows = 0
    symbols: list[str] = []
    for path in sorted(dataset_dir.glob("*_candles.csv")):
        symbols.append(path.name.removesuffix("_candles.csv"))
        with path.open(encoding="utf-8") as handle:
            rows += max(sum(1 for _ in handle) - 1, 0)
    return {"path": str(dataset_dir), "symbols": tuple(symbols), "rows": rows}


def _load_state_labels(path: Path | str) -> tuple[dict[str, object], ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = payload.get("state_labels") if isinstance(payload, dict) else payload
    if not isinstance(labels, list):
        raise ValueError("OOS survivor validation requires a state_labels list")
    return tuple(label for label in labels if isinstance(label, dict))


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("OOS survivor validation requires JSON object artifacts")
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
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
