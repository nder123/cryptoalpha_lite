"""Tests for cross-module consistency checks."""

from __future__ import annotations

from app.services.validation.cross_module_consistency import (
    check_event_bus_coverage,
    check_lineage_coverage,
    check_risk_coverage,
)

# ── A. risk_engine <-> trading_gate ──────────────────────────────────────


class TestRiskCoverage:
    def test_all_decisions_have_risk_results(self):
        decisions = ["h-1", "h-2", "h-3"]
        risk_results = {"h-1": {}, "h-2": {}, "h-3": {}}
        result = check_risk_coverage(decisions, risk_results)
        assert result.ok is True
        assert result.missing == []

    def test_missing_risk_result_fails(self):
        decisions = ["h-1", "h-2", "h-3"]
        risk_results = {"h-1": {}, "h-3": {}}
        result = check_risk_coverage(decisions, risk_results)
        assert result.ok is False
        assert "h-2" in result.missing


# ── B. execution_engine <-> event_bus ────────────────────────────────────


class TestEventBusCoverage:
    def test_all_executions_recorded(self):
        exec_ids = ["d-1", "d-2"]
        bus_records = {"d-1": {}, "d-2": {}}
        result = check_event_bus_coverage(exec_ids, bus_records)
        assert result.ok is True
        assert result.missing == []

    def test_missing_event_bus_record_fails(self):
        exec_ids = ["d-1", "d-2", "d-3"]
        bus_records = {"d-1": {}, "d-3": {}}
        result = check_event_bus_coverage(exec_ids, bus_records)
        assert result.ok is False
        assert "d-2" in result.missing


# ── C. trading_gate <-> event lineage ────────────────────────────────────


class TestLineageCoverage:
    def test_all_decisions_in_lineage(self):
        decisions = ["g-1", "g-2"]
        lineage = {"g-1": {}, "g-2": {}}
        result = check_lineage_coverage(decisions, lineage)
        assert result.ok is True
        assert result.missing == []

    def test_broken_lineage_fails(self):
        decisions = ["g-1", "g-2", "g-3"]
        lineage = {"g-1": {}}
        result = check_lineage_coverage(decisions, lineage)
        assert result.ok is False
        assert "g-2" in result.missing
        assert "g-3" in result.missing
