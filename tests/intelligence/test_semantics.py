"""Tests for semantic role inference."""

from __future__ import annotations

import pandas as pd
import pytest
from marketing_mcp.intelligence.contracts.evidence import ConfidenceLevel
from marketing_mcp.intelligence.contracts.issues import IssueCode
from marketing_mcp.intelligence.contracts.semantics import SemanticRole


def test_channel_inference_detects_channels_and_rejects_misleading_names():
    from marketing_mcp.intelligence.semantics.channels import infer_channel_column
    from marketing_mcp.intelligence.structural.profiler import profile_structure

    df = pd.DataFrame({
        "google_spend": [100.0, 150.0, 200.0] * 10,
        "meta_cost": [50.0, 75.0, 100.0] * 10,
        "influencer_cost": [10.0, 20.0, 30.0] * 10,
        "radio_spend": [500.0, 500.0, 600.0] * 10,
        "google_score": [1.0, 2.0, 3.0] * 10,      # misleading non-channel
        "meta_flag": [0, 1, 0] * 10,               # misleading non-channel
        "facebook_users": [1000, 2000, 3000] * 10,  # misleading non-channel
    })
    prof = profile_structure(df)

    # Valid channels
    for col in ["google_spend", "meta_cost", "influencer_cost", "radio_spend"]:
        inferred = infer_channel_column(col, df[col], prof.column_profiles[col])
        assert inferred is not None, f"Expected {col} to be detected as channel"
        assert inferred.role == SemanticRole.MEDIA_CHANNEL
        assert inferred.confidence.level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    # Misleading non-channels must NOT be inferred as media spend channels
    for col in ["google_score", "meta_flag", "facebook_users"]:
        inferred = infer_channel_column(col, df[col], prof.column_profiles[col])
        assert inferred is None or inferred.role != SemanticRole.MEDIA_CHANNEL, f"{col} should not be media channel"


def test_target_inference_flags_attributed_revenue():
    from marketing_mcp.intelligence.semantics.targets import infer_target_column
    from marketing_mcp.intelligence.structural.profiler import profile_structure

    df = pd.DataFrame({
        "total_revenue": [10000.0 + i * 100 for i in range(30)],
        "meta_attributed_revenue": [2000.0 + i * 50 for i in range(30)],
    })
    prof = profile_structure(df)

    # Independent revenue
    target_clean = infer_target_column("total_revenue", df["total_revenue"], prof.column_profiles["total_revenue"])
    assert target_clean is not None
    assert target_clean.role == SemanticRole.TARGET
    assert "ATTRIBUTED_REVENUE_TARGET" not in [s.signal_name for s in target_clean.confidence.evidence]

    # Attributed revenue
    target_attr = infer_target_column("meta_attributed_revenue", df["meta_attributed_revenue"], prof.column_profiles["meta_attributed_revenue"])
    assert target_attr is not None
    assert target_attr.role == SemanticRole.TARGET
    assert any("attributed" in s.signal_name.lower() for s in target_attr.confidence.evidence)


def test_currency_inference_and_fx_consistency():
    from marketing_mcp.intelligence.semantics.currencies import infer_currencies, verify_fx_consistency

    df = pd.DataFrame({
        "spend_local": [1000.0, 2000.0, 3000.0],
        "fx_rate": [3.75, 3.75, 3.75],  # SAR to USD (local / fx ≈ usd)
        "spend_usd": [266.67, 533.33, 800.0],
    })
    currencies = infer_currencies(df)
    assert "USD" in currencies or "local" in currencies

    is_consistent, diff_pct = verify_fx_consistency(df, "spend_local", "spend_usd", "fx_rate")
    assert is_consistent is True
    assert diff_pct < 0.01


def test_objectives_detects_mixed_semantics_and_zero_revenue_awareness():
    from marketing_mcp.intelligence.semantics.objectives import analyze_campaign_objectives

    df = pd.DataFrame({
        "objective": ["Sales", "Sales", "Awareness", "Awareness"],
        "conversion_event": ["purchase", "purchase", "video_view", "video_view"],
        "conversions": [10, 15, 500, 700],
        "revenue": [1000.0, 1500.0, 0.0, 0.0],
    })

    analysis = analyze_campaign_objectives(df)
    assert analysis.has_mixed_objectives is True
    assert analysis.has_zero_revenue_awareness is True
    assert analysis.issue is not None
    assert analysis.issue.code == IssueCode.MIXED_CONVERSION_SEMANTICS


def test_user_overrides_take_absolute_precedence():
    from marketing_mcp.intelligence.semantics.roles import infer_all_column_roles
    from marketing_mcp.intelligence.structural.profiler import profile_structure

    df = pd.DataFrame({
        "custom_col_x": [10.0, 20.0, 30.0] * 10,
        "other_col_y": [100.0, 200.0, 300.0] * 10,
    })
    prof = profile_structure(df)
    overrides = {
        "custom_col_x": {"role": SemanticRole.TARGET, "semantic_type": "revenue"},
        "other_col_y": {"role": SemanticRole.MEDIA_CHANNEL, "semantic_type": "spend"},
    }

    inferred = infer_all_column_roles(df, prof, user_overrides=overrides)
    assert inferred["custom_col_x"].role == SemanticRole.TARGET
    assert inferred["custom_col_x"].user_overridden is True
    assert inferred["custom_col_x"].confidence.score == 1.0
    assert inferred["other_col_y"].role == SemanticRole.MEDIA_CHANNEL
    assert inferred["other_col_y"].user_overridden is True
