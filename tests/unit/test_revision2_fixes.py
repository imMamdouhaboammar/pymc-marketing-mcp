"""Unit tests verifying fixes for Revision 2 test report findings."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
import xarray as xr

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.server import create_server
from marketing_mcp.schemas.models import DatasetValidationResult, Finding
from marketing_mcp.services.decision_service import DecisionService
from marketing_mcp.services.plotting_service import PlottingService

# ---------------------------------------------------------------------------
# Finding A: Schema Discoverability for register_dataset
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_register_dataset_schema_has_content_and_descriptions():
    mcp = create_server()
    tools = await mcp.list_tools()
    reg_tool = next((t for t in tools if t.name == "register_dataset"), None)
    assert reg_tool is not None, "register_dataset tool must exist"

    props = reg_tool.input_schema.get("properties", {})
    assert "content" in props, "content parameter must be exposed in schema"
    assert "filename" in props, "filename parameter must be exposed in schema"
    assert "content_base64" in props
    assert "url" in props
    assert "path" in props

    # Descriptions must be present and helpful
    assert props["content"].get("description"), "content must have description"
    assert "csv" in props["content"]["description"].lower()
    assert props["filename"].get("description")
    assert props["path"].get("description")


# ---------------------------------------------------------------------------
# Carry-over 2: No phantom repair_dataset in next_actions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_inspect_and_validate_do_not_suggest_phantom_repair_dataset():
    from marketing_mcp.mcp.tools.datasets import register_datasets_tools
    from marketing_mcp.schemas.models import DatasetInspection

    mock_app = MagicMock()
    mock_app.metadata.get_dataset.return_value = {"owner": "test", "dataset_id": "d1", "tenant_id": "test"}
    mock_app.datasets.inspect.return_value = DatasetInspection(
        dataset_id="d1",
        rows=3,
        frequency=None,
        date_range={"min": None, "max": None},
        possible_targets=[],
        possible_channels=[],
        possible_controls=[],
        missing_periods=[],
        issues=[],
        mmm_candidate=False,
    )
    mock_app.datasets.validate.return_value = DatasetValidationResult(
        dataset_id="d1",
        valid_for_modeling=False,
        findings=[
            Finding(
                severity="error",
                code="BAD_DATA",
                message="Dataset invalid",
                evidence={},
                next_action="Fix data",
            )
        ],
    )

    mock_mcp = MagicMock()
    tool_funcs = {}

    def mock_tool(name=None, description=None):
        def decorator(fn):
            tool_funcs[name or fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = mock_tool
    mock_principal = MagicMock()
    mock_principal.subject = "test"
    mock_principal.tenant_id = "test"
    mock_principal.scopes = ["marketing:read", "marketing:admin", "marketing:write"]
    register_datasets_tools(mock_mcp, mock_app, context_provider=lambda: MagicMock(principal=mock_principal))

    inspect_res = await tool_funcs["inspect_dataset"](dataset_id="d1")
    assert "repair_dataset" not in inspect_res.get("next_actions", [])
    assert "register_dataset" in inspect_res.get("next_actions", [])

    val_res = await tool_funcs["validate_dataset"](
        dataset_id="d1",
        date_column="date",
        target_column="sales",
        channel_columns=["c1"],
    )
    assert "repair_dataset" not in val_res.get("next_actions", [])
    assert "register_dataset" in val_res.get("next_actions", [])


# ---------------------------------------------------------------------------
# Finding B: Saturation curves rendering with model.plot or plot_curve_hdi
# ---------------------------------------------------------------------------


def test_saturation_curves_renders_without_type_error(tmp_path):
    import matplotlib.pyplot as plt

    service = PlottingService(tmp_path)

    # Mock model that mimics pymc-marketing MMM
    model = MagicMock()
    model.channel_columns = ["google", "meta"]

    # Mock DataArray for curve
    da = xr.DataArray(
        np.ones((1, 10, 20, 2)),
        dims=("chain", "draw", "x", "channel"),
        coords={
            "channel": ["google", "meta"],
            "x": np.linspace(0, 1, 20),
        },
    )
    model.sample_saturation_curve = MagicMock(return_value=da)

    # Strategy 1: model.plot.saturation_curves
    fig, ax = plt.subplots()
    model.plot = MagicMock()
    model.plot.saturation_curves = MagicMock(return_value=(fig, [ax]))

    img = service.generate_plot(model, "m100", "saturation_curves")
    assert len(img) > 0
    assert img[:8] == b"\x89PNG\r\n\x1a\n"


# ---------------------------------------------------------------------------
# Finding C: Per-channel response curves
# ---------------------------------------------------------------------------


def test_response_curves_returns_per_channel_trajectories():
    adapter = PyMCMarketingAdapter()
    model = MagicMock()

    # Create a 4D DataArray as returned by sample_saturation_curve
    x_vals = np.linspace(0, 1, 25)
    channels = ["google_spend", "meta_spend"]
    data = np.random.uniform(10, 500, size=(1, 50, len(channels), len(x_vals)))

    da = xr.DataArray(
        data,
        dims=("chain", "draw", "channel", "x"),
        coords={"channel": channels, "x": x_vals},
    )
    model.sample_saturation_curve = MagicMock(return_value=da)

    res = adapter.response_curves(model)
    assert "channels" in res
    assert "summary" in res
    assert "google_spend" in res["channels"]
    assert "meta_spend" in res["channels"]

    ch_curve = res["channels"]["google_spend"]
    assert len(ch_curve["spend_grid"]) > 0
    assert len(ch_curve["median_response"]) == len(ch_curve["spend_grid"])
    assert len(ch_curve["lower_94"]) == len(ch_curve["spend_grid"])
    assert len(ch_curve["upper_94"]) == len(ch_curve["spend_grid"])
    assert "max_response_median" in ch_curve
    assert "half_saturation_spend" in ch_curve


# ---------------------------------------------------------------------------
# Finding D & Carry-Over 1: Identifiability warning carry-forward & MODEL_NOT_DIAGNOSED
# ---------------------------------------------------------------------------


def test_model_not_diagnosed_error_has_evidence_and_next_action():
    mock_metadata = MagicMock()
    mock_modeling = MagicMock()

    # Model record with no diagnostics
    rec = MagicMock()
    rec.diagnostics = None
    rec.validation_state = "not_diagnosed"
    mock_modeling.status.return_value = rec

    service = DecisionService(metadata=mock_metadata, modeling=mock_modeling)
    with pytest.raises(DomainError) as exc_info:
        service._approved("m_undia")

    err = exc_info.value
    assert err.code == "MODEL_NOT_DIAGNOSED"
    assert err.evidence is not None
    assert err.evidence["model_id"] == "m_undia"
    assert err.next_action is not None
    assert "diagnose_mmm" in err.next_action


def test_optimize_budget_surfaces_channel_identifiability_warnings():
    from marketing_mcp.schemas.models import BudgetOptimizationInput

    mock_metadata = MagicMock()
    mock_modeling = MagicMock()

    # Approved model record
    rec = MagicMock()
    rec.diagnostics = {"warnings": [], "failures": []}
    rec.validation_state = "approved"
    rec.dataset_id = "d_test"
    rec.config = {
        "date_column": "date",
        "target_column": "revenue",
        "channel_columns": ["google_spend", "meta_spend"],
    }
    mock_modeling.status.return_value = rec
    mock_modeling.load_model.return_value = (MagicMock(), rec)

    # Dataset validation returned a LONG_ZERO_SPEND_RUN finding for google_spend
    mock_modeling.datasets.validate.return_value = DatasetValidationResult(
        dataset_id="d_test",
        valid_for_modeling=True,
        findings=[
            Finding(
                severity="warning",
                code="LONG_ZERO_SPEND_RUN",
                message="google_spend has 109 zero-spend periods",
                evidence={"column": "google_spend", "periods": 109},
                next_action="Check launch/offline periods and identifiability",
            )
        ],
    )

    mock_adapter = MagicMock()
    mock_adapter.optimize_budget.return_value = {
        "optimizer_success": True,
        "recommended_allocation": {"google_spend": 5000.0, "meta_spend": 2000.0},
        "baseline_allocation": {"google_spend": 0.0, "meta_spend": 2000.0},
    }
    mock_modeling.adapter_factory.return_value = mock_adapter

    service = DecisionService(metadata=mock_metadata, modeling=mock_modeling)
    opt_input = BudgetOptimizationInput(
        model_id="m_app",
        budget=7000.0,
        planning_periods=4,
    )

    res = service.optimize(opt_input)

    assert "warnings" in res
    assert "identifiability_risks" in res
    assert len(res["identifiability_risks"]) > 0

    risk = res["identifiability_risks"][0]
    assert risk["channel"] == "google_spend"
    assert risk["code"] == "IDENTIFIABILITY_RISK"
    assert risk["severity"] == "high"
    assert "LONG_ZERO_SPEND_RUN" in risk["message"]
    assert "lift tests" in risk["next_action"].lower()

    assert res["channel_confidence"]["google_spend"] == "low_sparse_history"
    assert res["channel_confidence"]["meta_spend"] == "high"
