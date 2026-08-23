from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    BudgetChange,
    BudgetSimulationInput,
    FlightingOptimizationInput,
)
from marketing_mcp.services.decision_service import DecisionService


class FakeMetadata:
    def __init__(self):
        self.scenarios = []

    def put_scenario(self, payload):
        self.scenarios.append(payload)


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def simulate_budget(self, model, baseline, scenario, planning_periods):
        self.calls.append((baseline, scenario, planning_periods))
        return {
            "baseline_response": {"median": 100.0, "lower": 90.0, "upper": 110.0},
            "scenario_response": {"median": 108.0, "lower": 96.0, "upper": 118.0},
            "comparison": {
                "probability_scenario_beats_baseline": 0.82,
                "delta": {"median": 8.0, "lower": -2.0, "upper": 18.0},
            },
            "response_variable": "total_media_contribution_original_scale",
            "planning_start": "2026-01-05",
            "planning_end": "2026-01-12",
        }


class FakeModeling:
    def __init__(self):
        self.adapter = FakeAdapter()
        self.record = SimpleNamespace(
            diagnostics={"failures": []},
            validation_state="approved",
            dataset_id="dataset_1",
            config={"provenance": {"pymc-marketing": "0.19.4"}},
        )
        self.model = SimpleNamespace(
            date_column="date",
            channel_columns=["meta", "google"],
            dims=(),
            X=pd.DataFrame(
                {
                    "date": pd.date_range("2025-01-06", periods=3, freq="W-MON"),
                    "meta": [10.0, 20.0, 30.0],
                    "google": [30.0, 40.0, 50.0],
                }
            ),
        )

    def status(self, model_id):
        return self.record

    def load_model(self, model_id):
        return self.model, self.record

    def adapter_factory(self):
        return self.adapter


def test_simulation_surfaces_posterior_comparison_for_agent_consumption():
    metadata = FakeMetadata()
    modeling = FakeModeling()
    service = DecisionService(metadata, modeling)
    request = BudgetSimulationInput(
        model_id="mmm_1",
        planning_periods=2,
        changes={
            "meta": BudgetChange(type="relative", value=-0.20),
            "google": BudgetChange(type="relative", value=0.15),
        },
    )

    result = service.simulate(request)

    assert result["baseline_allocation"] == {"meta": 50.0, "google": 90.0}
    assert result["scenario_allocation"]["meta"] == pytest.approx(40.0)
    assert result["scenario_allocation"]["google"] == pytest.approx(103.5)
    assert result["baseline_response"]["median"] == 100.0
    assert result["scenario_response"]["median"] == 108.0
    assert result["comparison"]["probability_scenario_beats_baseline"] == 0.82
    assert "posterior_result" not in result
    assert len(modeling.adapter.calls) == 1
    baseline_call, scenario_call, periods_call = modeling.adapter.calls[0]
    assert baseline_call == {"meta": 50.0, "google": 90.0}
    assert scenario_call["meta"] == pytest.approx(40.0)
    assert scenario_call["google"] == pytest.approx(103.5)
    assert periods_call == 2
    assert (
        metadata.scenarios[0]["result"]["comparison"]["probability_scenario_beats_baseline"] == 0.82
    )


def test_flighting_rejects_unmapped_transform_families_instead_of_silent_fallback():
    """A fitted model whose transform classes are not in the supported maps must
    fail loudly: silently optimizing against the generic geometric+logistic
    surface would misrepresent the model's response."""

    class UnmappedAdstock:
        l_max = 4

    class UnmappedSaturation:
        pass

    metadata = FakeMetadata()
    modeling = FakeModeling()
    modeling.model = SimpleNamespace(
        **{
            **vars(modeling.model),
            "adstock": UnmappedAdstock(),
            "saturation": UnmappedSaturation(),
            "fit_result": SimpleNamespace(data_vars={}),
            "get_scales_as_xarray": dict,
        }
    )
    service = DecisionService(metadata, modeling)
    request = FlightingOptimizationInput(
        model_id="mmm_1",
        total_budget=1000.0,
        planning_weeks=4,
        channel_constraints=[],
    )

    with pytest.raises(DomainError) as exc_info:
        service.optimize_flighting(request)

    assert exc_info.value.code == "INPUT_INVALID"
    assert "transform" in str(exc_info.value.message).lower()
