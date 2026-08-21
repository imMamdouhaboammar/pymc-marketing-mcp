from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.schemas.models import (
    BudgetCellChange,
    BudgetCellConstraint,
    BudgetOptimizationInput,
    BudgetSimulationInput,
)
from marketing_mcp.services.decision_service import DecisionService


class FakeMetadata:
    def __init__(self):
        self.scenarios = []

    def put_scenario(self, payload):
        self.scenarios.append(payload)


class FakePanelAdapter:
    def __init__(self):
        self.simulation_calls = []

    def simulate_budget(self, model, baseline, scenario, planning_periods):
        self.simulation_calls.append((baseline, scenario, planning_periods))
        return {
            "baseline_response": {"median": 100.0},
            "scenario_response": {"median": 105.0},
            "comparison": {"probability_scenario_beats_baseline": 0.75},
            "response_variable": "total_media_contribution_original_scale",
        }


class FakePanelModeling:
    def __init__(self, model):
        self.model = model
        self.adapter = FakePanelAdapter()
        self.record = SimpleNamespace(
            diagnostics={"failures": []},
            validation_state="approved",
            dataset_id="dataset_panel",
            config={"provenance": {"pymc-marketing": "0.19.4"}},
        )

    def status(self, model_id):
        return self.record

    def load_model(self, model_id):
        return self.model, self.record

    def adapter_factory(self):
        return self.adapter


def _panel_model():
    rows = []
    dates = pd.date_range("2025-01-06", periods=3, freq="W-MON")
    for date_i, date in enumerate(dates, start=1):
        for geo_i, geo in enumerate(["riyadh", "jeddah"], start=1):
            rows.append(
                {
                    "date": date,
                    "geo": geo,
                    "meta": float(10 * date_i + geo_i),
                    "google": float(20 * date_i + geo_i),
                }
            )
    return SimpleNamespace(
        date_column="date",
        channel_columns=["meta", "google"],
        dims=("geo",),
        X=pd.DataFrame(rows),
    )


def _cell_amount(allocation, channel, geo):
    for cell in allocation["cells"]:
        if cell["channel"] == channel and cell["dimensions"] == {"geo": geo}:
            return cell["amount"]
    raise AssertionError(f"cell not found: {channel}, {geo}")


def test_simulation_supports_channel_dimension_cell_changes():
    model = _panel_model()
    modeling = FakePanelModeling(model)
    service = DecisionService(FakeMetadata(), modeling)
    request = BudgetSimulationInput(
        model_id="mmm_panel",
        planning_periods=2,
        changes={},
        cell_changes=[
            BudgetCellChange(
                channel="meta",
                dimensions={"geo": "riyadh"},
                type="relative",
                value=-0.20,
            ),
            BudgetCellChange(
                channel="google",
                dimensions={"geo": "jeddah"},
                type="relative",
                value=0.15,
            ),
        ],
    )

    result = service.simulate(request)

    baseline = result["baseline_allocation"]
    scenario = result["scenario_allocation"]
    assert baseline["dimensions"] == ["geo"]
    assert _cell_amount(baseline, "meta", "riyadh") == pytest.approx(52.0)
    assert _cell_amount(baseline, "google", "jeddah") == pytest.approx(104.0)
    assert _cell_amount(scenario, "meta", "riyadh") == pytest.approx(41.6)
    assert _cell_amount(scenario, "google", "jeddah") == pytest.approx(119.6)


from typing import ClassVar


class FakeMultidimensionalWrapper:
    instances: ClassVar[list] = []

    def __init__(self, model, start_date, end_date):
        self.model = model
        self.start_date = start_date
        self.end_date = end_date
        self.sampled_allocations = []
        self.optimize_calls = []
        FakeMultidimensionalWrapper.instances.append(self)

    def sample_response_distribution(self, allocation_strategy, **kwargs):
        self.sampled_allocations.append(allocation_strategy.copy())
        total = float(allocation_strategy.sum())
        response = xr.DataArray(
            np.array([[total, total * 1.1], [total * 0.9, total * 1.2]]),
            dims=("chain", "draw"),
        )
        return {
            "posterior_predictive": xr.Dataset(
                {"total_media_contribution_original_scale": response}
            )
        }

    def optimize_budget(self, budget, budget_bounds=None):
        self.optimize_calls.append((budget, budget_bounds.copy()))
        values = np.array([[20.0, 30.0], [25.0, 25.0]])
        allocation = xr.DataArray(
            values,
            dims=("channel", "geo"),
            coords={
                "channel": ["meta", "google"],
                "geo": ["riyadh", "jeddah"],
            },
        )
        return allocation, SimpleNamespace(success=True, message="ok")


def _adapter():
    FakeMultidimensionalWrapper.instances.clear()
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.OptimizerWrapper = FakeMultidimensionalWrapper
    return adapter


def test_adapter_samples_multidimensional_allocation_with_channel_and_geo_dims():
    adapter = _adapter()
    model = _panel_model()
    baseline = {
        "dimensions": ["geo"],
        "cells": [
            {"channel": "meta", "dimensions": {"geo": "riyadh"}, "amount": 20.0},
            {"channel": "meta", "dimensions": {"geo": "jeddah"}, "amount": 30.0},
            {"channel": "google", "dimensions": {"geo": "riyadh"}, "amount": 25.0},
            {"channel": "google", "dimensions": {"geo": "jeddah"}, "amount": 25.0},
        ],
    }
    scenario = {
        **baseline,
        "cells": [dict(cell) for cell in baseline["cells"]],
    }
    scenario["cells"][0] = {**scenario["cells"][0], "amount": 15.0}

    adapter.simulate_budget(model, baseline, scenario, planning_periods=2)

    wrapper = FakeMultidimensionalWrapper.instances[-1]
    assert wrapper.sampled_allocations[0].dims == ("channel", "geo")
    assert wrapper.sampled_allocations[0].sel(channel="meta", geo="riyadh").item() == 20.0
    assert wrapper.sampled_allocations[1].sel(channel="meta", geo="riyadh").item() == 15.0


def test_optimize_budget_accepts_exact_dimension_cell_constraints():
    adapter = _adapter()
    model = _panel_model()
    request = BudgetOptimizationInput(
        model_id="mmm_panel",
        budget=100.0,
        planning_periods=2,
        constraints={},
        cell_constraints=[
            BudgetCellConstraint(
                channel="meta",
                dimensions={"geo": "riyadh"},
                min=10.0,
                max=40.0,
            ),
            BudgetCellConstraint(
                channel="google",
                dimensions={"geo": "jeddah"},
                fixed=25.0,
            ),
        ],
    )

    result = adapter.optimize_budget(
        model,
        request.budget,
        request.planning_periods,
        request.constraints,
        [cell.model_dump(exclude_none=True) for cell in request.cell_constraints],
    )

    wrapper = FakeMultidimensionalWrapper.instances[-1]
    _, bounds = wrapper.optimize_calls[0]
    assert bounds.dims == ("channel", "geo", "bound")
    assert bounds.sel(channel="meta", geo="riyadh", bound="lower").item() == 10.0
    assert bounds.sel(channel="meta", geo="riyadh", bound="upper").item() == 40.0
    assert bounds.sel(channel="google", geo="jeddah", bound="lower").item() == 25.0
    assert bounds.sel(channel="google", geo="jeddah", bound="upper").item() == 25.0
    assert result["recommended_allocation"]["dimensions"] == ["geo"]
    assert _cell_amount(result["recommended_allocation"], "meta", "riyadh") == 20.0
