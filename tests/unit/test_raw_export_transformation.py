from __future__ import annotations

import pandas as pd
import pytest

from marketing_mcp.scientific.transformations import (
    AggregationSemantic,
    classify_metric_aggregation,
    generate_transformation_plan,
    transform_long_form_export,
)


def test_classify_metric_aggregation():
    """Verify that additive metrics are summed and ratio/rate metrics are NEVER summed."""
    assert classify_metric_aggregation("spend") == AggregationSemantic.SUM
    assert classify_metric_aggregation("cost") == AggregationSemantic.SUM
    assert classify_metric_aggregation("revenue") == AggregationSemantic.SUM
    assert classify_metric_aggregation("orders") == AggregationSemantic.SUM
    assert classify_metric_aggregation("conversions") == AggregationSemantic.SUM
    assert classify_metric_aggregation("link_clicks") == AggregationSemantic.SUM

    # Strict non-summation invariants
    assert classify_metric_aggregation("ctr") == AggregationSemantic.RATIO_RECOMPUTE
    assert classify_metric_aggregation("cpc") == AggregationSemantic.RATIO_RECOMPUTE
    assert classify_metric_aggregation("cpa") == AggregationSemantic.RATIO_RECOMPUTE
    assert classify_metric_aggregation("roas") == AggregationSemantic.RATIO_RECOMPUTE


def test_transform_long_form_export_pivot_and_aggregation():
    """Test full long-to-wide pivot, date continuity, and dimensional panel generation."""
    raw_data = [
        # Date, Market, Platform, Spend, Revenue, Impressions, Clicks, CTR
        {"date": "2026-01-01", "geo": "US", "platform": "Google Ads", "spend": 100.0, "revenue": 300.0, "impressions": 1000, "clicks": 50, "ctr": 0.05},
        {"date": "2026-01-01", "geo": "US", "platform": "TikTok Ads", "spend": 80.0, "revenue": 160.0, "impressions": 2000, "clicks": 40, "ctr": 0.02},
        {"date": "2026-01-01", "geo": "UK", "platform": "Google Ads", "spend": 50.0, "revenue": 150.0, "impressions": 500, "clicks": 25, "ctr": 0.05},
        # Date 2026-01-02 missing TikTok in US, UK missing entirely
        {"date": "2026-01-02", "geo": "US", "platform": "Google Ads", "spend": 120.0, "revenue": 360.0, "impressions": 1200, "clicks": 60, "ctr": 0.05},
        # Date 2026-01-03
        {"date": "2026-01-03", "geo": "US", "platform": "TikTok Ads", "spend": 90.0, "revenue": 180.0, "impressions": 2500, "clicks": 50, "ctr": 0.02},
        {"date": "2026-01-03", "geo": "UK", "platform": "Google Ads", "spend": 60.0, "revenue": 180.0, "impressions": 600, "clicks": 30, "ctr": 0.05},
    ]
    df_raw = pd.DataFrame(raw_data)

    plan = generate_transformation_plan(
        df_raw,
        date_column="date",
        channel_column="platform",
        spend_column="spend",
        target_columns=["revenue"],
        dimension_columns=["geo"],
        frequency="D",
    )

    assert "google_ads_spend" in plan.pivot_channels
    assert "tiktok_ads_spend" in plan.pivot_channels
    assert plan.aggregation_rules["spend"] == "sum"
    assert plan.aggregation_rules["revenue"] == "sum"
    assert plan.aggregation_rules["ctr"] == "recompute_or_drop"

    transformed_df, provenance = transform_long_form_export(df_raw, plan)

    # 1. Check pivoted columns exist
    assert "google_ads_spend" in transformed_df.columns
    assert "tiktok_ads_spend" in transformed_df.columns
    assert "revenue" in transformed_df.columns
    assert "geo" in transformed_df.columns
    assert "date" in transformed_df.columns

    # 2. Check CTR is NOT summed (summing 0.05 + 0.02 would be 0.07, which is mathematical nonsense)
    if "ctr" in transformed_df.columns:
        # If recomputed: clicks / impressions = (50 + 40) / (1000 + 2000) = 90 / 3000 = 0.03
        row_us_day1 = transformed_df[(transformed_df["date"] == "2026-01-01") & (transformed_df["geo"] == "US")].iloc[0]
        assert row_us_day1["ctr"] == pytest.approx(0.03, abs=1e-3)

    # 3. Check zero-fill on missing channel spend
    row_us_day2 = transformed_df[(transformed_df["date"] == "2026-01-02") & (transformed_df["geo"] == "US")].iloc[0]
    assert row_us_day2["google_ads_spend"] == 120.0
    assert row_us_day2["tiktok_ads_spend"] == 0.0  # Safely filled with 0

    # 4. Check provenance metadata and financial reconciliation
    assert provenance.rows_before == len(df_raw)
    assert provenance.rows_after == len(transformed_df)
    assert len(provenance.channel_columns_created) == 2
    assert provenance.source_fingerprint is not None
    assert provenance.transformed_fingerprint is not None
    assert provenance.spend_reconciled is True
    assert provenance.spend_before == pytest.approx(500.0)
    assert provenance.spend_after == pytest.approx(500.0)
    assert provenance.spend_delta == pytest.approx(0.0, abs=1e-4)
