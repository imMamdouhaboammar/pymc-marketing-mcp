import pytest

from marketing_mcp.domain.diagnostics.gate import DecisionGate
from marketing_mcp.errors import DomainError


def test_rejected_model_blocks_decisions():
    gate = DecisionGate(
        decision_status="rejected",
        failures=[{"metric": "r_hat", "observed": 1.08, "required": "<= 1.01"}],
    )
    with pytest.raises(DomainError) as e:
        gate.require_decision_access()
    assert e.value.code == "MODEL_NOT_VALIDATED"


def test_approved_with_caution_allows_decisions():
    DecisionGate(decision_status="approved_with_caution", failures=[]).require_decision_access()
