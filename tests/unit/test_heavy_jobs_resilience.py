"""Tests for asynchronous heavy jobs (Area 4 & Area 5)."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


@pytest.fixture
def test_app(tmp_path):
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    return app


@pytest.fixture
def principal():
    return Principal(
        subject="analyst_test",
        tenant_id="tenant_resilience",
        scopes=frozenset({"marketing:read", "marketing:model", "marketing:decide"}),
        auth_type="api_key",
    )


@pytest.fixture
def mcp_server(test_app, principal):
    return create_server(test_app, context_provider=lambda: type("Context", (), {"principal": principal})())


def _call(server, tool: str, args: dict) -> dict:
    res = asyncio.run(server.call_tool(tool, args))
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


async def _acall(server, tool: str, args: dict) -> dict:
    res = await server.call_tool(tool, args)
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.mark.anyio
async def test_submit_transform_ad_export_job_idempotency_and_recovery(test_app, mcp_server, principal):
    # 1. Register a long-form dataset
    dates = pd.date_range("2026-01-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist() * 2
    channels = ["Google Ads"] * 60 + ["Meta Ads"] * 60
    spends = [100.0] * 120
    sales = [500.0] * 120
    df = pd.DataFrame({"date": dates, "channel": channels, "spend": spends, "revenue": sales})
    reg = test_app.datasets.register_bytes(
        df.to_csv(index=False).encode("utf-8"),
        format="csv",
        filename="raw_export.csv",
        principal=principal,
    )

    args = {
        "dataset_id": reg.dataset_id,
        "date_column": "date",
        "channel_column": "channel",
        "spend_column": "spend",
        "target_columns": ["revenue"],
        "idempotency_key": "transform-key-12345",
    }

    # Submit transform job
    resp1 = await _acall(mcp_server, "submit_transform_ad_export_job", args)
    assert "summary" in resp1
    job_id = resp1["summary"]["job_id"]
    assert resp1["summary"]["status"] in ("queued", "running", "succeeded")

    # Re-submitting with the same idempotency key must return the SAME job
    resp2 = await _acall(mcp_server, "submit_transform_ad_export_job", args)
    assert resp2["summary"]["job_id"] == job_id

    # Poll job to completion
    poll_resp = await _acall(mcp_server, "poll_job_progress", {"job_id": job_id, "timeout_seconds": 10})
    assert poll_resp["summary"]["is_terminal"] is True
    assert poll_resp["summary"]["job"]["status"] == "succeeded"

    # Recover state
    rec_resp = await _acall(mcp_server, "recover_execution_state", {"job_id_or_key": "transform-key-12345"})
    assert rec_resp["summary"]["has_usable_result"] is True
    assert rec_resp["summary"]["recommended_action"] == "inspect_dataset"


@pytest.mark.anyio
async def test_submit_budget_optimization_job_idempotency_and_recovery(test_app, mcp_server, principal):
    model_id = "test_model_opt"
    test_app.metadata.put_model({
        "model_id": model_id,
        "dataset_id": "test_ds",
        "validation_state": "approved",
        "diagnostics": {"status": "approved", "failures": [], "max_rhat": 1.01, "divergences": 0},
        "config": {},
        "owner": principal.subject,
        "tenant_id": principal.tenant_id,
    })

    mock_opt_result = {
        "recommended_allocation": {"tv": 1000.0, "meta": 2000.0},
        "baseline_allocation": {"tv": 1500.0, "meta": 1500.0},
        "optimizer_success": True,
        "channel_contributions": {"tv": 2000.0, "meta": 4000.0},
        "expected_response": 6000.0,
        "warnings": [],
        "identifiability_risks": [],
        "channel_confidence": {"tv": "high", "meta": "high"},
        "provenance": {"model_id": model_id},
    }

    with patch.object(test_app.decisions, "optimize", return_value=mock_opt_result):
        args = {
            "config": {
                "model_id": model_id,
                "budget": 3000.0,
                "planning_periods": 4,
            },
            "idempotency_key": "opt-key-9999",
        }

        resp1 = await _acall(mcp_server, "submit_budget_optimization_job", args)
        assert "summary" in resp1
        job_id = resp1["summary"]["job_id"]

        # Duplicate submit returns same job
        resp2 = await _acall(mcp_server, "submit_budget_optimization_job", args)
        assert resp2["summary"]["job_id"] == job_id

        # Poll
        poll_resp = await _acall(mcp_server, "poll_job_progress", {"job_id": job_id, "timeout_seconds": 10})
        assert poll_resp["summary"]["is_terminal"] is True
        assert poll_resp["summary"]["job"]["status"] == "succeeded"

        # Recover
        rec_resp = await _acall(mcp_server, "recover_execution_state", {"job_id_or_key": "opt-key-9999"})
        assert rec_resp["summary"]["has_usable_result"] is True
        assert rec_resp["summary"]["recommended_action"] == "simulate_budget"
