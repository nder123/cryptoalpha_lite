from random import Random

from tests._adversarial_core.fixtures import (
    ADVERSARIAL_PARAPHRASES,
    CLEAN_SIGNALS,
    CONSUMER_AGGREGATION_TRAPS,
    DOWNSTREAM_CONSUMER_TRAPS,
    EXECUTION_TRAP_INPUTS,
    FORBIDDEN_API_RESPONSES,
    FORBIDDEN_DECISION_OUTPUTS,
    FORBIDDEN_NARRATIVE_OUTPUTS,
    FORBIDDEN_POLICY_OUTPUTS,
    LOGGING_INFERENCE_TRIGGERS,
    NARRATIVE_TRAP_INPUTS,
)


def paraphrase_attack() -> tuple[str, ...]:
    return ADVERSARIAL_PARAPHRASES


def composition_attack(signals: tuple[str, ...] = CLEAN_SIGNALS) -> tuple[str, ...]:
    return signals[:25]


def ordering_attack(
    signals: tuple[str, ...] = CLEAN_SIGNALS,
    seeds: range = range(10),
) -> tuple[tuple[str, ...], ...]:
    shuffled_sets = []
    for seed in seeds:
        shuffled = list(signals)
        Random(seed).shuffle(shuffled)
        shuffled_sets.append(tuple(shuffled))
    return tuple(shuffled_sets)


def frequency_attack(signal: str = CLEAN_SIGNALS[0]) -> tuple[tuple[str, ...], ...]:
    return ((signal,), (signal,) * 10)


def narrative_emergence_attack() -> tuple[tuple[str, ...], ...]:
    return NARRATIVE_TRAP_INPUTS


def decision_leakage_attack() -> tuple[str, ...]:
    return FORBIDDEN_DECISION_OUTPUTS + FORBIDDEN_POLICY_OUTPUTS


def execution_bypass_attack() -> tuple[str, ...]:
    return EXECUTION_TRAP_INPUTS


def boundary_reconstruction_attack() -> tuple[str, ...]:
    api_values = tuple(
        " ".join(str(value) for value in response.values())
        for response in FORBIDDEN_API_RESPONSES
    )
    return (
        CONSUMER_AGGREGATION_TRAPS
        + LOGGING_INFERENCE_TRIGGERS
        + DOWNSTREAM_CONSUMER_TRAPS
        + FORBIDDEN_NARRATIVE_OUTPUTS
        + api_values
    )
