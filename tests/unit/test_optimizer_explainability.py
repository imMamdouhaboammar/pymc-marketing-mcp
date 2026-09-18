from unittest.mock import MagicMock

from marketing_mcp.schemas.models import BudgetOptimizationInput, ChannelConstraint, ModelRecord
from marketing_mcp.services.decision_service import DecisionService
from marketing_mcp.storage.metadata import SQLiteMetadataStore


def test_optimizer_provides_allocation_rationale_and_warns_on_sub_marginal_channel(tmp_path):
    metadata = SQLiteMetadataStore(tmp_path / "meta.db")
    modeling = MagicMock()

    # Create an approved model record
    model_rec = ModelRecord(
        model_id="mmm-opt-test-1",
        model_type="mmm",
        dataset_id="ds-1",
        config={
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": ["google", "linkedin"],
        },
        diagnostics={"failures": []},
        validation_state="approved",
        artifact_path="/dummy/path",
        metrics={},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    metadata.put_model(model_rec.model_dump())
    modeling.status.return_value = model_rec

    mock_model = MagicMock()
    mock_model.channel_columns = ["google", "linkedin"]
    modeling.load_model.return_value = (mock_model, model_rec)

    # Mock adapter returning an allocation where linkedin receives $10,000 with low iROAS (0.63)
    mock_adapter = MagicMock()
    mock_adapter.optimize_budget.return_value = {
        "optimizer_success": True,
        "recommended_allocation": {"google": 40000.0, "linkedin": 10000.0},
        "baseline_allocation": {"google": 30000.0, "linkedin": 20000.0},
        "expected_response": 120000.0,
    }
    # Mock iroas calculation where google is 2.5 and linkedin is 0.63
    mock_adapter.calculate_iroas.return_value = {
        "google": {"mean": 2.5, "p_above_1": 0.95},
        "linkedin": {"mean": 0.63, "p_above_1": 0.08},
    }
    modeling.adapter_factory.return_value = mock_adapter

    decision_service = DecisionService(metadata, modeling)
    opt_input = BudgetOptimizationInput(
        model_id="mmm-opt-test-1",
        budget=50000.0,
        planning_periods=4,
        constraints={
            "linkedin": ChannelConstraint(min=5000.0, max=20000.0),
        },
    )

    result = decision_service.optimize(opt_input)

    # 1. Rationale must be attached
    assert "allocation_rationale" in result
    rationale = result["allocation_rationale"]
    assert "linkedin" in rationale
    assert "google" in rationale

    # 2. LinkedIn rationale must state sub_marginal warning and explain constraints
    linkedin_info = rationale["linkedin"]
    assert linkedin_info["economic_verdict"] == "sub_marginal_warning"
    assert linkedin_info["allocated_spend"] == 10000.0

    # 3. An explicit warning for sub-marginal channel allocation must be emitted
    warning_codes = [w.get("code") if isinstance(w, dict) else getattr(w, "code", "") for w in result.get("warnings", [])]
    assert "ECONOMIC_SUB_MARGINAL_ALLOCATION" in warning_codes
