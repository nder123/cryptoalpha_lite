import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent
CORE_MODULES = {
    "__init__.py",
    "assertion_engine.py",
    "attacks.py",
    "fixtures.py",
    "invariants.py",
}
ALLOWED_PUBLIC_FUNCTIONS = {
    "assert_execution_rejects_unadmitted_input",
    "assert_explicit_admission_required",
    "assert_forbidden_terms_present",
    "assert_frequency_invariant",
    "assert_no_decision",
    "assert_no_execution_intent",
    "assert_no_forbidden_semantics",
    "assert_no_narrative",
    "assert_no_policy_inference",
    "assert_no_state_reconstruction",
    "assert_observation_only_output",
    "assert_order_invariant",
    "boundary_reconstruction_attack",
    "composition_attack",
    "decision_leakage_attack",
    "execution_bypass_attack",
    "forbidden_terms_in",
    "frequency_attack",
    "narrative_emergence_attack",
    "ordering_attack",
    "paraphrase_attack",
    "run",
    "run_signal_attack_suite",
    "semantic_signature",
}


def test_core_module_surface_is_minimal_and_explicit():
    source_modules = {
        path.name for path in CORE_DIR.glob("*.py") if not path.name.startswith("test_")
    }

    assert source_modules == CORE_MODULES


def test_core_public_function_surface_is_guarded():
    public_functions = set()
    for module_name in CORE_MODULES - {"__init__.py"}:
        tree = ast.parse((CORE_DIR / module_name).read_text(encoding="utf-8"))
        public_functions.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        )

    assert public_functions == ALLOWED_PUBLIC_FUNCTIONS


def test_core_does_not_grow_framework_constructs():
    for module_name in CORE_MODULES - {"__init__.py"}:
        tree = ast.parse((CORE_DIR / module_name).read_text(encoding="utf-8"))

        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
        assert not any(isinstance(node, ast.Try) for node in ast.walk(tree))
        assert not any(isinstance(node, ast.With) for node in ast.walk(tree))
