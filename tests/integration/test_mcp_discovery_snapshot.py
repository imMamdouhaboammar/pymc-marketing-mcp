"""Discovery snapshot: locks the exact MCP surface (Wave 3 Task 1).

Written BEFORE the server refactor so any accidental tool/resource drift
during the module split fails loudly. Tool names must also match the
capability inventory exactly (single source of truth).
"""

from __future__ import annotations

import asyncio

import pytest

from marketing_mcp.app import Application
from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server

# Characterization snapshot at pre-refactor head (commit 55d923a).
EXPECTED_TOOLS = frozenset(
    {
        "register_dataset",
        "inspect_dataset",
        "validate_dataset",
        "list_datasets",
        "fit_mmm",
        "get_model_status",
        "diagnose_mmm",
        "get_channel_contributions",
        "get_incremental_roas",
        "get_response_curves",
        "simulate_budget",
        "optimize_budget",
        "recommend_next_measurement",
        "cross_validate_mmm",
        "evaluate_prior_sensitivity",
        "calibrate_mmm",
        "compare_models",
        "archive_model",
        "get_posterior_plots",
        "fit_purchase_model",
        "fit_value_model",
        "predict_expected_purchases",
        "predict_probability_alive",
        "predict_expected_spend",
        "estimate_customer_lifetime_value",
        "fit_clv_model",
        "predict_customer_clv",
        "get_churn_risk_cohorts",
        "optimize_flighting",
        "select_best_model",
        "submit_fit_mmm_job",
        "submit_transform_ad_export_job",
        "submit_budget_optimization_job",
        "submit_flighting_optimization_job",
        "submit_cross_validate_mmm_job",
        "submit_prior_sensitivity_job",
        "get_job_status",
        "poll_job_progress",
        "recover_execution_state",
        "resume_job",
        "cancel_job",
        "list_jobs",
        "export_artifact_to_sandbox",
        "cleanup_server_storage",
        "record_agent_insight",
        "get_agent_insights",
        "transform_ad_export",
        "list_agentic_skills",
        "get_skill_guidance",
        "get_skill_workflow_map",
    }
)

EXPECTED_RESOURCE_TEMPLATES = frozenset(
    {
        "marketing://datasets/{dataset_id}",
        "marketing://models/{model_id}",
        "marketing://models/{model_id}/plots/{plot_type}",
        "marketing://models/{model_id}/diagnostics",
        "marketing://models/{model_id}/lineage",
        "marketing://clv/{model_id}",
        "marketing://skills/{skill_name}",
        "marketing://skills/{skill_name}/manifest",
    }
)

EXPECTED_STATIC_RESOURCES = frozenset(
    {
        "marketing://skills",
        "marketing://skills/tool-map",
        "marketing://skills/workflow-map",
        "marketing://skills/decision-gates",
        "marketing://skills/references/scientific-answer-contract",
        "marketing://skills/references/scientific-source-ledger",
    }
)


@pytest.fixture
def mcp(tmp_path):
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    return create_server(app)


def test_snapshot_tool_names_exact(mcp):
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


def test_snapshot_resource_templates_exact(mcp):
    templates = asyncio.run(mcp.list_resource_templates())
    uris = {t.uri_template for t in templates}
    assert uris == EXPECTED_RESOURCE_TEMPLATES


def test_discovered_tools_match_capability_inventory():
    # The registry covers tools, resource templates, and static resources:
    # together they must exactly equal the MCP discovery surface.
    inventory_names = {cap.name for cap in get_capability_inventory()}
    assert inventory_names == EXPECTED_TOOLS | EXPECTED_RESOURCE_TEMPLATES | EXPECTED_STATIC_RESOURCES, (
        "Capability inventory and MCP discovery surface have drifted"
    )
