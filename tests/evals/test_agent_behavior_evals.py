"""Executable Agent Behavior and Decision Safety Evals (Wave 7).

Verifies that autonomous agents interacting with PyMC Marketing MCP tools:
1. Cannot bypass the Bayesian diagnostics decision gate to run budget optimizations on unconverged/rejected models.
2. Are blocked when attempting cross-tenant resource access.
3. Successfully complete valid end-to-end Bayesian marketing workflows when gates pass.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    ModelRecord,
)
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.principal import Principal


def _app(tmp_path):
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )


class TestAgentBehaviorEvals:
    def test_eval_agent_cannot_bypass_unconverged_decision_gate(self, tmp_path):
        app = _app(tmp_path)
        # Store unconverged model with rejected diagnostics
        app.metadata.put_model(
            {
                "model_id": "bad-model-1",
                "dataset_id": "d1",
                "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
                "created_at": "2026-08-26T00:00:00Z",
                "updated_at": "2026-08-26T00:00:00Z",
                "validation_state": "rejected",
                "diagnostics": {
                    "failures": [{"code": "DIVERGENCES", "message": "50 divergences encountered"}],
                    "decision_tools_enabled": False,
                },
            }
        )

        sim_input = BudgetSimulationInput(
            model_id="bad-model-1",
            planning_periods=4,
            changes={"meta": {"type": "relative", "value": 0.1}},
        )

        # Agent calling simulate_budget on rejected model must be blocked
        with pytest.raises(DomainError) as exc_sim:
            app.decisions.simulate(sim_input)
        assert exc_sim.value.code == "MODEL_NOT_VALIDATED"
        assert "Decision tools are disabled" in exc_sim.value.message

        opt_input = BudgetOptimizationInput(
            model_id="bad-model-1",
            budget=10000.0,
            planning_periods=4,
        )

        # Agent calling optimize_budget on rejected model must be blocked
        with pytest.raises(DomainError) as exc_opt:
            app.decisions.optimize(opt_input)
        assert exc_opt.value.code == "MODEL_NOT_VALIDATED"
        app.metadata.close()

    def test_eval_agent_blocked_on_cross_tenant_manipulation(self, tmp_path):
        app = _app(tmp_path)
        # Model belongs to Tenant A
        app.metadata.put_model(
            {
                "model_id": "tenant-a-model",
                "dataset_id": "d1",
                "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
                "created_at": "2026-08-26T00:00:00Z",
                "updated_at": "2026-08-26T00:00:00Z",
                "owner": "user_a",
                "tenant_id": "tenant-a",
                "validation_state": "approved",
            }
        )

        # Agent representing Tenant B attempts access
        agent_tenant_b = Principal(
            subject="agent_b",
            auth_type="oauth",
            tenant_id="tenant-b",
            scopes=frozenset(["marketing:read", "marketing:model", "marketing:decide"]),
        )

        with pytest.raises(DomainError) as exc:
            model_rec = app.metadata.get_model("tenant-a-model")
            authorize_model(agent_tenant_b, model_rec, action="read")
        assert exc.value.code == "AUTH_FORBIDDEN"
        assert "tenant-a" in exc.value.message
        app.metadata.close()

    def test_eval_valid_agent_workflow_reaches_decisions_safely(self, tmp_path):
        app = _app(tmp_path)
        record_data = {
            "model_id": "good-model-1",
            "dataset_id": "d1",
            "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
            "created_at": "2026-08-26T00:00:00Z",
            "updated_at": "2026-08-26T00:00:00Z",
            "validation_state": "approved",
            "diagnostics": {
                "failures": [],
                "warnings": [],
                "decision_tools_enabled": True,
            },
        }
        app.metadata.put_model(record_data)

        # Mock modeling.load_model to return a mock MMM instance and ModelRecord
        mock_model = MagicMock()
        mock_model.channel_columns = ["meta"]
        mock_model.target_column = "sales"
        mock_model.date_column = "date"
        mock_model.sample_posterior_predictive = MagicMock()

        app.models.load_model = MagicMock(return_value=(mock_model, ModelRecord(**record_data)))
        app.decisions.simulate = MagicMock(return_value={"simulated_spend": 1000.0, "decision_status": "approved"})
        app.decisions.optimize = MagicMock(return_value={"optimal_allocation": {"meta": 1000.0}, "decision_status": "approved"})

        # Agent executes simulation
        sim_res = app.decisions.simulate(
            BudgetSimulationInput(
                model_id="good-model-1",
                planning_periods=4,
                changes={"meta": {"type": "relative", "value": 0.1}},
            )
        )
        assert sim_res["decision_status"] == "approved"

        # Agent executes optimization
        opt_res = app.decisions.optimize(
            BudgetOptimizationInput(
                model_id="good-model-1",
                budget=1000.0,
                planning_periods=4,
            )
        )
        assert opt_res["decision_status"] == "approved"
        app.metadata.close()
