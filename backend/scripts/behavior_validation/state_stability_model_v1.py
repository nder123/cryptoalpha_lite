from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.behavior_validation.data_adapter import (
    load_historical_data,
    normalize_dataset,
)
from scripts.behavior_validation.state_transition_model_v1 import (
    load_state_labels,
    state_sequences_by_symbol,
)

SUMMARY_FILENAME = "state_stability_model_v1.json"
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
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "expanded_dataset_v1"
)
BTC_SYMBOL = "BTCUSDT"
EXIT_WINDOWS = (1, 3, 5, 10)
EPSILON = 1e-9


def run_state_stability_model(
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    *,
    transition_model_path: Path | str = DEFAULT_TRANSITION_MODEL_PATH,
    dataset_path: Path | str = DEFAULT_DATASET_PATH,
    output_dir: Path | None = None,
) -> dict[str, object]:
    labels = load_state_labels(state_labels_path)
    transition_model = _load_transition_model(transition_model_path)
    dataset_rows = len(normalize_dataset(load_historical_data(dataset_path)))
    report = build_state_stability_model(
        labels=labels,
        transition_model=transition_model,
        dataset_rows=dataset_rows,
    )
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def build_state_stability_model(
    *,
    labels: Sequence[dict[str, object]],
    transition_model: Mapping[str, object],
    dataset_rows: int,
) -> dict[str, object]:
    sequences = state_sequences_by_symbol(labels)
    runs_by_symbol = state_runs_by_symbol(sequences)
    all_runs = tuple(run for runs in runs_by_symbol.values() for run in runs)
    state_metrics = _per_state_stability_metrics(
        all_runs,
        _global_transition_matrix(transition_model),
    )
    return {
        "dataset_rows": dataset_rows,
        "state_label_rows": len(labels),
        "symbols": len(sequences),
        "unique_states": len(
            {state for sequence in sequences.values() for state in sequence}
        ),
        "mean_state_duration_per_symbol": _mean_duration_per_symbol(runs_by_symbol),
        "per_state_duration_stats": _per_state_duration_stats(all_runs),
        "exit_probability_distributions": _exit_probability_distributions(
            all_runs,
            _global_transition_matrix(transition_model),
        ),
        "half_life_estimates": {
            "per_state": {
                state: values["half_life_steps"]
                for state, values in state_metrics.items()
            },
            "histogram_per_state_class": _half_life_histogram_per_state_class(
                state_metrics
            ),
        },
        "stability_ranking_of_states": _stability_ranking(state_metrics),
        "cross_symbol_stability_divergence": _cross_symbol_stability_divergence(
            runs_by_symbol
        ),
        "stability_entropy_metrics": {
            "per_state": {
                state: {
                    "exit_entropy": values["exit_entropy"],
                    "stability_score": values["stability_score"],
                }
                for state, values in state_metrics.items()
            },
            "global_exit_entropy": _global_exit_entropy(all_runs),
            "mean_state_stability_score": _mean(
                tuple(values["stability_score"] for values in state_metrics.values())
            ),
        },
        "baseline_random_model_comparison": _baseline_random_model_comparison(
            runs_by_symbol=runs_by_symbol,
            transition_model=transition_model,
        ),
        "transition_model_consistency": _transition_model_consistency(
            sequences,
            transition_model,
        ),
        "source_constraints": {
            "input_layers": (
                "market_state_labeling_v1",
                "state_transition_model_v1",
                "expanded_dataset_v1",
            ),
            "external_sources_used": False,
            "new_features_created": False,
            "price_prediction_model_used": False,
            "optimization_used": False,
            "trading_logic_used": False,
            "reinforcement_learning_used": False,
        },
    }


