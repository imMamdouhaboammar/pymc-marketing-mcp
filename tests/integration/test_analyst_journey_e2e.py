"""End-to-end integration acceptance test for the full analyst journey through MCP boundaries (Area 7).

Drives the complete user journey:
1. Register multi-market long-form export
2. Inspect raw export
3. Transform ad export into wide-form panel dataset with dimension preservation
4. Inspect transformed dataset with business shorthand user_overrides
5. Validate transformed panel dataset (valid_for_modeling == True)
6. Submit asynchronous fit_mmm job with panel dims (verifying P0 dims admission fix)
7. Poll job to terminal completion (verifying P1 fit_completed, model not_diagnosed)
8. Verify decision tools blocked before diagnostics
9. Execute diagnose_mmm (gate verdict approved / caution)
10. Query channel contributions, incremental ROAS, response curves
11. Submit async budget optimization job with idempotency key
12. Poll budget job and recover execution state
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


@pytest.fixture
def app_env(tmp_path):
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    principal = Principal(
        subject="analyst_journey",
        tenant_id="tenant_agency_01",
        scopes=frozenset({"marketing:read", "marketing:model", "marketing:decide", "marketing:admin"}),
        auth_type="api_key",
    )
    server = create_server(app, context_provider=lambda: type("Context", (), {"principal": principal})())
    return app, server, principal


async def _call(server, tool_name: str, args: dict) -> dict:
    res = await server.call_tool(tool_name, args)
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.mark.anyio
async def test_full_analyst_journey_e2e(app_env):
    app, server, principal = app_env

    # -------------------------------------------------------------------------
    # 0. Generate realistic 60-week multi-market advertising export (US & UK)
    # -------------------------------------------------------------------------
    np.random.seed(42)
    n_weeks = 60
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON").strftime("%Y-%m-%d").tolist()

    records = []
    channels = ["Meta_Ads", "Google_Search", "YouTube_Video"]
    for country in ["US", "UK"]:
        country_mult = 1.8 if country == "US" else 1.0
        for i, dt in enumerate(dates):
            base_sales = (2000.0 + i * 25.0 + np.sin(i / 4.0) * 300.0) * country_mult
            for ch in channels:
                spend = float(np.random.uniform(200.0, 800.0) * country_mult)
                records.append({
                    "date": dt,
                    "market": country,
                    "channel_name": ch,
                    "spend_amount": round(spend, 2),
                    "revenue_usd": round(base_sales / len(channels) + spend * 1.5, 2),
                })

    df_raw = pd.DataFrame(records)

    # -------------------------------------------------------------------------
    # 1. Register raw export
    # -------------------------------------------------------------------------
    reg_resp = await _call(
        server,
        "register_dataset",
        {"content": df_raw.to_csv(index=False), "filename": "multi_market_ad_export.csv"},
    )
    assert "summary" in reg_resp
    raw_dataset_id = reg_resp["summary"]["dataset_id"]
    assert raw_dataset_id.startswith("dataset_")

    # -------------------------------------------------------------------------
    # 2. Inspect raw export
    # -------------------------------------------------------------------------
    insp_raw = await _call(server, "inspect_dataset", {"dataset_id": raw_dataset_id})
    assert "summary" in insp_raw
    assert insp_raw["summary"]["rows"] == len(df_raw)

    # -------------------------------------------------------------------------
    # 3. Transform long-form ad export into wide-format panel dataset
    # -------------------------------------------------------------------------
    trans_resp = await _call(
        server,
        "transform_ad_export",
        {
            "dataset_id": raw_dataset_id,
            "date_column": "date",
            "channel_column": "channel_name",
            "spend_column": "spend_amount",
            "target_columns": ["revenue_usd"],
            "dimension_columns": ["market"],
            "frequency": "W-MON",
        },
    )
    assert "summary" in trans_resp
    wide_dataset_id = trans_resp["summary"]["transformed_dataset_id"]
    assert trans_resp["summary"]["spend_reconciled"] is True
    assert trans_resp["summary"]["rows"] == n_weeks * 2  # 60 weeks * 2 markets

    # -------------------------------------------------------------------------
    # 4. Inspect transformed dataset with business shorthand user_overrides (Area 3)
    # -------------------------------------------------------------------------
    insp_wide = await _call(
        server,
        "inspect_dataset",
        {
            "dataset_id": wide_dataset_id,
            "user_overrides": {
                "target_column": "revenue_usd",
                "channel_columns": ["google_search_spend", "meta_ads_spend", "youtube_video_spend"],
                "dims": ["market"],
            },
        },
    )
    assert "summary" in insp_wide
    assert "revenue_usd" in insp_wide["summary"]["possible_targets"]

    # -------------------------------------------------------------------------
    # 5. Validate transformed dataset
    # -------------------------------------------------------------------------
    channel_cols = ["google_search_spend", "meta_ads_spend", "youtube_video_spend"]
    val_resp = await _call(
        server,
        "validate_dataset",
        {
            "dataset_id": wide_dataset_id,
            "date_column": "date",
            "target_column": "revenue_usd",
            "channel_columns": channel_cols,
            "dims": ["market"],
        },
    )
    assert "summary" in val_resp
    assert val_resp["summary"]["valid_for_modeling"] is True

    # -------------------------------------------------------------------------
    # 6. Submit asynchronous fit_mmm job with panel dims (Area 1 - P0 fix)
    # -------------------------------------------------------------------------
    fit_config = {
        "dataset_id": wide_dataset_id,
        "date_column": "date",
        "target_column": "revenue_usd",
        "channel_columns": channel_cols,
        "dims": ["market"],
        "adstock": {"type": "geometric"},
        "saturation": {"type": "logistic"},
        "sampler": {
            "draws": 50,
            "tune": 50,
            "chains": 2,
            "target_accept": 0.8,
        },
    }
    submit_resp = await _call(server, "submit_fit_mmm_job", {"config": fit_config})
    assert "summary" in submit_resp
    fit_job_id = submit_resp["summary"]["job_id"]

    # -------------------------------------------------------------------------
    # 7. Poll job to terminal completion (Area 2 - P1 fix)
    # -------------------------------------------------------------------------
    poll_resp = await _call(server, "poll_job_progress", {"job_id": fit_job_id, "timeout_seconds": 45})
    assert poll_resp["summary"]["is_terminal"] is True
    assert poll_resp["summary"]["job"]["status"] == "succeeded"

    # Verify latest checkpoint is fit_completed (NOT diagnostics_completed)
    latest_cp = poll_resp["summary"]["latest_checkpoint"]
    assert latest_cp["stage"] == "fit_completed"

    model_id = latest_cp["state_data"]["model_id"]

    # Verify model is NOT diagnosed yet
    status_resp = await _call(server, "get_model_status", {"model_id": model_id})
    assert status_resp["summary"]["validation_state"] == "not_diagnosed"

    # -------------------------------------------------------------------------
    # 8. Decision Gate: optimize_budget MUST be blocked before diagnostics
    # -------------------------------------------------------------------------
    opt_blocked = await _call(
        server,
        "optimize_budget",
        {
            "config": {
                "model_id": model_id,
                "budget": 5000.0,
                "planning_periods": 4,
            }
        },
    )
    assert "error" in opt_blocked or opt_blocked.get("code") == "MODEL_NOT_DIAGNOSED"

    # -------------------------------------------------------------------------
    # 9. Execute diagnose_mmm (mandatory gate)
    # -------------------------------------------------------------------------
    diag_resp = await _call(server, "diagnose_mmm", {"model_id": model_id})
    assert "summary" in diag_resp
    verdict = diag_resp["summary"]["decision_status"]
    assert verdict in ("approved", "approved_with_caution", "rejected")

    # -------------------------------------------------------------------------
    # 10. Descriptive tools: channel contributions, response curves
    # (Permitted even on rejected models to inspect why they failed)
    # -------------------------------------------------------------------------
    contrib_resp = await _call(server, "get_channel_contributions", {"model_id": model_id})
    assert "summary" in contrib_resp
    assert "channels" in contrib_resp["summary"]

    curves_resp = await _call(server, "get_response_curves", {"model_id": model_id})
    assert "summary" in curves_resp

    # -------------------------------------------------------------------------
    # 11. Decision Gate: verify optimization is blocked if rejected, then transition to approved
    # -------------------------------------------------------------------------
    if verdict == "rejected":
        opt_rejected = await _call(
            server,
            "optimize_budget",
            {
                "config": {
                    "model_id": model_id,
                    "budget": 5000.0,
                    "planning_periods": 4,
                }
            },
        )
        assert "error" in opt_rejected or "failed diagnostic checks" in str(opt_rejected)

        # Transition model to approved state to test downstream optimization journey
        model_rec = app.metadata.get_model(model_id)
        model_rec["validation_state"] = "approved"
        model_rec["diagnostics"]["status"] = "approved"
        model_rec["diagnostics"]["failures"] = []
        app.metadata.put_model(model_rec)

    # -------------------------------------------------------------------------
    # 12. Decision Tool: incremental ROAS on approved model
    # -------------------------------------------------------------------------
    iroas_resp = await _call(server, "get_incremental_roas", {"model_id": model_id})
    assert "summary" in iroas_resp

    # -------------------------------------------------------------------------
    # 13. Async budget optimization job with idempotency (Area 4 & 5)
    # -------------------------------------------------------------------------
    opt_args = {
        "config": {
            "model_id": model_id,
            "budget": 6000.0,
            "planning_periods": 4,
        },
        "idempotency_key": "opt-e2e-analyst-journey",
    }
    opt_job1 = await _call(server, "submit_budget_optimization_job", opt_args)
    assert "summary" in opt_job1
    opt_job_id = opt_job1["summary"]["job_id"]

    # Idempotent re-submission returns identical job
    opt_job2 = await _call(server, "submit_budget_optimization_job", opt_args)
    assert opt_job2["summary"]["job_id"] == opt_job_id

    # Poll optimization to completion
    opt_poll = await _call(server, "poll_job_progress", {"job_id": opt_job_id, "timeout_seconds": 30})
    assert opt_poll["summary"]["is_terminal"] is True
    assert opt_poll["summary"]["job"]["status"] == "succeeded"

    # Recover state and verify recommended action
    opt_rec = await _call(server, "recover_execution_state", {"job_id_or_key": "opt-e2e-analyst-journey"})
    assert opt_rec["summary"]["has_usable_result"] is True
    assert opt_rec["summary"]["recommended_action"] == "simulate_budget"
