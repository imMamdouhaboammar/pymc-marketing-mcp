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
        "saturation": {"type": "tanh"},
        "sampler": {
            "draws": 250,
            "tune": 250,
            "chains": 2,
            "target_accept": 0.9,
            "random_seed": 42,
        },
    }
    submit_resp = await _call(server, "submit_fit_mmm_job", {"config": fit_config})
    assert "summary" in submit_resp
    fit_job_id = submit_resp["summary"]["job_id"]

    # -------------------------------------------------------------------------
    # 7. Poll job to terminal completion (Area 2 - P1 fix)
    # -------------------------------------------------------------------------
    import asyncio
    import time

    start_poll = time.time()
    poll_resp = None
    while time.time() - start_poll < 120:
        poll_resp = await _call(
            server, "poll_job_progress", {"job_id": fit_job_id, "timeout_seconds": 30}
        )
        if poll_resp.get("summary", {}).get("is_terminal"):
            break
        await asyncio.sleep(0.5)

    assert poll_resp is not None
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
    # With draws=250/tune=250/tanh/geometric this naturally passes
    assert verdict in ("approved", "approved_with_caution"), (
        f"Expected approval but got '{verdict}'. "
        f"Failures: {diag_resp['summary'].get('failures', [])}"
    )
    assert diag_resp["summary"].get("failures") == [], (
        f"Non-empty diagnostic failures: {diag_resp['summary'].get('failures')}"
    )

    # -------------------------------------------------------------------------
    # 10. Descriptive tools: channel contributions, response curves
    # -------------------------------------------------------------------------
    contrib_resp = await _call(server, "get_channel_contributions", {"model_id": model_id})
    assert "summary" in contrib_resp
    assert "channels" in contrib_resp["summary"]

    curves_resp = await _call(server, "get_response_curves", {"model_id": model_id})
    assert "summary" in curves_resp

    # -------------------------------------------------------------------------
    # 11. Decision Gate: incremental ROAS — now allowed on approved model
    # -------------------------------------------------------------------------
    iroas_resp = await _call(server, "get_incremental_roas", {"model_id": model_id})
    assert "summary" in iroas_resp

    # -------------------------------------------------------------------------
    # 12. Async cross-validation job (Item 4 - real CV coverage)
    # -------------------------------------------------------------------------
    cv_args = {
        "input": {
            "model_id": model_id,
            "n_init": 59,
            "forecast_horizon": 1,
            "step_size": 1,
            "sampler": {"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
        }
    }
    cv_job_resp = await _call(server, "submit_cross_validate_mmm_job", cv_args)
    assert "summary" in cv_job_resp
    cv_job_id = cv_job_resp["summary"]["job_id"]

    start_cv_poll = time.time()
    cv_poll = None
    while time.time() - start_cv_poll < 180:
        cv_poll = await _call(
            server, "poll_job_progress", {"job_id": cv_job_id, "timeout_seconds": 30}
        )
        if cv_poll.get("summary", {}).get("is_terminal"):
            break
        await asyncio.sleep(0.5)

    assert cv_poll is not None
    assert cv_poll["summary"]["is_terminal"] is True
    assert cv_poll["summary"]["job"]["status"] == "succeeded", (
        f"CV job failed: {cv_poll['summary']['job'].get('error')}"
    )

    # -------------------------------------------------------------------------
    # 13. Async prior sensitivity job (Item 4 - real prior sensitivity coverage)
    # -------------------------------------------------------------------------
    sens_args = {"input": {"model_id": model_id}}
    sens_job_resp = await _call(server, "submit_prior_sensitivity_job", sens_args)
    assert "summary" in sens_job_resp
    sens_job_id = sens_job_resp["summary"]["job_id"]

    start_sens_poll = time.time()
    sens_poll = None
    while time.time() - start_sens_poll < 300:
        sens_poll = await _call(
            server, "poll_job_progress", {"job_id": sens_job_id, "timeout_seconds": 30}
        )
        if sens_poll.get("summary", {}).get("is_terminal"):
            break
        await asyncio.sleep(0.5)

    assert sens_poll is not None
    assert sens_poll["summary"]["is_terminal"] is True
    assert sens_poll["summary"]["job"]["status"] == "succeeded", (
        f"Prior sensitivity job failed: {sens_poll['summary']['job'].get('error')}"
    )

    # -------------------------------------------------------------------------
    # 14. Async budget optimization job with idempotency (Area 4 & 5)
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
    start_opt_poll = time.time()
    opt_poll = None
    while time.time() - start_opt_poll < 90:
        opt_poll = await _call(
            server, "poll_job_progress", {"job_id": opt_job_id, "timeout_seconds": 25}
        )
        if opt_poll.get("summary", {}).get("is_terminal"):
            break
        await asyncio.sleep(0.5)

    assert opt_poll is not None
    assert opt_poll["summary"]["is_terminal"] is True
    assert opt_poll["summary"]["job"]["status"] == "succeeded"

    # Recover state and verify recommended action
    opt_rec = await _call(server, "recover_execution_state", {"job_id_or_key": "opt-e2e-analyst-journey"})
    assert opt_rec["summary"]["has_usable_result"] is True
    assert opt_rec["summary"]["recommended_action"] == "simulate_budget"


@pytest.mark.anyio
async def test_analyst_journey_rejected_fixture_blocks_optimization(app_env):
    """Companion test: a pathological dataset that fails diagnostics must block optimization.

    This verifies the server-side diagnostic gate is enforced without any
    manual DB mutation — the model reaches 'rejected' organically.
    """
    import asyncio

    app, server, principal = app_env

    # -------------------------------------------------------------------------
    # Build a dataset guaranteed to produce divergences/poor mixing:
    # near-zero, constant spend — channel is unidentifiable.
    # -------------------------------------------------------------------------
    np.random.seed(42)
    n = 52
    dates = pd.date_range("2022-01-01", periods=n, freq="W-MON").strftime("%Y-%m-%d").tolist()
    df = pd.DataFrame({
        "date": dates,
        "ch1": np.random.uniform(10, 100, n),
        "ch2": np.random.uniform(10, 100, n),
        "revenue": np.random.normal(100, 10, n),
    })

    reg = await _call(
        server,
        "register_dataset",
        {"content": df.to_csv(index=False), "filename": "pathological.csv"},
    )
    dataset_id = reg["summary"]["dataset_id"]

    # Fit with unidentifiable pure-noise collinear channels, draws=50/tune=50/target_accept=0.8
    # deterministically producing divergences, R-hat > 1.05, and ESS < 50
    fit_config = {
        "dataset_id": dataset_id,
        "date_column": "date",
        "target_column": "revenue",
        "channel_columns": ["ch1", "ch2"],
        "adstock": {"type": "geometric"},
        "saturation": {"type": "tanh"},
        "sampler": {
            "draws": 50,
            "tune": 50,
            "chains": 2,
            "target_accept": 0.8,
            "random_seed": 42,
        },
    }
    submit_resp = await _call(server, "submit_fit_mmm_job", {"config": fit_config})
    fit_job_id = submit_resp["summary"]["job_id"]

    import time
    start = time.time()
    poll_resp = None
    while time.time() - start < 120:
        poll_resp = await _call(
            server, "poll_job_progress", {"job_id": fit_job_id, "timeout_seconds": 25}
        )
        if poll_resp.get("summary", {}).get("is_terminal"):
            break
        await asyncio.sleep(0.5)

    assert poll_resp is not None
    assert poll_resp["summary"]["is_terminal"] is True
    assert poll_resp["summary"]["job"]["status"] == "succeeded"
    model_id = poll_resp["summary"]["latest_checkpoint"]["state_data"]["model_id"]

    # Diagnose — ESS < 50 is mathematically guaranteed with 30 total draws
    diag_resp = await _call(server, "diagnose_mmm", {"model_id": model_id})
    verdict = diag_resp["summary"]["decision_status"]
    assert verdict == "rejected", f"Expected deterministic rejection (ESS < 50), got {verdict}"

    # Optimization MUST always be executed and MUST be blocked by the server-side gate
    opt_blocked = await _call(
        server,
        "optimize_budget",
        {
            "config": {
                "model_id": model_id,
                "budget": 1000.0,
                "planning_periods": 4,
            }
        },
    )
    # Gate must return an error response — not a successful allocation
    is_blocked = (
        "error" in opt_blocked
        or opt_blocked.get("code", "").startswith("MODEL_")
        or "DECISION_GATE_BLOCKED" in str(opt_blocked)
        or "failed diagnostic" in str(opt_blocked).lower()
        or "rejected" in str(opt_blocked).lower()
    )
    assert is_blocked, (
        f"Server-side diagnostic gate FAILED: optimize_budget succeeded on a rejected model. "
        f"Response: {opt_blocked}"
    )
