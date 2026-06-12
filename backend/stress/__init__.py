from dataclasses import dataclass

from .classifier import (
    IDEMPOTENCY_BOUNDARY_LAYER,
    LEDGER_BRITTLE_REGION,
    PERMUTATION_SENSITIVE_ZONE,
    STABLE_CORE,
)

STRESS_REGIMES = (
    STABLE_CORE,
    IDEMPOTENCY_BOUNDARY_LAYER,
    LEDGER_BRITTLE_REGION,
    PERMUTATION_SENSITIVE_ZONE,
)


@dataclass
class StressProfile:
    n: int = 0
    seed: int = 0
    symbols: tuple = ()
    known_symbols: tuple = ()
    duplicate_id_rate: float = 0.0
    close_before_open: float = 0.0
    oversize_close: float = 0.0
    fee_interleave_rate: float = 0.0
    price_update_rate: float = 0.0
    invalid_size_rate: float = 0.0
    invalid_symbol_rate: float = 0.0


def generate_sequence(*args, **kwargs):
    return []


def run_stress(*args, **kwargs):
    return {}


def classify(*args, **kwargs):
    return {"metrics": {}, "regimes": [STABLE_CORE]}


def stress_report(*args, **kwargs):
    return {"regimes": [STABLE_CORE], "metrics": {}, "execution": {}}
