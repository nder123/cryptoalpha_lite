"""Tests for the Stage 1 freeze guard.

These tests do TWO things:

1. Positive: against the actual repo state, `run_all_checks()` must pass
   (zero violations). This is the CI gate.

2. Negative: feeding a tampered manifest must surface the expected violation
   codes. This proves the guard is not just rubber-stamping.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from runtime.freeze_guard.checker import (
    CheckReport,
    Violation,
    check_frozen_documents_exist,
    check_structural_assertions,
    check_test_counts,
    load_manifest,
    run_all_checks,
    _count_test_cases,
)


# ── Positive: live freeze passes every check ─────────────────────────


def test_live_repo_freeze_passes():
    report = run_all_checks()
    codes = [v.code for v in report.violations]
    messages = [v.message for v in report.violations]
    assert report.passed, f"freeze violated: codes={codes} messages={messages}"


def test_live_manifest_loads_with_expected_top_keys():
    m = load_manifest()
    for key in (
        "schema", "freeze_version", "axioms", "invariants",
        "frozen_documents", "structural_assertions",
        "test_count_baseline", "frozen_endpoints", "re_entry",
    ):
        assert key in m, f"missing top-level key: {key}"
    assert m["schema"] == "stage1_freeze_manifest.v1"


# ── Negative: tampered manifests must surface violations ─────────────


def _tamper(transform) -> CheckReport:
    """Run all checks against a deep-copied manifest after tamper(transform)."""
    base = load_manifest()
    tampered = deepcopy(base)
    transform(tampered)
    report = CheckReport()
    check_frozen_documents_exist(tampered, report)
    check_structural_assertions(tampered, report)
    check_test_counts(tampered, report)
    return report


def test_tamper_with_state_set_yields_enum_violation():
    def t(m):
        m["structural_assertions"]["h_states_exact_7"]["expected"] = [
            "HEALTHY", "DEGRADED"
        ]  # too few
    rep = _tamper(t)
    assert any(v.code == "FG-ENUM-1" for v in rep.violations)


def test_tamper_with_forbidden_pair_yields_pair_violation():
    def t(m):
        # Require a pair that does NOT exist in production code.
        m["structural_assertions"]["forbidden_direct_transitions_superset"][
            "required_pairs"
        ].append(["HEALTHY", "HEALTHY"])  # would only be present if H→H were forbidden
    rep = _tamper(t)
    assert any(v.code == "FG-PAIR-1" for v in rep.violations)


def test_tamper_requiring_extra_autorestart_yields_set_violation():
    def t(m):
        m["structural_assertions"][
            "forbidden_autorestart_includes_backend_and_watchdog"
        ]["required_members"].append("cryptoalpha-snapshots.service")
    rep = _tamper(t)
    assert any(v.code == "FG-SET-1" for v in rep.violations)


def test_tamper_allowed_states_to_non_exact_yields_violation():
    def t(m):
        m["structural_assertions"]["trading_gate_allowed_states_exact"][
            "expected_members"
        ] = ["HEALTHY"]  # gate is more permissive than manifest claims
    rep = _tamper(t)
    assert any(v.code == "FG-SET-EX-1" for v in rep.violations)


def test_tamper_never_prune_required_id_yields_violation():
    def t(m):
        m["structural_assertions"]["retention_never_prune_includes_audit"][
            "required_members"
        ].append("nonexistent_never_prune_id")
    rep = _tamper(t)
    assert any(v.code == "FG-TUPDC-1" for v in rep.violations)


def test_tamper_schema_constant_yields_violation():
    def t(m):
        m["structural_assertions"]["evidence_schemas_unchanged"]["expected"][
            "TRANSITION_SCHEMA"
        ] = "runtime_health_transition.v2"
    rep = _tamper(t)
    assert any(v.code == "FG-CONST-1" for v in rep.violations)


def test_tamper_unknown_kind_yields_violation():
    def t(m):
        m["structural_assertions"]["bogus"] = {
            "module": "runtime.watchdog.states",
            "attribute": "H",
            "kind": "spaghetti",
        }
    rep = _tamper(t)
    assert any(v.code == "FG-KIND-UNKNOWN" for v in rep.violations)


def test_tamper_missing_doc_yields_violation():
    def t(m):
        m["frozen_documents"].append("docs/__never_exists__.md")
    rep = _tamper(t)
    assert any(v.code == "FG-DOC-MISSING" for v in rep.violations)


def test_tamper_test_count_inflation_yields_violation():
    def t(m):
        m["test_count_baseline"]["files"]["tests/test_watchdog_states.py"] = 999_999
    rep = _tamper(t)
    assert any(v.code == "FG-TESTS-1" for v in rep.violations)


def test_tamper_minimum_total_inflation_yields_violation():
    def t(m):
        m["test_count_baseline"]["minimum_total"] = 999_999
    rep = _tamper(t)
    assert any(v.code == "FG-TESTS-TOTAL" for v in rep.violations)


# ── Negative: new check kinds (boundary-stress additions) ────────────


def test_tamper_restart_budget_value_yields_violation():
    """If RESTART_BUDGETS['snapshots'].max_count is silently bumped from 3
    to e.g. 99, the gate must catch it."""
    def t(m):
        m["structural_assertions"]["restart_budgets_pinned"]["expected"][
            "cryptoalpha-snapshots.service"
        ] = 99   # require something the code does NOT set
    rep = _tamper(t)
    assert any(v.code == "FG-MAP-VAL-1" for v in rep.violations)


def test_tamper_unknown_budget_key_yields_missing_violation():
    def t(m):
        m["structural_assertions"]["restart_budgets_pinned"]["expected"][
            "cryptoalpha-bogus.service"
        ] = 3
    rep = _tamper(t)
    assert any(v.code == "FG-MAP-MISSING" for v in rep.violations)


def test_tamper_path_exists_required_phantom_path():
    def t(m):
        m["structural_assertions"]["systemd_units_present"]["paths"].append(
            "ops/systemd-user/cryptoalpha-phantom.service"
        )
    rep = _tamper(t)
    assert any(v.code == "FG-PATH-MISSING" for v in rep.violations)


def test_tamper_text_contains_phantom_substring():
    """If we add a substring that's NOT in bybit_adapter.py, gate must fail."""
    def t(m):
        m["structural_assertions"]["bybit_adapter_calls_gate"]["must_contain"].append(
            "this_substring_does_not_exist_anywhere_xyz123"
        )
    rep = _tamper(t)
    assert any(v.code == "FG-TEXT-MISSING" for v in rep.violations)


def test_tamper_text_contains_unreadable_file():
    def t(m):
        m["structural_assertions"]["bybit_adapter_calls_gate"]["path"] = (
            "backend/app/exchange/__nonexistent_file__.py"
        )
    rep = _tamper(t)
    assert any(v.code == "FG-FILE-LOAD" for v in rep.violations)


# ── Test counter sanity ──────────────────────────────────────────────


def test_test_counter_counts_def_test_lines(tmp_path: Path):
    p = tmp_path / "test_x.py"
    p.write_text(
        "def test_one():\n    pass\n\n"
        "def test_two():\n    pass\n\n"
        "def helper():\n    return 1\n\n"
        "async def test_async():\n    pass\n"
    )
    assert _count_test_cases(p) == 3


def test_test_counter_expands_parametrize(tmp_path: Path):
    p = tmp_path / "test_p.py"
    p.write_text(
        '@pytest.mark.parametrize("x", [1, 2, 3, 4])\n'
        "def test_pp(x):\n    pass\n"
    )
    assert _count_test_cases(p) == 4


def test_test_counter_missing_file_returns_zero(tmp_path: Path):
    assert _count_test_cases(tmp_path / "absent.py") == 0
