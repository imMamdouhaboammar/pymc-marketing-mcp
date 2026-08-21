import pytest
from pydantic import ValidationError

from marketing_mcp.schemas.models import BudgetOptimizationInput, FitMMMInput


def test_fit_schema_rejects_arbitrary_adstock_type():
    with pytest.raises(ValidationError):
        FitMMMInput(
            dataset_id="d1",
            date_column="date",
            target_column="revenue",
            channel_columns=["meta"],
            adstock={"type": "python_eval", "l_max": 8},
        )


def test_budget_constraints_reject_min_above_max():
    with pytest.raises(ValidationError):
        BudgetOptimizationInput(
            model_id="m1",
            budget=1000,
            planning_periods=8,
            constraints={"meta": {"min": 900, "max": 100}},
        )
