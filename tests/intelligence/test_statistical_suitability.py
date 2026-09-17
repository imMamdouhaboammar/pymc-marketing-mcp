"""Tests for statistical suitability and identifiability risk synthesis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from marketing_mcp.intelligence.contracts.issues import IssueCode
from marketing_mcp.intelligence.contracts.suitability import RiskLevel


def test_variance_detects_low_variation_channel():
    from marketing_mcp.intelligence.statistical.variance import assess_spend_variance

    # ch1 has healthy variance; ch2 is near-constant (100.0, 100.1, ...)
    df = pd.DataFrame({
        "ch1": [100.0, 150.0, 200.0, 80.0] * 10,
        "ch2": [100.0, 100.01, 100.0, 99.99] * 10,
    })

    report = assess_spend_variance(df, ["ch1", "ch2"])
    assert "ch1" in report.channel_cv
    assert "ch2" in report.channel_cv
    assert report.channel_cv["ch1"] > 0.15
    assert report.channel_cv["ch2"] < 0.01
    assert any(i.code == IssueCode.LOW_VARIATION_CHANNEL for i in report.issues)


def test_collinearity_detects_co_moving_channels():
    from marketing_mcp.intelligence.statistical.collinearity import assess_collinearity

    # ch1 and ch2 are almost perfectly correlated (r > 0.98)
    base = np.linspace(10, 100, 40)
    df = pd.DataFrame({
        "google_ads": base,
        "meta_ads": base * 1.5 + np.random.normal(0, 0.1, 40),
        "tiktok_ads": np.random.uniform(10, 50, 40),
    })

    report = assess_collinearity(df, ["google_ads", "meta_ads", "tiktok_ads"])
    assert report.max_correlation > 0.95
    assert any(i.code == IssueCode.HIGH_CHANNEL_COLLINEARITY for i in report.issues)


def test_identifiability_synthesizer_escalates_risk_and_suggests_mitigations():
    from marketing_mcp.intelligence.contracts.profile import TemporalProfile
    from marketing_mcp.intelligence.statistical.identifiability import evaluate_identifiability_risk

    # Dataset with both collinearity and short history (< 26 periods)
    temporal = TemporalProfile(observed_periods=24, is_continuous=True)
    collinearity_issues = [
        # high collinearity
        IssueCode.HIGH_CHANNEL_COLLINEARITY
    ]
    variance_issues = [
        # low variation
        IssueCode.LOW_VARIATION_CHANNEL
    ]

    risk = evaluate_identifiability_risk(
        temporal=temporal,
        collinearity_issues=collinearity_issues,
        variance_issues=variance_issues,
        staggered_issues=[],
        sparse_issues=[],
    )

    assert risk.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert len(risk.factors) >= 2
    assert len(risk.mitigations) >= 1
