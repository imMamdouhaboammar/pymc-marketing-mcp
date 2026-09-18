"""Tests for UP-056: Extract pure Python diagnostics and decision policy gate."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from marketing_mcp.scientific.decision_gate import (
    evaluate_diagnostic_policy,
)


@pytest.fixture
def baseline_config() -> dict:
    baseline_path = (
        Path(__file__).resolve().parents[3]
        / "migration/baselines/diagnostic_gates.json"
    )
    with open(baseline_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_baseline_scenarios_match_policy(baseline_config):
    scenarios = baseline_config["scenarios"]
    assert len(scenarios) >= 6

    for scenario in scenarios:
        metrics = scenario["metrics"]
        name = scenario["name"]
        run_id = uuid4()

        report = evaluate_diagnostic_policy(
            run_id=run_id,
            max_rhat=metrics["max_rhat"],
            divergences=metrics["divergences"],
            min_bfmi=metrics["min_bfmi"],
            policy_version=baseline_config.get("policy_version", "1.0.0"),
        )

        assert report.decision_status == scenario["expected_verdict"], (
            f"Scenario {name} failed: expected {scenario['expected_verdict']}, "
            f"got {report.decision_status}. Reasons: {report.reasons}"
        )
        assert report.diagnostics.rhat_ok == scenario["expected_rhat_ok"], (
            f"Scenario {name} rhat_ok mismatch: expected {scenario['expected_rhat_ok']}, "
            f"got {report.diagnostics.rhat_ok}"
        )
        assert report.diagnostics.divergences_ok == scenario["expected_divergences_ok"], (
            f"Scenario {name} divergences_ok mismatch: expected {scenario['expected_divergences_ok']}, "
            f"got {report.diagnostics.divergences_ok}"
        )
        assert report.diagnostics.bfmi_ok == scenario["expected_bfmi_ok"], (
            f"Scenario {name} bfmi_ok mismatch: expected {scenario['expected_bfmi_ok']}, "
            f"got {report.diagnostics.bfmi_ok}"
        )


def test_decision_gate_enforcement_raises_on_block():
    from marketing_mcp.errors import DomainError
    from marketing_mcp.scientific.decision_gate import enforce_decision_gate

    run_id = uuid4()
    # Severe failure: R-hat 1.20
    report = evaluate_diagnostic_policy(
        run_id=run_id,
        max_rhat=1.20,
        divergences=0,
        min_bfmi=0.5,
    )
    assert report.decision_status == "block"

    with pytest.raises(DomainError) as exc_info:
        enforce_decision_gate(report, action="optimize_budget")

    assert exc_info.value.code == "MODEL_NOT_VALIDATED"
    assert "block" in exc_info.value.message


def test_decision_gate_enforcement_allows_on_pass():
    from marketing_mcp.scientific.decision_gate import enforce_decision_gate

    run_id = uuid4()
    report = evaluate_diagnostic_policy(
        run_id=run_id,
        max_rhat=1.002,
        divergences=0,
        min_bfmi=0.8,
    )
    assert report.decision_status == "pass"

    # Should not raise
    enforce_decision_gate(report, action="optimize_budget")
