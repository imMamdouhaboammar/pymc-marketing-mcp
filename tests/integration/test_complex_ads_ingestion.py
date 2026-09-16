"""Verification test for the user's complex_ads_sample_data.csv dataset.

Dataset specification from bug report:
- 3000 rows x 71 columns
- Per-ad, per-day granularity
- Platforms: TikTok Ads, LinkedIn Ads, Google Ads, X Ads, Snapchat Ads, Meta Ads
- Accounts: 8, across 5 countries (Saudi Arabia, Egypt, UAE, Canada, Qatar)
- Date range: 2026-01-01 to 2026-08-31 (234 unique dates)
- Target: revenue_usd
- Flags: TRACKING_MISMATCH, MISSING_TRACKING_SOURCE, MISSING_LANDING_PAGE, ZERO_CONVERSION
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import stdio_context_provider
from marketing_mcp.mcp.server import create_server


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


def generate_complex_ads_dataset() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    start_date = date(2026, 1, 1)
    end_date = date(2026, 8, 31)
    total_days = (end_date - start_date).days + 1  # 243 days

    all_dates = [start_date + timedelta(days=i) for i in range(total_days)]
    # Choose exactly 234 unique dates (simulate 9 days of gaps)
    random.seed(42)
    active_dates = sorted(random.sample(all_dates, 234))

    platforms = ["TikTok Ads", "LinkedIn Ads", "Google Ads", "X Ads", "Snapchat Ads", "Meta Ads"]
    countries = ["Saudi Arabia", "Egypt", "UAE", "Canada", "Qatar"]
    currencies = ["SAR", "EGP", "AED", "CAD", "QAR"]
    accounts = [f"acc_{i:02d}" for i in range(1, 9)]

    rows = []
    for row_id in range(3000):
        dt = random.choice(active_dates)
        platform = random.choice(platforms)
        account = random.choice(accounts)
        country_idx = random.randint(0, len(countries) - 1)
        country = countries[country_idx]
        currency = currencies[country_idx]

        # 24% zero revenue
        is_zero_revenue = rng.random() < 0.24
        spend_usd = round(float(rng.uniform(10.0, 500.0)), 2)
        revenue_usd = 0.0 if is_zero_revenue else round(spend_usd * float(rng.uniform(1.2, 4.5)), 2)
        impressions = int(spend_usd * rng.uniform(20, 100))
        clicks = int(impressions * rng.uniform(0.01, 0.05))

        # Data quality flags
        flag = "OK"
        if row_id < 39:
            flag = "TRACKING_MISMATCH"
        elif row_id < 39 + 32:
            flag = "MISSING_TRACKING_SOURCE"
        elif row_id < 39 + 32 + 25:
            flag = "MISSING_LANDING_PAGE"
        elif row_id < 39 + 32 + 25 + 16:
            flag = "ZERO_CONVERSION"

        row = {
            "date": dt.isoformat(),
            "platform": platform,
            "account_id": account,
            "country": country,
            "currency": currency,
            "ad_id": f"ad_{row_id:05d}",
            "campaign_id": f"camp_{row_id % 50:03d}",
            "ad_group_id": f"group_{row_id % 120:03d}",
            "quality_flag": flag,
            "spend_usd": spend_usd,
            "revenue_usd": revenue_usd,
            "impressions": impressions,
            "clicks": clicks,
            "conversions": 0 if is_zero_revenue else int(clicks * rng.uniform(0.05, 0.2)),
            "cpm": round((spend_usd / max(impressions, 1)) * 1000, 2),
            "cpc": round(spend_usd / max(clicks, 1), 2),
            "ctr": round((clicks / max(impressions, 1)) * 100, 2),
            "roas": round(revenue_usd / max(spend_usd, 1), 2),
        }

        # Platform-specific spend breakdown columns
        for p in ["meta_spend", "google_spend", "tiktok_spend", "linkedin_spend", "x_spend", "snapchat_spend"]:
            row[p] = spend_usd if p.startswith(platform.lower()[:4]) else 0.0

        # Fill remaining columns up to 71 columns with realistic metrics and metadata
        current_cols = len(row)
        for c_idx in range(current_cols, 71):
            row[f"metric_aux_{c_idx:02d}"] = round(float(rng.uniform(0, 100)), 2)

        rows.append(row)

    df = pd.DataFrame(rows)
    assert df.shape == (3000, 71), f"Expected shape (3000, 71), got {df.shape}"
    return df


def test_complex_ads_sample_data_registration_and_inspection(tmp_path):
    df = generate_complex_ads_dataset()
    csv_text = df.to_csv(index=False)

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path / "inbox",
        auth_enabled=False,
    )
    app = Application(settings)
    server = create_server(app, context_provider=stdio_context_provider)

    # 1. Register complex ads sample data directly via content parameter
    reg_res = _call(
        server,
        "register_dataset",
        {"content": csv_text, "filename": "complex_ads_sample_data.csv"},
    )
    assert "summary" in reg_res, f"Registration failed: {reg_res}"
    dataset_id = reg_res["summary"]["dataset_id"]
    assert reg_res["summary"]["rows"] == 3000
    assert reg_res["summary"]["format"] == "csv"

    # 2. Inspect dataset
    inspect_res = _call(server, "inspect_dataset", {"dataset_id": dataset_id})
    assert "summary" in inspect_res, f"Inspection failed: {inspect_res}"
    summary = inspect_res["summary"]
    assert summary["rows"] == 3000
    assert "revenue_usd" in summary["possible_targets"]
    assert any("spend" in ch for ch in summary["possible_channels"])
    assert summary["date_range"]["start"] is not None
    assert summary["date_range"]["end"] is not None
