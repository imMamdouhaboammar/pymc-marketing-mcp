from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter


class FakeIncrementality:
    def __init__(self):
        self.calls = []

    def contribution_over_spend(self, **kwargs):
        self.calls.append(("total", kwargs))
        values = np.array(
            [
                [[2.0, 3.0], [1.0, 2.0]],
                [[4.0, 5.0], [3.0, 4.0]],
            ]
        )
        return xr.DataArray(
            values,
            dims=("chain", "draw", "channel"),
            coords={"channel": ["meta", "google"]},
        )

    def marginal_contribution_over_spend(self, **kwargs):
        self.calls.append(("marginal", kwargs))
        values = np.array(
            [
                [[1.0, 2.0], [0.5, 1.0]],
                [[2.0, 3.0], [1.5, 2.0]],
            ]
        )
        return xr.DataArray(
            values,
            dims=("chain", "draw", "channel"),
            coords={"channel": ["meta", "google"]},
        )


class FakeROASModel:
    def __init__(self):
        self.incrementality = FakeIncrementality()


def test_incremental_roas_uses_official_total_and_marginal_apis():
    adapter = object.__new__(PyMCMarketingAdapter)
    model = FakeROASModel()

    result = adapter.incremental_roas(model)

    assert [call[0] for call in model.incrementality.calls] == ["total", "marginal"]
    assert model.incrementality.calls[0][1]["frequency"] == "all_time"
    assert model.incrementality.calls[1][1]["frequency"] == "all_time"
    assert result["method"] == "pymc_marketing_incrementality"
    assert {row["channel"] for row in result["channels"]} == {"meta", "google"}
    meta = next(row for row in result["channels"] if row["channel"] == "meta")
    assert meta["total_iroas"]["median"] == 2.5
    assert meta["marginal_iroas"]["probability_gt_1"] == 0.5


class FakeBudgetWrapper:
    instances = []

    def __init__(self, model, start_date, end_date):
        self.model = model
        self.start_date = start_date
        self.end_date = end_date
        self.sampled_allocations = []
        self.optimize_calls = []
        FakeBudgetWrapper.instances.append(self)

    def sample_response_distribution(self, allocation_strategy, **kwargs):
        allocation = allocation_strategy.copy()
        self.sampled_allocations.append(allocation)
        total = float(allocation.sum())
        response = xr.DataArray(
            np.array([[total * 1.0, total * 1.1], [total * 0.9, total * 1.2]]),
            dims=("chain", "draw"),
        )
        return {
            "posterior_predictive": xr.Dataset(
                {"total_media_contribution_original_scale": response}
            )
        }

    def optimize_budget(self, budget, budget_bounds=None):
        self.optimize_calls.append((budget, budget_bounds))
        allocation = xr.DataArray(
            [budget * 0.25, budget * 0.75],
            dims=("channel",),
            coords={"channel": ["meta", "google"]},
        )
        return allocation, SimpleNamespace(success=True, message="ok")


class FakeBudgetModel:
    def __init__(self):
        self.date_column = "date"
        self.channel_columns = ["meta", "google"]
        self.dims = ()
        self.X = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-06", periods=12, freq="W-MON"),
                "meta": [10.0] * 12,
                "google": [30.0] * 12,
            }
        )


def _budget_adapter():
    FakeBudgetWrapper.instances.clear()
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.OptimizerWrapper = FakeBudgetWrapper
    return adapter


def test_simulate_budget_samples_requested_allocations_without_optimizing():
    adapter = _budget_adapter()
    model = FakeBudgetModel()

    result = adapter.simulate_budget(
        model,
        baseline_allocation={"meta": 20.0, "google": 60.0},
        scenario_allocation={"meta": 16.0, "google": 69.0},
        planning_periods=2,
    )

    wrapper = FakeBudgetWrapper.instances[-1]
    assert len(wrapper.sampled_allocations) == 2
    assert wrapper.optimize_calls == []
    assert result["baseline_response"]["median"] == 84.0
    assert result["scenario_response"]["median"] == 89.25
    assert result["comparison"]["probability_scenario_beats_baseline"] == 1.0


def test_optimize_budget_samples_baseline_and_recommended_allocations():
    adapter = _budget_adapter()
    model = FakeBudgetModel()

    result = adapter.optimize_budget(
        model,
        budget=100.0,
        planning_periods=2,
        constraints={},
    )

    wrapper = FakeBudgetWrapper.instances[-1]
    assert len(wrapper.optimize_calls) == 1
    assert len(wrapper.sampled_allocations) == 2
    assert result["baseline_allocation"] == {"meta": 25.0, "google": 75.0}
    assert result["recommended_allocation"] == {"meta": 25.0, "google": 75.0}
    assert "baseline_response" in result
    assert "recommended_response" in result
    assert "comparison" in result
