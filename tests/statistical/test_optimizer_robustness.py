from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
import xarray as xr
from pymc_marketing.mmm.budget_optimizer import MinimizeException

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.errors import DomainError


class FlakyOptimizer:
    def __init__(self, model, start_date, end_date):
        self.model = model
        self.call_count = 0
        self.initializations = []

    def optimize_budget(self, budget, budget_bounds=None, x0=None, minimize_kwargs=None):
        self.call_count += 1
        self.initializations.append(x0)
        # First attempt (uniform x0 is None) fails with line search derivative error
        if self.call_count == 1:
            raise MinimizeException(
                "Optimization failed: Positive directional derivative for linesearch"
            )
        
        # Second attempt (with alternative x0) succeeds
        allocation = xr.DataArray(
            [40.0, 60.0],
            dims=("channel",),
            coords={"channel": ["meta", "google"]},
        )
        outcome = SimpleNamespace(
            success=True,
            message="Optimization terminated successfully",
            fun=-123.45,
        )
        return allocation, outcome

    def sample_response_distribution(self, allocation_strategy, **kwargs):
        total = float(allocation_strategy.sum())
        response = xr.DataArray([[total, total]], dims=("chain", "draw"))
        return {
            "posterior_predictive": xr.Dataset(
                {"total_media_contribution_original_scale": response}
            )
        }


class AlwaysFailingOptimizer(FlakyOptimizer):
    def optimize_budget(self, budget, budget_bounds=None, x0=None, minimize_kwargs=None):
        self.call_count += 1
        self.initializations.append(x0)
        raise MinimizeException(
            "Optimization failed: Positive directional derivative for linesearch"
        )


@pytest.fixture
def mock_model():
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


def test_optimizer_retries_on_line_search_failure(mock_model):
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.OptimizerWrapper = FlakyOptimizer

    result = adapter.optimize_budget(
        mock_model,
        budget=100.0,
        planning_periods=2,
        constraints={},
    )

    assert result["optimizer_success"] is True
    assert result["converged"] is True
    assert result["fallback_used"] is True
    assert result["optimizer_status"] == "converged"
    assert result["solver"] == "SLSQP"
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["success"] is False
    assert "Positive directional derivative" in result["attempts"][0]["message"]
    assert result["attempts"][1]["success"] is True
    assert result["constraint_validation"]["budget_conserved"] is True
    assert result["constraint_validation"]["total_allocated"] == pytest.approx(100.0)


def test_optimizer_fails_safely_when_all_retries_fail(mock_model):
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.OptimizerWrapper = AlwaysFailingOptimizer

    with pytest.raises(DomainError) as exc_info:
        adapter.optimize_budget(
            mock_model,
            budget=100.0,
            planning_periods=2,
            constraints={},
        )

    assert exc_info.value.code == "OPTIMIZATION_FAILED"
    assert "Positive directional derivative" in exc_info.value.evidence["optimizer_message"]
    assert exc_info.value.evidence["optimizer_status"] in ("failed", "exception")