def state_runs_by_symbol(
    sequences: Mapping[str, Sequence[str]],
) -> dict[str, tuple[dict[str, object], ...]]:
    runs_by_symbol: dict[str, tuple[dict[str, object], ...]] = {}
    for symbol, sequence in sorted(sequences.items()):
        symbol_runs: list[dict[str, object]] = []
        if not sequence:
            runs_by_symbol[symbol] = ()
            continue
        current_state = sequence[0]
        start_index = 0
        for index, state in enumerate(sequence[1:], start=1):
            if state != current_state:
                symbol_runs.append(
                    {
                        "symbol": symbol,
                        "state": current_state,
                        "start_index": start_index,
                        "duration": index - start_index,
                        "next_state": state,
                    }
                )
                current_state = state
                start_index = index
        symbol_runs.append(
            {
                "symbol": symbol,
                "state": current_state,
                "start_index": start_index,
                "duration": len(sequence) - start_index,
                "next_state": None,
            }
        )
        runs_by_symbol[symbol] = tuple(symbol_runs)
    return runs_by_symbol


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run state stability model v1")
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
    report = run_state_stability_model(
        args.state_labels,
        transition_model_path=args.transition_model,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _per_state_stability_metrics(
    runs: Sequence[dict[str, object]],
    transition_matrix: Mapping[str, float],
) -> dict[str, dict[str, float]]:
    states = sorted({str(run["state"]) for run in runs})
    metrics = {}
    for state in states:
        state_runs = tuple(run for run in runs if str(run["state"]) == state)
        next_state_distribution = _next_state_distribution(state_runs)
        exit_entropy = _entropy_from_probabilities(
            tuple(next_state_distribution.values())
        )
        stay_probability = _stay_probability(state, transition_matrix)
        metrics[state] = {
            "mean_duration": _mean(
                tuple(_float_value(run["duration"]) for run in state_runs)
            ),
            "max_duration": max(
                tuple(_float_value(run["duration"]) for run in state_runs),
                default=0.0,
            ),
            "stay_probability_next_step": stay_probability,
            "exit_probability_next_step": 1.0 - stay_probability,
            "half_life_steps": _half_life(stay_probability),
            "exit_entropy": exit_entropy,
            "stability_score": 1.0 / max(exit_entropy, EPSILON),
        }
    return metrics


def _mean_duration_per_symbol(
    runs_by_symbol: Mapping[str, Sequence[dict[str, object]]],
) -> dict[str, dict[str, float | int]]:
    return {
        symbol: {
            "run_count": len(runs),
            "mean_duration": _mean(
                tuple(_float_value(run["duration"]) for run in runs)
            ),
            "median_duration": _median(
                tuple(_float_value(run["duration"]) for run in runs)
            ),
            "max_duration": max(
                tuple(_float_value(run["duration"]) for run in runs),
                default=0.0,
            ),
        }
        for symbol, runs in sorted(runs_by_symbol.items())
    }


def _per_state_duration_stats(
    runs: Sequence[dict[str, object]],
) -> dict[str, dict[str, float | int]]:
    stats = {}
    for state in sorted({str(run["state"]) for run in runs}):
        durations = tuple(
            _float_value(run["duration"]) for run in runs if str(run["state"]) == state
        )
        stats[state] = {
            "run_count": len(durations),
            "mean_duration": _mean(durations),
            "median_duration": _median(durations),
            "max_duration": max(durations, default=0.0),
            "min_duration": min(durations, default=0.0),
        }
    return stats


def _exit_probability_distributions(
    runs: Sequence[dict[str, object]],
    transition_matrix: Mapping[str, float],
) -> dict[str, dict[str, object]]:
    distributions = {}
    for state in sorted({str(run["state"]) for run in runs}):
        state_runs = tuple(run for run in runs if str(run["state"]) == state)
        nonterminal_runs = tuple(
            run for run in state_runs if run.get("next_state") is not None
        )
        next_distribution = _next_state_distribution(state_runs)
        distributions[state] = {
            "observed_runs": len(state_runs),
            "observed_exits": len(nonterminal_runs),
            "exit_within_k_steps": {
                str(window): _exit_within_k_probability(nonterminal_runs, window)
                for window in EXIT_WINDOWS
            },
            "next_state_distribution": next_distribution,
            "stay_probability_next_step": _stay_probability(state, transition_matrix),
            "exit_probability_next_step": 1.0
            - _stay_probability(state, transition_matrix),
        }
    return distributions


def _half_life_histogram_per_state_class(
    state_metrics: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, dict[str, int]]]:
    histograms: dict[str, dict[str, Counter[str]]] = {
        "volatility": defaultdict(Counter),
        "trend": defaultdict(Counter),
        "stress": defaultdict(Counter),
    }
    for state, metrics in state_metrics.items():
        volatility, trend, stress = _state_parts(state)
        bucket = _half_life_bucket(metrics["half_life_steps"])
        histograms["volatility"][volatility][bucket] += 1
        histograms["trend"][trend][bucket] += 1
        histograms["stress"][stress][bucket] += 1
    return {
        dimension: {
            state_class: dict(sorted(counter.items()))
            for state_class, counter in sorted(classes.items())
        }
        for dimension, classes in histograms.items()
    }


