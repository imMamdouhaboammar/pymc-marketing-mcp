"""Contract tests: every model-consuming tool has an EXPLICIT diagnostics-gate policy.

Policy matrix (documented rationale):

| Tool class | Tools                                   | not_diagnosed | rejected      | approved | approved_with_caution        |
|------------|------------------------------------------|---------------|---------------|----------|------------------------------|
| decision   | simulate, optimize, optimize_flighting,  | BLOCKED       | BLOCKED       | allowed  | allowed + warnings surfaced  |
|            | iroas                                    |               |               |          |                              |
| descriptive| contributions, response_curves           | allowed*      | allowed*      | allowed  | allowed + warnings surfaced  |

* Descriptive tools run on undiagnosed/rejected models so users can inspect the
  evidence behind a rejection; their outputs always carry `decision_gate` so
  rejected-model numbers can never be mistaken for decision-grade.

Rationale: iROAS directly drives budget reallocation, so it is decision-grade.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest
import xarray as xr

from marketing_mcp.adapters.mmm_config import GeometricAdstock, LogisticSaturation
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    BudgetChange,
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FlightingOptimizationInput,
)
from marketing_mcp.services.decision_service import DecisionService

CHANNELS = ["meta", "google"]


class FakeMetadata:
    def __init__(self):
        self.scenarios = []

    def put_scenario(self, payload):
        self.scenarios.append(payload)


class FakeAdapter:
    def channel_contributions(self, model):
        return {"channels": [{"channel": ch, "contribution_median": 10.0} for ch in CHANNELS]}

    def incremental_roas(self, model):
        return {"channels": [{"channel": ch, "iroas": 2.0} for ch in CHANNELS]}

    def response_curves(self, model):
        return {"curves": []}

    def optimize_budget(self, model, budget, planning_periods, constraints, cell_constraints):
        return {
            "optimizer_success": True,
            "recommended_allocation": {ch: budget / len(CHANNELS) for ch in CHANNELS},
        }

    def simulate_budget(self, model, baseline_allocation, scenario_allocation, planning_periods):
        return {
            "baseline_response": {"median": 100.0},
            "scenario_response": {"median": 105.0},
            "comparison": {"probability_scenario_beats_baseline": 0.7},
        }


def _fake_record(state: str):
    if state == "not_diagnosed":
        diagnostics = None
        validation_state = None
    elif state == "rejected":
        diagnostics = {
            "warnings": [],
            "failures": [{"code": "BAD_RHAT", "message": "r-hat too high"}],
        }
        validation_state = "rejected"
    elif state == "approved":
        diagnostics = {"warnings": [], "failures": []}
        validation_state = "approved"
    else:  # approved_with_caution
        diagnostics = {
            "warnings": [{"code": "LOW_EFFECTIVE_SAMPLE_SIZE", "message": "low ESS"}],
            "failures": [],
        }
        validation_state = "approved_with_caution"
    return SimpleNamespace(
        diagnostics=diagnostics,
        validation_state=validation_state,
        dataset_id="ds_1",
        config={
            "provenance": {"pymc-marketing": "1.0.0"},
            "date_column": "date",
            "target_column": "sales",
            "channel_columns": CHANNELS,
        },
    )


class FakeModeling:
    def __init__(self, record):
        self.record = record
        self.adapter = FakeAdapter()
        scale = xr.DataArray([100.0, 100.0], dims="channel", coords={"channel": CHANNELS})
        self.model = SimpleNamespace(
            date_column="date",
            channel_columns=CHANNELS,
            dims=(),
            X=pd.DataFrame(
                {
                    "date": pd.date_range("2025-01-06", periods=6, freq="W-MON"),
                    "meta": [10.0, 20.0, 30.0, 20.0, 25.0, 15.0],
                    "google": [30.0, 40.0, 50.0, 35.0, 45.0, 55.0],
                }
            ),
            adstock=GeometricAdstock(l_max=2),
            saturation=LogisticSaturation(),
            fit_result=xr.Dataset(
                {
                    # Posterior means sufficient for the official-transform evaluator.
                    "adstock_alpha": xr.DataArray(
                        [0.3] * len(CHANNELS), dims="channel", coords={"channel": CHANNELS}
                    ),
                    "saturation_lam": xr.DataArray(
                        [1.0] * len(CHANNELS), dims="channel", coords={"channel": CHANNELS}
                    ),
                    "saturation_beta": xr.DataArray(
                        [2.0] * len(CHANNELS), dims="channel", coords={"channel": CHANNELS}
                    ),
                }
            ),
            get_scales_as_xarray=lambda: {"channel_scale": scale},
        )

    def status(self, model_id):
        return self.record

    def load_model(self, model_id):
        return self.model, self.record

    def adapter_factory(self):
        return self.adapter


def _service(state: str):
    modeling = FakeModeling(_fake_record(state))
    return DecisionService(FakeMetadata(), modeling), modeling


MODEL_ID_INPUT_TOOLS = ["iroas"]
ALL_DECISION_TOOLS = ["iroas", "simulate", "optimize", "optimize_flighting"]
DESCRIPTIVE_TOOLS = ["contributions", "response_curves"]


@pytest.mark.parametrize("tool", ALL_DECISION_TOOLS)
def test_decision_tools_blocked_when_not_diagnosed(tool):
    service, _modeling = _service("not_diagnosed")
    with pytest.raises(DomainError) as exc_info:
        _call(service, tool)
    assert exc_info.value.code == "MODEL_NOT_DIAGNOSED"


@pytest.mark.parametrize("tool", ALL_DECISION_TOOLS)
def test_decision_tools_blocked_when_rejected(tool):
    service, _modeling = _service("rejected")
    with pytest.raises(DomainError) as exc_info:
        _call(service, tool)
    assert exc_info.value.code == "MODEL_NOT_VALIDATED"


@pytest.mark.parametrize("tool", ALL_DECISION_TOOLS)
def test_caution_surfaces_diagnostic_warnings_in_output(tool):
    service, _modeling = _service("approved_with_caution")
    result = _call(service, tool)
    gate = result["decision_gate"]
    assert gate["decision_status"] == "approved_with_caution"
    codes = [w.get("code") for w in gate["diagnostic_warnings"]]
    assert "LOW_EFFECTIVE_SAMPLE_SIZE" in codes


@pytest.mark.parametrize("tool", ALL_DECISION_TOOLS)
def test_approved_has_no_diagnostic_warning_block(tool):
    service, _modeling = _service("approved")
    result = _call(service, tool)
    gate = result["decision_gate"]
    assert gate["decision_status"] == "approved"
    assert not gate.get("diagnostic_warnings")


@pytest.mark.parametrize("tool", DESCRIPTIVE_TOOLS)
def test_descriptive_tools_run_on_rejected_models_but_label_it(tool):
    # Rationale: users may inspect WHY a model was rejected; the output is
    # explicitly labelled so it cannot masquerade as decision-grade.
    service, _modeling = _service("rejected")
    result = _call(service, tool)
    assert result["decision_gate"]["decision_status"] == "rejected"
    assert result["decision_gate"]["diagnostic_failures"]


def _call(service, tool):
    if tool == "iroas":
        return service.iroas("mmm_1")
    if tool == "contributions":
        return service.contributions("mmm_1")
    if tool == "response_curves":
        return service.response_curves("mmm_1")
    if tool == "simulate":
        return service.simulate(
            BudgetSimulationInput(
                model_id="mmm_1",
                planning_periods=4,
                changes={"meta": BudgetChange(type="relative", value=0.1)},
            )
        )
    if tool == "optimize":
        return service.optimize(
            BudgetOptimizationInput(model_id="mmm_1", budget=1000.0, planning_periods=4)
        )
    if tool == "optimize_flighting":
        return service.optimize_flighting(
            FlightingOptimizationInput(
                model_id="mmm_1",
                total_budget=1000.0,
                planning_weeks=4,
                channel_constraints=[],
            )
        )
    raise AssertionError(f"unknown tool {tool}")


def test_all_decision_tools_declared_gated_in_capability_registry():
    from marketing_mcp.capabilities import get_capability

    for tool_name in [
        "get_incremental_roas",
        "simulate_budget",
        "optimize_budget",
        "optimize_flighting",
    ]:
        cap = get_capability(tool_name)
        assert cap.decision_gate_required is True, (
            f"{tool_name} must be marked decision_gate_required=True in capability registry"
        )
