from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

SUMMARY_FILENAME = "state_transition_model_v1.json"
DEFAULT_STATE_LABEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "artifacts"
    / "behavior_validation"
    / "market_state_labeling_v1.json"
)
STATE_KEYS = ("volatility", "trend", "stress")


def run_state_transition_model(
    state_labels_path: Path | str = DEFAULT_STATE_LABEL_PATH,
    *,
    output_dir: Path | None = None,
) -> dict[str, object]:
    labels = load_state_labels(state_labels_path)
    report = build_state_transition_model(labels)
    target_output_dir = output_dir or _default_output_dir()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    (target_output_dir / SUMMARY_FILENAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def load_state_labels(path: Path | str) -> tuple[dict[str, object], ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = payload.get("state_labels") if isinstance(payload, dict) else payload
    if not isinstance(labels, list):
        raise ValueError("State transition model requires a state_labels list")
    return tuple(label for label in labels if isinstance(label, dict))


def build_state_transition_model(
    labels: Sequence[dict[str, object]],
) -> dict[str, object]:
    sequences = state_sequences_by_symbol(labels)
    symbol_transition_counts = {
        symbol: _transition_counts(sequence) for symbol, sequence in sequences.items()
    }
    global_transition_counts = _sum_transition_counts(
        tuple(symbol_transition_counts.values())
    )
    symbol_matrices = {
        symbol: _transition_matrix(counts)
        for symbol, counts in symbol_transition_counts.items()
    }
    global_matrix = _transition_matrix(global_transition_counts)
    unique_states = tuple(
        sorted({state for sequence in sequences.values() for state in sequence})
    )
    return {
        "input_rows": len(labels),
        "symbols": len(sequences),
        "unique_states": len(unique_states),
        "state_space": unique_states,
        "transition_matrices_per_symbol": symbol_matrices,
        "global_transition_matrix": global_matrix,
        "transition_counts_per_symbol": {
            symbol: dict(sorted(counts.items()))
            for symbol, counts in symbol_transition_counts.items()
        },
        "global_transition_counts": dict(sorted(global_transition_counts.items())),
        "entropy_metrics": _entropy_metrics(
            symbol_transition_counts=symbol_transition_counts,
            global_transition_counts=global_transition_counts,
            state_space_size=len(unique_states),
        ),
        "stability_of_transitions": _transition_stability(
            symbol_transition_counts=symbol_transition_counts,
            global_transition_counts=global_transition_counts,
        ),
        "baseline_comparison": _baseline_comparison(
            symbol_transition_counts=symbol_transition_counts,
            global_transition_counts=global_transition_counts,
            state_space_size=len(unique_states),
        ),
        "cross_symbol_similarity_matrix": _cross_symbol_similarity_matrix(
            symbol_matrices
        ),
        "btc_vs_alts_structural_divergence": _btc_vs_alt_divergence(symbol_matrices),
        "source_constraints": {
            "input_layer": "market_state_labeling_v1",
            "external_sources_used": False,
            "new_features_created": False,
            "learning_model_used": False,
            "forecasting_model_used": False,
            "optimization_used": False,
        },
    }


def state_sequences_by_symbol(
    labels: Sequence[dict[str, object]],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for label in labels:
        grouped[str(label["symbol"])].append(label)
    return {
        symbol: tuple(_state_key(label) for label in sorted_labels)
        for symbol, sorted_labels in (
            (
                symbol,
                sorted(symbol_labels, key=lambda label: str(label["timestamp"])),
            )
            for symbol, symbol_labels in sorted(grouped.items())
        )
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run state transition model v1")
    parser.add_argument(
        "state_labels",
        nargs="?",
        type=Path,
        default=DEFAULT_STATE_LABEL_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    report = run_state_transition_model(args.state_labels, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))


def _transition_counts(sequence: Sequence[str]) -> Counter[str]:
    return Counter(
        f"{current} -> {next_state}"
        for current, next_state in zip(sequence, sequence[1:], strict=False)
    )


def _transition_matrix(counts: Mapping[str, int]) -> dict[str, float]:
    totals_by_origin: Counter[str] = Counter()
    for transition, count in counts.items():
        origin, _ = _split_transition(transition)
        totals_by_origin[origin] += count
    return {
        transition: count / totals_by_origin[_split_transition(transition)[0]]
        for transition, count in sorted(counts.items())
        if totals_by_origin[_split_transition(transition)[0]] > 0
    }


def _entropy_metrics(
    *,
    symbol_transition_counts: Mapping[str, Counter[str]],
    global_transition_counts: Counter[str],
    state_space_size: int,
) -> dict[str, object]:
    uniform_entropy = _uniform_entropy(state_space_size)
    per_symbol = {
        symbol: _entropy_summary(counts, uniform_entropy)
        for symbol, counts in symbol_transition_counts.items()
    }
    return {
        "per_symbol": per_symbol,
        "global": _entropy_summary(global_transition_counts, uniform_entropy),
    }


def _entropy_summary(
    counts: Mapping[str, int],
    uniform_entropy: float,
) -> dict[str, float | bool]:
    transition_entropy = _entropy_from_counts(counts)
    conditional_entropy = _conditional_entropy(counts)
    return {
        "transition_entropy": transition_entropy,
        "conditional_entropy": conditional_entropy,
        "uniform_baseline_entropy": uniform_entropy,
        "entropy_below_uniform": conditional_entropy < uniform_entropy,
        "entropy_reduction_vs_uniform": uniform_entropy - conditional_entropy,
    }


def _transition_stability(
    *,
    symbol_transition_counts: Mapping[str, Counter[str]],
    global_transition_counts: Counter[str],
) -> dict[str, object]:
    per_symbol = {
        symbol: _stability_summary(counts)
        for symbol, counts in symbol_transition_counts.items()
    }
    return {
        "per_symbol": per_symbol,
        "global": _stability_summary(global_transition_counts),
    }


def _stability_summary(counts: Mapping[str, int]) -> dict[str, float | int | bool]:
    total = sum(counts.values())
    if total == 0:
        return {
            "transition_count": 0,
            "probability_mass_top_1": 0.0,
            "probability_mass_top_5": 0.0,
            "diagonal_dominance": 0.0,
            "diagonal_dominance_observed": False,
        }
    ordered_counts = tuple(sorted(counts.values(), reverse=True))
    diagonal_count = sum(
        count
        for transition, count in counts.items()
        if _split_transition(transition)[0] == _split_transition(transition)[1]
    )
    return {
        "transition_count": total,
        "probability_mass_top_1": ordered_counts[0] / total,
        "probability_mass_top_5": sum(ordered_counts[:5]) / total,
        "diagonal_dominance": diagonal_count / total,
        "diagonal_dominance_observed": diagonal_count > 0,
    }


def _baseline_comparison(
    *,
    symbol_transition_counts: Mapping[str, Counter[str]],
    global_transition_counts: Counter[str],
    state_space_size: int,
) -> dict[str, object]:
    uniform_entropy = _uniform_entropy(state_space_size)
    per_symbol = {
        symbol: _baseline_summary(counts, uniform_entropy)
        for symbol, counts in symbol_transition_counts.items()
    }
    return {
        "uniform_random_model": {
            "state_space_size": state_space_size,
            "next_state_probability": (
                1.0 / state_space_size if state_space_size else 0.0
            ),
            "conditional_entropy": uniform_entropy,
        },
        "per_symbol": per_symbol,
        "global": _baseline_summary(global_transition_counts, uniform_entropy),
    }


def _baseline_summary(
    counts: Mapping[str, int],
    uniform_entropy: float,
) -> dict[str, float | bool]:
    conditional_entropy = _conditional_entropy(counts)
    return {
        "observed_conditional_entropy": conditional_entropy,
        "uniform_conditional_entropy": uniform_entropy,
        "predictability_proxy": uniform_entropy - conditional_entropy,
        "observed_more_predictable_than_uniform": conditional_entropy < uniform_entropy,
        "mean_max_next_state_probability": _mean_max_next_state_probability(counts),
    }


def _cross_symbol_similarity_matrix(
    symbol_matrices: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    symbols = tuple(sorted(symbol_matrices))
    return {
        first: {
            second: _cosine_similarity(symbol_matrices[first], symbol_matrices[second])
            for second in symbols
        }
        for first in symbols
    }


def _btc_vs_alt_divergence(
    symbol_matrices: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    btc_matrix = symbol_matrices.get("BTCUSDT", {})
    divergences = {
        symbol: 1.0 - _cosine_similarity(btc_matrix, matrix)
        for symbol, matrix in sorted(symbol_matrices.items())
        if symbol != "BTCUSDT"
    }
    return {
        "per_alt_symbol": divergences,
        "mean_divergence": _mean(tuple(divergences.values())),
    }


def _sum_transition_counts(
    counters: Sequence[Counter[str]],
) -> Counter[str]:
    total: Counter[str] = Counter()
    for counter in counters:
        total.update(counter)
    return total


def _conditional_entropy(counts: Mapping[str, int]) -> float:
    counts_by_origin: dict[str, Counter[str]] = defaultdict(Counter)
    for transition, count in counts.items():
        origin, destination = _split_transition(transition)
        counts_by_origin[origin][destination] += count
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return sum(
        (sum(destination_counts.values()) / total)
        * _entropy_from_counts(destination_counts)
        for destination_counts in counts_by_origin.values()
    )


def _mean_max_next_state_probability(counts: Mapping[str, int]) -> float:
    counts_by_origin: dict[str, Counter[str]] = defaultdict(Counter)
    for transition, count in counts.items():
        origin, destination = _split_transition(transition)
        counts_by_origin[origin][destination] += count
    max_probabilities = tuple(
        max(destination_counts.values()) / sum(destination_counts.values())
        for destination_counts in counts_by_origin.values()
        if sum(destination_counts.values()) > 0
    )
    return _mean(max_probabilities)


def _entropy_from_counts(counts: Mapping[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts.values()
        if count > 0
    )


def _uniform_entropy(state_space_size: int) -> float:
    if state_space_size <= 1:
        return 0.0
    return math.log2(state_space_size)


def _cosine_similarity(
    first: Mapping[str, float],
    second: Mapping[str, float],
) -> float:
    keys = set(first) | set(second)
    if not keys:
        return 0.0
    numerator = sum(first.get(key, 0.0) * second.get(key, 0.0) for key in keys)
    first_norm = sum(first.get(key, 0.0) ** 2 for key in keys) ** 0.5
    second_norm = sum(second.get(key, 0.0) ** 2 for key in keys) ** 0.5
    if first_norm == 0.0 or second_norm == 0.0:
        return 0.0
    return numerator / (first_norm * second_norm)


def _state_key(label: Mapping[str, object]) -> str:
    state = label["state"]
    if not isinstance(state, dict):
        return "LOW_FLAT_STABLE"
    return "_".join(str(state[key]) for key in STATE_KEYS)


def _split_transition(transition: str) -> tuple[str, str]:
    origin, destination = transition.split(" -> ", maxsplit=1)
    return origin, destination


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "artifacts" / "behavior_validation"


if __name__ == "__main__":
    main()
