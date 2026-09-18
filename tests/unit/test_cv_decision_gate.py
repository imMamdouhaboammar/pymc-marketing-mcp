from unittest.mock import MagicMock

import pytest

from marketing_mcp.domain.diagnostics.gate import DecisionGate
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import CrossValidateMMMInput, ModelRecord, SamplerConfig
from marketing_mcp.security.principal import Principal
from marketing_mcp.services.decision_service import DecisionService
from marketing_mcp.services.diagnostics_service import DiagnosticsService
from marketing_mcp.storage.metadata import SQLiteMetadataStore


def test_decision_gate_blocks_on_blocked_predictive_failure():
    gate = DecisionGate(decision_status="blocked_predictive_failure", failures=[{"code": "CV_PREDICTIVE_FAILURE"}])
    with pytest.raises(DomainError) as exc:
        gate.require_decision_access()
    assert exc.value.code == "MODEL_NOT_VALIDATED"
    assert "diagnostic checks" in exc.value.message

def test_diagnostics_service_cross_validate_persists_failure_and_blocks_optimizer(tmp_path):
    metadata = SQLiteMetadataStore(tmp_path / "meta.db")
    modeling = MagicMock()

    model_rec = ModelRecord(
        model_id="mmm-cv-test-1",
        model_type="mmm",
        dataset_id="ds-1",
        config={
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": ["meta", "google"],
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
    modeling.datasets.load.return_value = MagicMock()

    # Mock adapter returning failing CV metrics (mean_nrmse = 0.966 > 0.50)
    mock_adapter = MagicMock()
    mock_adapter.time_slice_cross_validate.return_value = {
        "folds": 3,
        "metrics": [{"fold": 1, "out_of_sample_nrmse": 0.966}],
        "mean_out_of_sample_rmse": 450.0,
        "mean_out_of_sample_nrmse": 0.966,
        "stability_findings": [],
        "decision_provenance": {
            "metric": "NRMSE",
            "observed": 0.966,
            "threshold": 0.50,
            "decision": "blocked_predictive_failure",
        },
    }
    modeling.adapter_factory.return_value = mock_adapter

    diag_service = DiagnosticsService(metadata, modeling)
    cv_input = CrossValidateMMMInput(
        model_id="mmm-cv-test-1",
        n_init=20,
        forecast_horizon=5,
        step_size=5,
        sampler=SamplerConfig(draws=50, tune=50, chains=2),
    )

    res = diag_service.cross_validate(cv_input)
    assert res["mean_out_of_sample_nrmse"] == 0.966
    assert res["decision_provenance"]["decision"] == "blocked_predictive_failure"

    # Verify model record was updated in metadata store
    updated_rec = metadata.get_model("mmm-cv-test-1")
    assert updated_rec["validation_state"] == "blocked_predictive_failure"
    assert "cross_validation" in updated_rec["diagnostics"]
    assert updated_rec["diagnostics"]["cross_validation"]["mean_out_of_sample_nrmse"] == 0.966

    # Verify DecisionService now BLOCKS optimization
    decision_service = DecisionService(metadata, modeling)
    modeling.status.return_value = ModelRecord(**updated_rec)
    opt_input = MagicMock()
    opt_input.model_id = "mmm-cv-test-1"

    with pytest.raises(DomainError) as exc:
        decision_service.optimize(opt_input)
    assert exc.value.code == "MODEL_NOT_VALIDATED"

@pytest.mark.anyio
async def test_cross_validate_mmm_tool_next_actions_on_failure():

    from marketing_mcp.mcp.tools.mmm import register_mmm_tools

    mock_mcp = MagicMock()
    registered_tools = {}
    def tool_decorator(**kwargs):
        def wrapper(fn):
            registered_tools[kwargs.get("name", fn.__name__)] = fn
            return fn
        return wrapper
    mock_mcp.tool = tool_decorator

    mock_app = MagicMock()
    mock_app.metadata.get_model.return_value = {"model_id": "m-1", "tenant_id": "default", "owner": "local"}
    mock_app.diagnostics.cross_validate.return_value = {
        "mean_out_of_sample_nrmse": 0.966,
        "decision_impact": "blocked_predictive_failure",
        "failures": [{"metric": "cross_validation_nrmse", "observed": 0.966}],
        "stability_findings": [],
    }

    mock_context = MagicMock()
    principal = Principal(subject="tester", auth_type="api_key", scopes=frozenset(["*"]), tenant_id="default")
    mock_context.principal = principal
    register_mmm_tools(mock_mcp, mock_app, context_provider=lambda: mock_context)

    tool_fn = registered_tools["cross_validate_mmm"]
    cv_input = CrossValidateMMMInput(
        model_id="m-1",
        n_init=20,
        forecast_horizon=5,
        step_size=5,
        sampler=SamplerConfig(draws=50, tune=50, chains=2),
    )
    result = await tool_fn(cv_input)
    assert "optimize_budget" not in result["next_actions"]
    assert "validate_dataset" in result["next_actions"]