def _stability_ranking(
    state_metrics: Mapping[str, Mapping[str, float]],
) -> dict[str, tuple[dict[str, float | str], ...]]:
    persistent = sorted(
        state_metrics.items(),
        key=lambda item: (
            item[1]["mean_duration"],
            item[1]["stay_probability_next_step"],
        ),
        reverse=True,
    )
    transient = sorted(
        state_metrics.items(),
        key=lambda item: (
            item[1]["mean_duration"],
            item[1]["stay_probability_next_step"],
        ),
    )
    volatile = sorted(
        state_metrics.items(),
        key=lambda item: item[1]["exit_entropy"],
        reverse=True,
    )
    return {
        "most_persistent": _ranked_states(tuple(persistent[:5])),
        "most_transient": _ranked_states(tuple(transient[:5])),
        "most_volatile_exit_distribution": _ranked_states(tuple(volatile[:5])),
    }


def _cross_symbol_stability_divergence(
    runs_by_symbol: Mapping[str, Sequence[dict[str, object]]],
) -> dict[str, object]:
    mean_duration_by_symbol = {
        symbol: _mean(tuple(_float_value(run["duration"]) for run in runs))
        for symbol, runs in sorted(runs_by_symbol.items())
    }
    btc_mean = mean_duration_by_symbol.get(BTC_SYMBOL, 0.0)
    alt_means = tuple(
        value
        for symbol, value in mean_duration_by_symbol.items()
        if symbol != BTC_SYMBOL
    )
    pairwise_differences = {
        symbol: btc_mean - value
        for symbol, value in sorted(mean_duration_by_symbol.items())
        if symbol != BTC_SYMBOL
    }
    return {
        "mean_duration_by_symbol": mean_duration_by_symbol,
        "btc_mean_duration": btc_mean,
        "alt_mean_duration": _mean(alt_means),
        "btc_duration_advantage": btc_mean - _mean(alt_means),
        "btc_vs_alt_duration_differences": pairwise_differences,
        "cross_symbol_duration_stddev": _stddev(
            tuple(mean_duration_by_symbol.values())
        ),
    }


def _baseline_random_model_comparison(
    *,
    runs_by_symbol: Mapping[str, Sequence[dict[str, object]]],
    transition_model: Mapping[str, object],
) -> dict[str, object]:
    state_space_size = int(_float_value(transition_model.get("unique_states")))
    random_stay_probability = 1.0 / state_space_size if state_space_size else 0.0
    transition_stability = transition_model.get("stability_of_transitions")
    if not isinstance(transition_stability, dict):
        transition_stability = {}
    per_symbol_transition = transition_stability.get("per_symbol")
    if not isinstance(per_symbol_transition, dict):
        per_symbol_transition = {}
    global_transition = transition_stability.get("global")
    if not isinstance(global_transition, dict):
        global_transition = {}
    observed_global_stay = _float_value(global_transition.get("diagonal_dominance"))
    return {
        "random_model": {
            "state_space_size": state_space_size,
            "same_state_probability": random_stay_probability,
        },
        "global": {
            "observed_same_state_probability": observed_global_stay,
            "stability_edge_vs_random": observed_global_stay - random_stay_probability,
            "stability_above_random": observed_global_stay > random_stay_probability,
        },
        "per_symbol": {
            symbol: {
                "observed_same_state_probability": _float_value(
                    _mapping(per_symbol_transition.get(symbol)).get(
                        "diagonal_dominance"
                    )
                ),
                "stability_edge_vs_random": _float_value(
                    _mapping(per_symbol_transition.get(symbol)).get(
                        "diagonal_dominance"
                    )
                )
                - random_stay_probability,
                "mean_duration": _mean(
                    tuple(_float_value(run["duration"]) for run in runs)
                ),
            }
            for symbol, runs in sorted(runs_by_symbol.items())
        },
    }


