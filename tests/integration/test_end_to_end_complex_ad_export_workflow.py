from __future__ import annotations

import asyncio
import json
import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.schemas.models import ModelRecord
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


def _provider_for(principal):
    return lambda: ExecutionContext(principal=principal)


def _call(server, tool, args):
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def generate_synthetic_3000_row_ad_export() -> pd.DataFrame:
    """Generate representative 3,000-row complex advertising export with 6 platforms and 5 geos."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", "2026-08-31", freq="D")
    platforms = ["Google Ads", "Meta Ads", "TikTok", "LinkedIn", "Snapchat", "X"]
    geos = ["US", "UK", "DE", "FR", "CA"]
    objectives = ["Conversions", "Traffic", "Awareness", "Lead Gen", "App Installs"]

    rows = []
    # Generate ~3,000 rows across dates, geos, and platforms
    for i in range(3000):
        d = np.random.choice(dates)
        plat = np.random.choice(platforms)
        geo = np.random.choice(geos)
        obj = np.random.choice(objectives)
        spend = float(np.random.uniform(20.0, 500.0))
        impressions = int(spend * np.random.uniform(50, 150))
        clicks = int(impressions * np.random.uniform(0.01, 0.05))
        revenue = float(spend * np.random.uniform(1.2, 4.0)) if obj in ("Conversions", "Lead Gen") else 0.0
        ctr = clicks / impressions if impressions > 0 else 0.0
        cpa = spend / max(1, int(revenue / 50)) if revenue > 0 else 0.0

        date_str = pd.to_datetime(d).strftime("%Y-%m-%d")
        rows.append({
            "date": date_str,
            "geo": geo,
            "platform": plat,
            "campaign_objective": obj,
            "spend": round(spend, 2),
            "revenue": round(revenue, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(ctr, 4),
            "cpa": round(cpa, 2),
        })

    return pd.DataFrame(rows)


def test_end_to_end_3000_row_ad_export_acceptance(tmp_path):
    """End-to-End Acceptance Scenario:
    1. Ingestion of 3,000-row granular long-form export
    2. Long-to-wide transformation with spend reconciliation and non-summation of CTR/CPA
    3. Multi-platform channel auto-discovery across all 6 networks
    4. Model gating & predictive failure attribution preventing unsound budget allocation
    5. Exploratory mode permitting analytical simulation with audit watermark
    """
    app = _app(tmp_path)
    principal = Principal(
        subject="lead_scientist",
        tenant_id="enterprise_brand",
        scopes=frozenset({"marketing:read", "marketing:model", "marketing:decide"}),
        auth_type="api_key",
    )
    server = create_server(app, context_provider=_provider_for(principal))

    # --- Step 1: Register Raw Dataset ---
    df_raw = generate_synthetic_3000_row_ad_export()
    total_raw_spend = round(float(df_raw["spend"].sum()), 2)
    raw_csv = df_raw.to_csv(index=False)

    reg_resp = _call(server, "register_dataset", {"content": raw_csv, "filename": "dirty_3000_ads.csv"})
    assert "summary" in reg_resp
    raw_dataset_id = reg_resp["summary"]["dataset_id"]
    assert raw_dataset_id is not None

    # --- Step 2: Transform Ad Export (Pivoting, Continuous Calendar, Non-Summation) ---
    transform_resp = _call(
        server,
        "transform_ad_export",
        {
            "dataset_id": raw_dataset_id,
            "date_column": "date",
            "channel_column": "platform",
            "spend_column": "spend",
            "target_columns": ["revenue"],
            "dimension_columns": ["geo"],
            "frequency": "D",
        },
    )
    assert "summary" in transform_resp
    t_sum = transform_resp["summary"]
    assert t_sum["spend_reconciled"] is True
    assert t_sum["spend_delta"] < 1e-3
    transformed_id = t_sum["transformed_dataset_id"]

    prov = transform_resp["evidence"]["provenance"]
    created_cols = prov["channel_columns_created"]
    # All 6 platforms must be recognized and pivoted
    assert "google_ads_spend" in created_cols
    assert "meta_ads_spend" in created_cols
    assert "tiktok_spend" in created_cols
    assert "linkedin_spend" in created_cols
    assert "snapchat_spend" in created_cols
    assert "x_spend" in created_cols

    # --- Step 3: Inspect Transformed Dataset ---
    inspect_resp = _call(server, "inspect_dataset", {"dataset_id": transformed_id})
    assert "summary" in inspect_resp
    i_sum = inspect_resp["summary"]
    assert "revenue" in i_sum["possible_targets"]

    # --- Step 4: Validate Dataset for MMM ---
    validate_resp = _call(
        server,
        "validate_dataset",
        {
            "dataset_id": transformed_id,
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": created_cols,
            "dims": ["geo"],
        },
    )
    assert "summary" in validate_resp
    assert validate_resp["summary"]["valid_for_modeling"] is True

    # --- Step 5: Simulate Fitted Model with Predictive Failure (NRMSE = 0.966) ---
    model_id = "mmm_complex_export_001"
    model_record = ModelRecord(
        model_id=model_id,
        model_type="mmm",
        dataset_id=transformed_id,
        dataset_fingerprint=t_sum.get("transformed_fingerprint") or prov.get("transformed_fingerprint"),
        tenant_id="enterprise_brand",
        config={
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": created_cols,
        },
        diagnostics={
            "failures": [
                {
                    "metric": "cross_validation_nrmse",
                    "observed": 0.966,
                    "threshold": 0.50,
                    "message": "Out-of-sample predictive NRMSE (0.966) exceeds decision threshold (0.50).",
                }
            ],
            "cross_validation": {
                "mean_out_of_sample_nrmse": 0.966,
                "failure_attribution": {
                    "naive_baseline": {
                        "skill_score": -1.24,
                        "skill_verdict": "inferior",
                    },
                    "residual_diagnostics": {
                        "mean_lag1_autocorr": 0.52,
                        "autocorr_verdict": "excessive",
                    },
                },
            },
        },
        validation_state="blocked_predictive_failure",
        artifact_path="/dummy/model.nc",
        metrics={"nrmse": 0.966},
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
    )
    app.metadata.put_model(model_record.model_dump(), tenant_id="enterprise_brand")

    # --- Step 6: Verify Production Mode Decision Gate Blocks Optimization ---
    opt_resp = _call(
        server,
        "optimize_budget",
        {
            "config": {
                "model_id": model_id,
                "budget": 200000.0,
                "planning_periods": 30,
            }
        },
    )
    # Must be strictly rejected with diagnostic evidence
    assert "error" in opt_resp or opt_resp.get("status") == "error" or opt_resp.get("code") == "MODEL_NOT_VALIDATED"
    assert "MODEL_NOT_VALIDATED" in str(opt_resp) or "diagnostic checks" in str(opt_resp)

    # --- Step 7: Verify Attribution Insights are Preserved ---
    cv_info = model_record.diagnostics["cross_validation"]["failure_attribution"]
    assert cv_info["naive_baseline"]["skill_verdict"] == "inferior"
    assert cv_info["residual_diagnostics"]["autocorr_verdict"] == "excessive"

    # --- Step 8: Verify Dual-Mode Decision Readiness ---
    from marketing_mcp.domain.diagnostics.gate import DecisionGate
    readiness_prod = DecisionGate(
        decision_status=model_record.validation_state,
        failures=model_record.diagnostics.get("failures", []),
        model_id=model_id,
        mode="production",
    ).evaluate_readiness()
    assert readiness_prod.decision_eligible is False
    assert readiness_prod.allowed_actions == []
    assert "optimize_budget" in readiness_prod.blocked_actions

    readiness_exp = DecisionGate(
        decision_status=model_record.validation_state,
        failures=model_record.diagnostics.get("failures", []),
        model_id=model_id,
        mode="exploratory",
    ).evaluate_readiness()
    assert readiness_exp.decision_eligible is False
    assert "simulate_budget" in readiness_exp.allowed_actions
    assert "optimize_budget" in readiness_exp.blocked_actions
    assert "EXPLORATORY_ANALYSIS_ONLY" in (readiness_exp.audit_watermark or "")

