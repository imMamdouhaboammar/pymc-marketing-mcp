from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
import xarray as xr

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import BudgetOptimizationInput, ChannelConstraint
from marketing_mcp.services.decision_service import DecisionService


class ControlledOptimizer:
    outcome = SimpleNamespace(success=True, message="converged")
    error: Exception | None = None

    def __init__(self, model, start_date, end_date):
        self.model = model

    def optimize_budget(self, budget, budget_bounds=None):
        if self.error is not None:
            raise self.error
        allocation = xr.DataArray(
            [25.0, 75.0],
            dims=("channel",),
            coords={"channel": ["meta", "google"]},
        )
        return allocation, self.outcome

    def sample_response_distribution(self, allocation_strategy, **kwargs):
        total = float(allocation_strategy.sum())
        response = xr.DataArray([[total, total]], dims=("chain", "draw"))
        return {
            "posterior_predictive": xr.Dataset(
                {"total_media_contribution_original_scale": response}
            )
        }


@pytest.fixture
def model():
    return SimpleNamespace(
        date_column="date",
        channel_columns=["meta", "google"],
        dims=(),
        X=pd.DataFrame(
            {
                "date": pd.date_range("2025-01-06", periods=8, freq="W-MON"),
                "meta": [10.0] * 8,
                "google": [30.0] * 8,
            }
        ),
    )


@pytest.fixture
def adapter():
    ControlledOptimizer.outcome = SimpleNamespace(success=True, message="converged")
    ControlledOptimizer.error = None
    value = object.__new__(PyMCMarketingAdapter)
    value.OptimizerWrapper = ControlledOptimizer
    return value


def test_optimizer_upstream_exception_becomes_stable_domain_error(adapter, model):
    ControlledOptimizer.error = ValueError("solver internals changed")

    with pytest.raises(DomainError) as exc_info:
        adapter.optimize_budget(model, 100.0, 2, {})

    assert exc_info.value.code == "OPTIMIZATION_FAILED"
    assert exc_info.value.message == "Budget optimizer failed to produce a trustworthy allocation"
    assert exc_info.value.evidence == {
        "optimizer_message": "solver internals changed",
        "optimizer_status": "exception",
        "type": "ValueError",
    }


@pytest.mark.parametrize(
    "outcome",
    [
        SimpleNamespace(success=False, message="iteration limit reached"),
        SimpleNamespace(message="status unavailable"),
    ],
    ids=["nonconverged", "missing-success"],
)
def test_optimizer_requires_explicit_success(adapter, model, outcome):
    ControlledOptimizer.outcome = outcome

    with pytest.raises(DomainError) as exc_info:
        adapter.optimize_budget(model, 100.0, 2, {})

    assert exc_info.value.code == "OPTIMIZATION_FAILED"
    assert exc_info.value.evidence["optimizer_success"] is getattr(outcome, "success", None)


def test_supported_optimizer_result_conserves_budget_and_bounds(adapter, model):
    result = adapter.optimize_budget(
        model,
        100.0,
        2,
        {
            "meta": ChannelConstraint(min=20.0, max=30.0).model_dump(exclude_none=True),
            "google": ChannelConstraint(min=70.0, max=80.0).model_dump(exclude_none=True),
        },
    )

    allocation = result["recommended_allocation"]
    assert sum(allocation.values()) == pytest.approx(100.0)
    assert 20.0 <= allocation["meta"] <= 30.0
    assert 70.0 <= allocation["google"] <= 80.0
    assert result["optimizer_success"] is True


class RecordingMetadata:
    def __init__(self):
        self.scenarios = []

    def put_scenario(self, payload):
        self.scenarios.append(payload)


class ControlledAdapter:
    def __init__(self, result):
        self.result = result

    def optimize_budget(self, *args, **kwargs):
        return self.result


class ControlledModeling:
    def __init__(self, result, model):
        self.adapter = ControlledAdapter(result)
        self.model = model
        self.record = SimpleNamespace(
            diagnostics={"failures": [], "warnings": []},
            validation_state="approved",
            dataset_id="dataset_1",
            config={"provenance": {}},
        )

    def status(self, model_id):
        return self.record

    def load_model(self, model_id):
        return self.model, self.record

    def adapter_factory(self):
        return self.adapter


@pytest.mark.parametrize(
    "result",
    [
        {"recommended_allocation": {"meta": 25.0, "google": 75.0}},
        {
            "recommended_allocation": {"meta": 25.0, "google": 75.0},
            "optimizer_success": False,
        },
    ],
    ids=["missing-success", "false-success"],
)
def test_unsuccessful_optimizer_result_is_not_persisted_or_authorized(model, result):
    metadata = RecordingMetadata()
    service = DecisionService(metadata, ControlledModeling(result, model))

    with pytest.raises(DomainError) as exc_info:
        service.optimize(
            BudgetOptimizationInput(model_id="mmm_1", budget=100.0, planning_periods=2)
        )

    assert exc_info.value.code == "OPTIMIZATION_FAILED"
    assert metadata.scenarios == []