def _transition_model_consistency(
    sequences: Mapping[str, Sequence[str]],
    transition_model: Mapping[str, object],
) -> dict[str, object]:
    observed_counts = _transition_counts_by_symbol(sequences)
    model_counts = _transition_counts_from_model(transition_model)
    mismatches = {}
    for symbol, observed in observed_counts.items():
        model_symbol_counts = model_counts.get(symbol, {})
        if dict(observed) != model_symbol_counts:
            mismatches[symbol] = {
                "observed": dict(sorted(observed.items())),
                "model": dict(sorted(model_symbol_counts.items())),
            }
    return {
        "matches_state_transition_model_v1": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _transition_counts_by_symbol(
    sequences: Mapping[str, Sequence[str]],
) -> dict[str, Counter[str]]:
    return {
        symbol: Counter(
            f"{current} -> {next_state}"
            for current, next_state in zip(sequence, sequence[1:], strict=False)
        )
        for symbol, sequence in sequences.items()
    }


def _transition_counts_from_model(
    transition_model: Mapping[str, object],
) -> dict[str, dict[str, int]]:
    raw_counts = transition_model.get("transition_counts_per_symbol")
    if not isinstance(raw_counts, dict):
        return {}
    return {
        str(symbol): {
            str(transition): int(_float_value(count))
            for transition, count in _mapping(counts).items()
        }
        for symbol, counts in raw_counts.items()
    }


def _next_state_distribution(
    runs: Sequence[dict[str, object]],
) -> dict[str, float]:
    next_counts: Counter[str] = Counter(
        str(run["next_state"]) for run in runs if run.get("next_state") is not None
    )
    total = sum(next_counts.values())
    if total == 0:
        return {}
    return {state: count / total for state, count in sorted(next_counts.items())}


def _exit_within_k_probability(
    runs: Sequence[dict[str, object]],
    steps: int,
) -> float:
    if not runs:
        return 0.0
    return sum(1 for run in runs if _float_value(run["duration"]) <= steps) / len(runs)


def _global_transition_matrix(
    transition_model: Mapping[str, object],
) -> dict[str, float]:
    matrix = transition_model.get("global_transition_matrix")
    if not isinstance(matrix, dict):
        return {}
    return {
        str(transition): _float_value(probability)
        for transition, probability in matrix.items()
    }


def _stay_probability(
    state: str,
    transition_matrix: Mapping[str, float],
) -> float:
    return transition_matrix.get(f"{state} -> {state}", 0.0)


def _half_life(stay_probability: float) -> float:
    if stay_probability <= 0.0:
        return 0.0
    if stay_probability >= 1.0:
        return 1.0 / EPSILON
    return math.log(0.5) / math.log(stay_probability)


def _half_life_bucket(value: float) -> str:
    if value >= 1.0 / EPSILON:
        return "unbounded"
    if value < 1.0:
        return "0_to_1"
    if value < 3.0:
        return "1_to_3"
    if value < 5.0:
        return "3_to_5"
    if value < 10.0:
        return "5_to_10"
    return "10_plus"


def _global_exit_entropy(runs: Sequence[dict[str, object]]) -> float:
    next_counts: Counter[str] = Counter(
        str(run["next_state"]) for run in runs if run.get("next_state") is not None
    )
    total = sum(next_counts.values())
    if total == 0:
        return 0.0
    return _entropy_from_probabilities(
        tuple(count / total for count in next_counts.values())
    )


def _ranked_states(
    ranked: Sequence[tuple[str, Mapping[str, float]]],
) -> tuple[dict[str, float | str], ...]:
    return tuple(
        {
            "state": state,
            "mean_duration": metrics["mean_duration"],
            "stay_probability_next_step": metrics["stay_probability_next_step"],
            "half_life_steps": metrics["half_life_steps"],
            "exit_entropy": metrics["exit_entropy"],
            "stability_score": metrics["stability_score"],
        }
        for state, metrics in ranked
    )


def _state_parts(state: str) -> tuple[str, str, str]:
    parts = state.split("_", maxsplit=2)
    if len(parts) != 3:
        return "LOW", "FLAT", "STABLE"
    return parts[0], parts[1], parts[2]


def _entropy_from_probabilities(probabilities: Sequence[float]) -> float:
    return -sum(
        probability * math.log2(probability)
        for probability in probabilities
        if probability > 0.0
    )


def _load_transition_model(path: Path | str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("State stability model requires a transition model object")
    return payload


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = tuple(sorted(values))
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


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
