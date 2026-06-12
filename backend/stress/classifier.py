STABLE_CORE = "stable_core"
IDEMPOTENCY_BOUNDARY_LAYER = "idempotency_boundary_layer"
LEDGER_BRITTLE_REGION = "ledger_brittle_region"
PERMUTATION_SENSITIVE_ZONE = "permutation_sensitive_zone"
CLOSURE_STRESS_FRONTIER = "closure_stress_frontier"


def classify(*args, **kwargs):
    return {"metrics": {}, "regimes": [STABLE_CORE]}
