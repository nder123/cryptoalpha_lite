import ast
from pathlib import Path

CORE_DIR = Path(__file__).parent
CORE_SOURCE_FILES = tuple(
    path
    for path in CORE_DIR.glob("*.py")
    if path.name not in {"__init__.py"} and not path.name.startswith("test_")
)

INTERPRETATION_FUNCTION_TERMS = (
    "analyze",
    "classify",
    "interpret",
    "score",
    "rank",
    "summarize",
    "trade",
)

BUSINESS_OUTPUT_TERMS = (
    "buy should",
    "sell should",
    "execute should",
    "policy should",
    "strategy should",
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_core_has_no_interpretation_or_scoring_functions():
    for path in CORE_SOURCE_FILES:
        tree = _tree(path)
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }

        for function_name in function_names:
            assert all(
                term not in function_name for term in INTERPRETATION_FUNCTION_TERMS
            )


def test_core_does_not_generate_positive_business_outputs():
    for path in CORE_SOURCE_FILES:
        source = path.read_text(encoding="utf-8").lower()

        assert all(term not in source for term in BUSINESS_OUTPUT_TERMS)


def test_semantic_terms_are_only_negative_invariants_or_attack_fixtures():
    invariant_source = (CORE_DIR / "invariants.py").read_text(encoding="utf-8")
    attacks_source = (CORE_DIR / "attacks.py").read_text(encoding="utf-8")

    assert "assert_no_" in invariant_source
    assert "decision_leakage_attack" in attacks_source
    assert "execution_bypass_attack" in attacks_source
    assert "boundary_reconstruction_attack" in attacks_source
