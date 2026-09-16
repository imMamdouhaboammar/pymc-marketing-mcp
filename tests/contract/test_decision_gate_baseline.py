"""Tests verifying diagnostic gate characterization and decision policy invariants (UP-004)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketing_mcp.domain.diagnostics.gate import DecisionGate
from marketing_mcp.errors import DomainError

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


def test_decision_gate_fixtures_and_invariants():
    with open(BASELINES_DIR / "decision_gate_fixtures.json", encoding="utf-8") as f:
        data = json.load(f)

    fixtures = data["fixtures"]
    assert len(fixtures) >= 7

    for fix in fixtures:
        name = fix["name"]
        status = fix["expected_status"]
        enabled = fix["expected_decision_tools_enabled"]
        metrics = fix["metrics"]

        # 1. Invariant: Only 'approved' or 'approved_with_caution' enable decision tools
        if status in ("approved", "approved_with_caution"):
            assert enabled is True, f"Fixture {name} must have decision_tools_enabled=True"
            # DecisionGate must permit execution
            gate = DecisionGate(decision_status=status, failures=[])
            # Should not raise
            gate.require_decision_access()
        else:
            assert status == "rejected"
            assert enabled is False, f"Fixture {name} must have decision_tools_enabled=False"
            # DecisionGate must block execution with DomainError('MODEL_NOT_VALIDATED')
            failures = [{"metric": m, "observed": metrics.get(m)} for m in fix.get("expected_failure_metrics", [])]
            gate = DecisionGate(decision_status=status, failures=failures)
            with pytest.raises(DomainError) as exc_info:
                gate.require_decision_access()
            assert exc_info.value.code == "MODEL_NOT_VALIDATED"
            assert "Decision tools are disabled" in exc_info.value.message


def test_policy_threshold_invariants():
    with open(BASELINES_DIR / "decision_gate_fixtures.json", encoding="utf-8") as f:
        data = json.load(f)

    policy = data["policy"]
    assert policy["divergences_threshold"] == 0
    assert policy["rhat_strict_threshold"] == 1.01
    assert policy["rhat_max_threshold"] == 1.05
    assert policy["ess_bulk_warning_threshold"] == 400.0
    assert policy["ess_bulk_minimum_threshold"] == 50.0
    assert policy["coverage_94_warning_threshold"] == 0.80
    assert policy["coverage_94_minimum_threshold"] == 0.50
