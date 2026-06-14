from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.state_stability_model_v1 import state_runs_by_symbol
from scripts.behavior_validation.state_transition_model_v1 import (
    load_state_labels,
    state_sequences_by_symbol,
)

SUMMARY_FILENAME = "regime_forecastability_v1.json"
DEFAULT_STATE_LABEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "market_state_labeling_v1.json"
)
DEFAULT_TRANSITION_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "state_transition_model_v1.json"
)
DEFAULT_STABILITY_MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "state_stability_model_v1.json"
)
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
BTC_SYMBOL = "BTCUSDT"
HAZARD_WINDOWS = (1, 2, 3, 5, 10)
LEAD_WINDOWS = (1, 3, 5)


def run_regime_forecastability(
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    *,
    transition_model_path: Path | str = DEFAULT_TRANSITION_MODEL_PATH,
    stability_model_path: Path | str = DEFAULT_STABILITY_MODEL_PATH,
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    labels = load_state_labels(state_labels_path)
    transition_model = _load_json_object(transition_model_path)
    stability_model = _load_json_object(stability_model_path)
    dataset_rows = len(normalize_dataset(load_historical_data(dataset_path)))
    report = build_regime_forecastability_report(
        labels=labels,
        transition_model=transition_model,
        stability_model=stability_model,
        dataset_rows=dataset_rows,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_regime_forecastability_report(
    *,
    labels: Sequence[dict[str, object]],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    dataset_rows: int,
) -> dict[str, object]:
    sequences = state_sequences_by_symbol(labels)
    runs_by_symbol = state_runs_by_symbol(sequences)
    transition_matrix = _float_mapping(transition_model.get("global_transition_matrix"))
    state_space = tuple(
        sorted({state for sequence in sequences.values() for state in sequence})
    )
    random_stay_probability = 1.0 / len(state_space) if state_space else 0.0
    stay_by_state = _stay_probabilities_per_state(state_space, transition_matrix)
    hazard_curves = _hazard_curves(runs_by_symbol)
    per_state = _per_state_forecastability(
        state_space=state_space,
        stay_by_state=stay_by_state,
        hazard_curves=hazard_curves,
        random_stay_probability=random_stay_probability,
    )
    symbol_scores = _cross_symbol_scores(
        sequences=sequences,
        random_stay_probability=random_stay_probability,
    )
    return {
        "dataset_rows": dataset_rows,
        "state_label_rows": len(labels),
        "symbols": len(sequences),
        "unique_states": len(state_space),
        "stay_probabilities_per_state": stay_by_state,
        "hazard_curves": hazard_curves,
        "forecastability_score_per_state": per_state,
        "global_forecastability_index": _global_forecastability_index(
            sequences=sequences,
            stay_by_state=stay_by_state,
            random_stay_probability=random_stay_probability,
        ),
        "baseline_random_comparison": {
            "state_space_size": len(state_space),
            "random_same_state_probability": random_stay_probability,
            "forecastability_above_random": _mean(tuple(stay_by_state.values()))
            > random_stay_probability,
        },
        "lead_lag_signal_check": _lead_lag_signal_check(
            sequences=sequences,
            stay_by_state=stay_by_state,
        ),
        "cross_symbol_comparison": symbol_scores,
        "model_consistency": _model_consistency(
            labels=labels,
            state_space=state_space,
            transition_model=transition_model,
            stability_model=stability_model,
            symbol_scores=symbol_scores,
        ),
        "source_constraints": {
            "input_layers": (
                "market_state_labeling_v1",
                "state_transition_model_v1",
                "state_stability_model_v1",
                "expanded_dataset_v1",
            ),
            "external_sources_used": False,
            "new_features_created": False,
            "learning_model_used": False,
            "parameter_search_used": False,
            "trading_rules_used": False,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run regime forecastability v1")
    parser.add_argument(
        "state_labels",
        nargs="?",
        type=Path,
        default=DEFAULT_STATE_LABEL_PATH,
    )
    parser.add_argument(
        "--transition-model",
        type=Path,
        default=DEFAULT_TRANSITION_MODEL_PATH,
    )
    parser.add_argument(
        "--stability-model",
        type=Path,
        default=DEFAULT_STABILITY_MODEL_PATH,
    )
    parser.add_argument(
        "--dataset",
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
    report = run_regime_forecastability(
        args.state_labels,
        transition_model_path=args.transition_model,
        stability_model_path=args.stability_model,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _per_state_forecastability(
    *,
    state_space: Sequence[str],
    stay_by_state: Mapping[str, float],
    hazard_curves: Mapping[str, Mapping[str, object]],
    random_stay_probability: float,
) -> dict[str, dict[str, object]]:
    scores = {}
    for state in state_space:
        stay_probability = stay_by_state.get(state, 0.0)
        hazard_curve = _mapping(hazard_curves.get(state))
        cumulative = _float_mapping(hazard_curve.get("cumulative_exit_probability"))
        one_step_exit = 1.0 - stay_probability
        scores[state] = {
            "stay_probability": stay_probability,
            "one_step_transition_risk": one_step_exit,
            "forecastability_score": stay_probability - random_stay_probability,
            "forecastability_above_random": stay_probability > random_stay_probability,
            "hazard_non_uniform": _hazard_non_uniform(cumulative),
            "hazard_slope_1_to_5": cumulative.get("5", 0.0) - cumulative.get("1", 0.0),
            "risk_class": _risk_class(stay_probability),
        }
    return scores


def _global_forecastability_index(
    *,
    sequences: Mapping[str, Sequence[str]],
    stay_by_state: Mapping[str, float],
    random_stay_probability: float,
) -> dict[str, float | bool]:
    state_counts: Counter[str] = Counter(
        state for sequence in sequences.values() for state in sequence
    )
    total = sum(state_counts.values())
    weighted_stay = (
        sum(
            stay_by_state.get(state, 0.0) * count
            for state, count in state_counts.items()
        )
        / total
        if total
        else 0.0
    )
    return {
        "weighted_stay_probability": weighted_stay,
        "random_same_state_probability": random_stay_probability,
        "forecastability_gain_vs_random": weighted_stay - random_stay_probability,
        "forecastability_index": weighted_stay,
        "forecastability_above_random": weighted_stay > random_stay_probability,
    }


def _stay_probabilities_per_state(
    state_space: Sequence[str],
    transition_matrix: Mapping[str, float],
) -> dict[str, float]:
    return {
        state: transition_matrix.get(f"{state} -> {state}", 0.0)
        for state in state_space
    }


def _hazard_curves(
    runs_by_symbol: Mapping[str, Sequence[dict[str, object]]],
) -> dict[str, dict[str, object]]:
    runs = tuple(run for symbol_runs in runs_by_symbol.values() for run in symbol_runs)
    curves = {}
    for state in sorted({str(run["state"]) for run in runs}):
        state_runs = tuple(run for run in runs if str(run["state"]) == state)
        terminal_adjusted = tuple(
            run for run in state_runs if run.get("next_state") is not None
        )
        durations = tuple(_float_value(run["duration"]) for run in terminal_adjusted)
        curves[state] = {
            "observed_runs": len(state_runs),
            "observed_exits": len(durations),
            "step_hazard": {
                str(window): _step_hazard(durations, window)
                for window in HAZARD_WINDOWS
            },
            "cumulative_exit_probability": {
                str(window): _cumulative_exit_probability(durations, window)
                for window in HAZARD_WINDOWS
            },
            "decay_shape": _decay_shape(durations),
        }
    return curves


def _lead_lag_signal_check(
    *,
    sequences: Mapping[str, Sequence[str]],
    stay_by_state: Mapping[str, float],
) -> dict[str, object]:
    per_window = {
        str(window): _lead_window_summary(
            sequences=sequences,
            stay_by_state=stay_by_state,
            lead_window=window,
        )
        for window in LEAD_WINDOWS
    }
    return {
        "risk_signal": "one_step_transition_risk_by_current_state",
        "per_lead_window": per_window,
        "aggregate_risk_rises_before_shift": any(
            _mapping(summary).get("risk_rises_before_shift") is True
            for summary in per_window.values()
        ),
    }


def _lead_window_summary(
    *,
    sequences: Mapping[str, Sequence[str]],
    stay_by_state: Mapping[str, float],
    lead_window: int,
) -> dict[str, float | bool]:
    pre_shift_risks: list[float] = []
    stable_risks: list[float] = []
    for sequence in sequences.values():
        for index, state in enumerate(sequence[:-1]):
            risk = 1.0 - stay_by_state.get(state, 0.0)
            future = sequence[index + 1 : index + lead_window + 1]
            exits_within_window = any(next_state != state for next_state in future)
            remains_same = len(future) == lead_window and all(
                next_state == state for next_state in future
            )
            if exits_within_window:
                pre_shift_risks.append(risk)
            elif remains_same:
                stable_risks.append(risk)
    pre_shift_mean = _mean(tuple(pre_shift_risks))
    stable_mean = _mean(tuple(stable_risks))
    return {
        "lead_window": lead_window,
        "pre_shift_mean_transition_risk": pre_shift_mean,
        "stable_mean_transition_risk": stable_mean,
        "risk_lift_before_shift": pre_shift_mean - stable_mean,
        "risk_rises_before_shift": pre_shift_mean > stable_mean,
        "pre_shift_samples": len(pre_shift_risks),
        "stable_samples": len(stable_risks),
    }


def _cross_symbol_scores(
    *,
    sequences: Mapping[str, Sequence[str]],
    random_stay_probability: float,
) -> dict[str, object]:
    per_symbol = {}
    for symbol, sequence in sorted(sequences.items()):
        same_count = sum(
            1
            for current, next_state in zip(sequence, sequence[1:], strict=False)
            if current == next_state
        )
        transition_count = max(len(sequence) - 1, 0)
        stay_probability = same_count / transition_count if transition_count else 0.0
        per_symbol[symbol] = {
            "stay_probability": stay_probability,
            "forecastability_gain_vs_random": stay_probability
            - random_stay_probability,
            "transition_count": transition_count,
        }
    btc_score = _float_value(
        _mapping(per_symbol.get(BTC_SYMBOL)).get("stay_probability")
    )
    alt_scores = tuple(
        _float_value(_mapping(metrics).get("stay_probability"))
        for symbol, metrics in per_symbol.items()
        if symbol != BTC_SYMBOL
    )
    return {
        "per_symbol": per_symbol,
        "btc_stay_probability": btc_score,
        "alt_mean_stay_probability": _mean(alt_scores),
        "btc_vs_alt_forecastability_delta": btc_score - _mean(alt_scores),
        "cross_symbol_stay_probability_stddev": _stddev(
            tuple(
                _float_value(_mapping(metrics).get("stay_probability"))
                for metrics in per_symbol.values()
            )
        ),
    }


def _model_consistency(
    *,
    labels: Sequence[dict[str, object]],
    state_space: Sequence[str],
    transition_model: Mapping[str, object],
    stability_model: Mapping[str, object],
    symbol_scores: Mapping[str, object],
) -> dict[str, object]:
    stability_baseline = _mapping(
        stability_model.get("baseline_random_model_comparison")
    )
    stability_global = _mapping(stability_baseline.get("global"))
    cross_symbol = _mapping(symbol_scores.get("per_symbol"))
    transition_stability = _mapping(transition_model.get("stability_of_transitions"))
    transition_per_symbol = _mapping(transition_stability.get("per_symbol"))
    total_transition_count = 0.0
    total_same_state_count = 0.0
    mismatches = {}
    for symbol, metrics in cross_symbol.items():
        transition_metrics = _mapping(_mapping(transition_per_symbol).get(symbol))
        observed = _float_value(_mapping(metrics).get("stay_probability"))
        transition_count = _float_value(_mapping(metrics).get("transition_count"))
        total_transition_count += transition_count
        total_same_state_count += observed * transition_count
        expected = _float_value(transition_metrics.get("diagonal_dominance"))
        if abs(observed - expected) > 1e-12:
            mismatches[str(symbol)] = {
                "observed": observed,
                "transition_model": expected,
            }
    observed_global_stay = (
        total_same_state_count / total_transition_count
        if total_transition_count
        else 0.0
    )
    expected_global_stay = _float_value(
        stability_global.get("observed_same_state_probability")
    )
    return {
        "state_label_rows_match": len(labels)
        == int(_float_value(stability_model.get("state_label_rows"))),
        "unique_states_match_transition_model": len(state_space)
        == int(_float_value(transition_model.get("unique_states"))),
        "global_same_state_probability": observed_global_stay,
        "stability_model_same_state_probability": expected_global_stay,
        "same_state_probability_matches_stability_model": abs(
            observed_global_stay - expected_global_stay
        )
        <= 1e-12,
        "per_symbol_stay_matches_transition_model": not mismatches,
        "per_symbol_mismatch_count": len(mismatches),
        "per_symbol_mismatches": mismatches,
    }


def _step_hazard(durations: Sequence[float], step: int) -> float:
    at_risk = sum(1 for duration in durations if duration >= step)
    if at_risk == 0:
        return 0.0
    exits_at_step = sum(1 for duration in durations if duration == step)
    return exits_at_step / at_risk


def _cumulative_exit_probability(durations: Sequence[float], step: int) -> float:
    if not durations:
        return 0.0
    return sum(1 for duration in durations if duration <= step) / len(durations)


def _decay_shape(durations: Sequence[float]) -> str:
    cumulative = {
        window: _cumulative_exit_probability(durations, window)
        for window in HAZARD_WINDOWS
    }
    early_gain = cumulative[3] - cumulative[1]
    late_gain = cumulative[10] - cumulative[5]
    if early_gain > late_gain * 1.5:
        return "front_loaded"
    if late_gain > early_gain * 1.5:
        return "back_loaded"
    return "mixed"


def _hazard_non_uniform(cumulative: Mapping[str, float]) -> bool:
    values = tuple(cumulative.get(str(window), 0.0) for window in HAZARD_WINDOWS)
    if len(set(values)) <= 1:
        return False
    increments = tuple(
        next_value - current_value
        for current_value, next_value in zip(values, values[1:], strict=False)
    )
    return max(increments, default=0.0) - min(increments, default=0.0) > 0.05


def _risk_class(stay_probability: float) -> str:
    if stay_probability >= 0.7:
        return "HIGHLY_PREDICTABLE"
    if stay_probability >= 0.5:
        return "MODERATELY_PREDICTABLE"
    return "VOLATILE"


def _float_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _float_value(item) for key, item in value.items()}


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _load_json_object(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Regime forecastability requires JSON object artifacts")
    return payload


def _stddev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


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


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
