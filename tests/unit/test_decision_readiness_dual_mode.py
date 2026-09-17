from __future__ import annotations

import pytest

from marketing_mcp.domain.diagnostics.gate import DecisionGate, DecisionReadiness
from marketing_mcp.errors import DomainError


def test_decision_readiness_production_mode_blocking():
    """Verify that in production mode, any diagnostic failure blocks all decision tools."""
    gate = DecisionGate(
        decision_status="blocked_predictive_failure",
        failures=[{"metric": "cv_nrmse", "observed": 0.966, "threshold": 0.50}],
        model_id="mod_test_123",
        dataset_id="ds_test_123",
        mode="production",
    )

    readiness = gate.evaluate_readiness()
    assert readiness.decision_eligible is False
    assert "optimize_budget" in readiness.blocked_actions
    assert "simulate_budget" in readiness.blocked_actions
    assert len(readiness.failed_checks) >= 1

    with pytest.raises(DomainError) as exc_info:
        gate.require_decision_access("optimize_budget")
    assert exc_info.value.code == "MODEL_NOT_VALIDATED"

    with pytest.raises(DomainError) as exc_info:
        gate.require_decision_access("simulate_budget")
    assert exc_info.value.code == "MODEL_NOT_VALIDATED"


def test_decision_readiness_exploratory_mode_permits_simulation_with_watermark():
    """Verify that exploratory mode permits inspection/simulation with watermark but still blocks optimizer."""
    gate = DecisionGate(
        decision_status="blocked_predictive_failure",
        failures=[{"metric": "cv_nrmse", "observed": 0.966, "threshold": 0.50}],
        model_id="mod_test_123",
        dataset_id="ds_test_123",
        mode="exploratory",
    )

    readiness = gate.evaluate_readiness()
    assert readiness.decision_eligible is False
    assert "simulate_budget" in readiness.allowed_actions
    assert "optimize_budget" in readiness.blocked_actions
    assert "EXPLORATORY" in readiness.audit_watermark

    # Simulation access succeeds in exploratory mode
    readiness_sim = gate.require_decision_access("simulate_budget")
    assert readiness_sim.decision_eligible is False
    assert readiness_sim.audit_watermark is not None

    # Optimization access is STILL strictly blocked in exploratory mode
    with pytest.raises(DomainError) as exc_info:
        gate.require_decision_access("optimize_budget")
    assert exc_info.value.code == "MODEL_NOT_VALIDATED"


def test_decision_readiness_approved_model():
    """Verify that an approved model grants full decision access without watermarks."""
    gate = DecisionGate(
        decision_status="approved",
        failures=[],
        model_id="mod_clean_456",
        dataset_id="ds_clean_456",
        mode="production",
    )

    readiness = gate.evaluate_readiness()
    assert readiness.decision_eligible is True
    assert "optimize_budget" in readiness.allowed_actions
    assert "simulate_budget" in readiness.allowed_actions
    assert len(readiness.blocked_actions) == 0
    assert readiness.audit_watermark is None

    # Both succeed
    gate.require_decision_access("optimize_budget")
    gate.require_decision_access("simulate_budget")
