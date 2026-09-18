"""Tests for marketing domain intelligence: lifecycle, market structure, tracking quality."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.issues import IssueCode


def test_channel_lifecycle_detects_sparse_and_staggered():
    from marketing_mcp.intelligence.marketing.lifecycle import analyze_channel_lifecycles

    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    # ch1 active first 30 weeks only
    # ch2 active last 30 weeks only
    # ch3 active only 4 weeks total (sparse & short)
    ch1 = [100.0] * 30 + [0.0] * 30
    ch2 = [0.0] * 30 + [150.0] * 30
    ch3 = [0.0] * 56 + [50.0] * 4

    df = pd.DataFrame({
        "date": dates,
        "meta": ch1,
        "tiktok": ch2,
        "influencer": ch3,
    })

    result = analyze_channel_lifecycles(df, date_column="date", channel_columns=["meta", "tiktok", "influencer"])
    assert "meta" in result.channel_profiles
    assert "tiktok" in result.channel_profiles
    assert "influencer" in result.channel_profiles

    # Check influencer is flagged as sparse/short
    inf_prof = result.channel_profiles["influencer"]
    assert inf_prof.active_period_count == 4
    assert inf_prof.active_fraction < 0.10

    issue_codes = [issue.code for issue in result.issues]
    assert IssueCode.STAGGERED_CHANNEL_LIFECYCLE in issue_codes
    assert IssueCode.SPARSE_CHANNEL in issue_codes


def test_market_structure_recommends_hierarchical_or_warns_heterogeneity():
    from marketing_mcp.intelligence.marketing.market_structure import analyze_market_structure

    dates = pd.date_range("2025-01-06", periods=40, freq="W-MON").tolist() * 3
    markets = ["US"] * 40 + ["UK"] * 40 + ["DE"] * 40
    df = pd.DataFrame({
        "date": dates,
        "market": markets,
        "revenue": [1000.0] * 120,
        "spend": [100.0] * 120,
    })

    # When dims not passed, warns unmodeled market heterogeneity
    structure_undimmed = analyze_market_structure(df, date_column="date", dims=[])
    assert structure_undimmed.issue is not None
    assert structure_undimmed.issue.code == IssueCode.MARKET_HETEROGENEITY

    # When dims passed, recommends hierarchical/panel strategy
    structure_dimmed = analyze_market_structure(df, date_column="date", dims=["market"])
    assert structure_dimmed.recommended_strategy in ("hierarchical_panel", "separate_models")
    assert structure_dimmed.market_count == 3


def test_tracking_quality_detects_target_gap():
    from marketing_mcp.intelligence.marketing.tracking_quality import analyze_tracking_quality

    df = pd.DataFrame({
        "spend": [100.0] * 10,
        "revenue": [500.0] * 8 + [0.0, 0.0],  # 2 periods with spend > 0 but revenue == 0
    })

    quality = analyze_tracking_quality(df, target_column="revenue", channel_columns=["spend"])
    assert quality.zero_target_active_spend_count == 2
    assert quality.issue is not None
    assert quality.issue.code == IssueCode.POSSIBLE_TARGET_TRACKING_GAP
