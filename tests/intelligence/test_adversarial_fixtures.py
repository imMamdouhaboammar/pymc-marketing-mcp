"""Comprehensive tests for Adversarial Fixtures A through L."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.intelligence.contracts.issues import IssueCode
from marketing_mcp.intelligence.contracts.semantics import SemanticRole
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    RiskLevel,
    SuitabilityVerdict,
)
from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine


@pytest.fixture
def engine():
    return MarketingDataIntelligenceEngine()


def test_fixture_a_clean_mmm(engine):
    """Fixture A: Clean MMM with date, revenue, google_spend, meta_spend."""
    dates = pd.date_range("2025-01-06", periods=65, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "revenue": [50000.0 + i * 200 + (i % 5) * 500 for i in range(65)],
        "google_spend": [2000.0 + (i % 3) * 200 for i in range(65)],
        "meta_spend": [1500.0 + (i % 4) * 150 for i in range(65)],
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_a")

    assert contract.target is not None
    assert contract.target.column == "revenue"
    assert len(contract.channels) == 2
    assert {c.column for c in contract.channels} == {"google_spend", "meta_spend"}
    assessment = contract.suitability[AnalysisType.MMM]
    assert assessment.verdict == SuitabilityVerdict.SUITABLE
    assert contract.modeling_contract is not None


def test_fixture_b_mixed_objectives(engine):
    """Fixture B: Mixed objectives (Sales, Traffic, Lead Gen, Awareness)."""
    dates = pd.date_range("2025-01-06", periods=30, freq="W-MON").tolist() * 4
    objectives = ["Sales"] * 30 + ["Traffic"] * 30 + ["Lead Generation"] * 30 + ["Awareness"] * 30
    conversions = [100] * 30 + [5000] * 30 + [250] * 30 + [0] * 30
    df = pd.DataFrame({
        "date": dates,
        "objective": objectives,
        "conversions": conversions,
        "revenue": [10000.0] * 30 + [0.0] * 30 + [2500.0] * 30 + [0.0] * 30,
        "spend": [1000.0] * 120,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_b")

    issue_codes = [iss.code for iss in contract.issues]
    assert IssueCode.MIXED_CONVERSION_SEMANTICS in issue_codes
    assert contract.suitability[AnalysisType.MMM].verdict in (
        SuitabilityVerdict.REQUIRES_TRANSFORMATION,
        SuitabilityVerdict.SUITABLE_WITH_CAUTION,
    )


def test_fixture_c_multiple_currencies(engine):
    """Fixture C: Multiple currencies (SAR, USD) with FX rates."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=40, freq="W-MON"),
        "spend_local": [3750.0] * 40,
        "usd_fx_rate": [3.75] * 40,
        "spend_usd": [1000.0] * 40,
        "revenue_usd": [5000.0] * 40,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_c")

    assert "USD" in contract.currencies
    assert "local" in contract.currencies or "SAR" in contract.currencies


def test_fixture_d_staggered_channels(engine):
    """Fixture D: Staggered channels where Channel A ends when Channel B starts."""
    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    # Channel A active first 30 weeks only; Channel B active last 30 weeks only
    meta = [500.0] * 30 + [0.0] * 30
    snap = [0.0] * 30 + [600.0] * 30
    df = pd.DataFrame({
        "date": dates,
        "revenue": [20000.0] * 60,
        "meta_spend": meta,
        "snapchat_spend": snap,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_d")

    issue_codes = [iss.code for iss in contract.issues]
    assert IssueCode.STAGGERED_CHANNEL_LIFECYCLE in issue_codes


def test_fixture_e_correlated_channels(engine):
    """Fixture E: Two channels always move together (r > 0.95)."""
    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    base = np.linspace(100, 1000, 60)
    df = pd.DataFrame({
        "date": dates,
        "revenue": [10000.0 + i * 50 for i in range(60)],
        "search_spend": base,
        "social_spend": base * 1.8 + np.random.normal(0, 0.01, 60),
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_e")

    issue_codes = [iss.code for iss in contract.issues]
    assert IssueCode.HIGH_CHANNEL_COLLINEARITY in issue_codes
    assert contract.suitability[AnalysisType.MMM].identifiability_risk is not None
    assert contract.suitability[AnalysisType.MMM].identifiability_risk.overall_risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_fixture_f_market_heterogeneity(engine):
    """Fixture F: Multi-market heterogeneous dataset without dims."""
    dates = pd.date_range("2025-01-06", periods=30, freq="W-MON").tolist() * 3
    df = pd.DataFrame({
        "date": dates,
        "country": ["USA"] * 30 + ["UK"] * 30 + ["Germany"] * 30,
        "revenue": [10000.0] * 90,
        "meta_spend": [1000.0] * 90,
        "google_spend": [1200.0] * 90,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_f", dims=[])

    issue_codes = [iss.code for iss in contract.issues]
    assert IssueCode.MARKET_HETEROGENEITY in issue_codes


def test_fixture_g_sparse_channel(engine):
    """Fixture G: Channel active only occasionally (< 15% of periods)."""
    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    sparse_media = [0.0] * 55 + [200.0] * 5
    df = pd.DataFrame({
        "date": dates,
        "revenue": [10000.0] * 60,
        "google_spend": [1000.0] * 60,
        "pinterest_spend": sparse_media,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_g")

    issue_codes = [iss.code for iss in contract.issues]
    assert IssueCode.SPARSE_CHANNEL in issue_codes


def test_fixture_h_misleading_field_names(engine):
    """Fixture H: Misleading field names (google_score, meta_flag, facebook_users)."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=30, freq="W-MON"),
        "revenue": [10000.0] * 30,
        "google_score": [95.0, 92.0, 88.0] * 10,
        "meta_flag": [1, 0, 1] * 10,
        "facebook_users": [50000, 52000, 51000] * 10,
        "actual_google_spend": [1500.0] * 30,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_h")

    channel_names = [c.column for c in contract.channels]
    assert "actual_google_spend" in channel_names
    assert "google_score" not in channel_names
    assert "meta_flag" not in channel_names
    assert "facebook_users" not in channel_names


def test_fixture_i_custom_channels(engine):
    """Fixture I: Custom channels (influencer_cost, radio_spend, affiliate_commission)."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=30, freq="W-MON"),
        "revenue": [10000.0] * 30,
        "influencer_cost": [500.0] * 30,
        "radio_spend": [1200.0] * 30,
        "affiliate_commission": [300.0] * 30,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_i")

    channel_names = [c.column for c in contract.channels]
    assert "influencer_cost" in channel_names
    assert "radio_spend" in channel_names
    assert "affiliate_commission" in channel_names


def test_fixture_j_platform_attributed_revenue(engine):
    """Fixture J: Platform-attributed revenue (meta_reported_revenue)."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=30, freq="W-MON"),
        "meta_reported_revenue": [3000.0 + i * 20 for i in range(30)],
        "meta_spend": [500.0] * 30,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_j")

    assert contract.target is not None
    assert contract.target.column == "meta_reported_revenue"
    assert any("attributed" in s.signal_name.lower() for s in contract.target.confidence.evidence)


def test_fixture_k_zero_revenue_awareness(engine):
    """Fixture K: Zero-revenue awareness campaigns understood as legitimate."""
    dates = pd.date_range("2025-01-06", periods=20, freq="W-MON").tolist() * 2
    df = pd.DataFrame({
        "date": dates,
        "objective": ["Sales"] * 20 + ["Awareness"] * 20,
        "revenue": [5000.0] * 20 + [0.0] * 20,
        "spend": [400.0] * 40,
    })
    contract = engine.analyze_dataset(df, dataset_id="fixture_k")

    obj_issue = next((iss for iss in contract.issues if iss.code == IssueCode.MIXED_CONVERSION_SEMANTICS), None)
    assert obj_issue is not None
    assert obj_issue.evidence.get("has_zero_revenue_awareness") is True


def test_fixture_l_explicit_user_override(engine):
    """Fixture L: Explicit user override makes specified column authoritative."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=30, freq="W-MON"),
        "col_a": [100.0] * 30,
        "col_b": [200.0] * 30,
    })
    overrides = {
        "col_a": {"role": SemanticRole.TARGET, "semantic_type": "revenue"},
        "col_b": {"role": SemanticRole.MEDIA_CHANNEL, "semantic_type": "spend"},
    }
    contract = engine.analyze_dataset(df, dataset_id="fixture_l", user_overrides=overrides)

    assert contract.target.column == "col_a"
    assert contract.target.user_overridden is True
    assert contract.target.confidence.score == 1.0
    assert len(contract.channels) == 1
    assert contract.channels[0].column == "col_b"
    assert contract.channels[0].user_overridden is True


def test_golden_fixture_observed_daily_panel(engine):
    """Test engine on canonical golden fixture: pymc_harsh_observed_daily_panel.csv."""
    path = Path(__file__).parents[3] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_observed_daily_panel.csv"
    if not path.exists():
        path = Path(__file__).parents[2] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_observed_daily_panel.csv"
    assert path.exists(), f"Golden fixture not found: {path}"
    df = pd.read_csv(path)
    contract = engine.analyze_dataset(df, dataset_id="golden_observed_daily")
    assert contract.target is not None
    assert contract.target.column == "revenue"
    assert set(c.column for c in contract.channels) == {"meta", "google", "tiktok"}
    assert contract.suitability[AnalysisType.MMM].verdict == SuitabilityVerdict.SUITABLE_WITH_CAUTION


def test_golden_fixture_collinear_panel(engine):
    """Test engine on canonical golden fixture: pymc_harsh_collinear_panel.csv."""
    path = Path(__file__).parents[3] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_collinear_panel.csv"
    if not path.exists():
        path = Path(__file__).parents[2] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_collinear_panel.csv"
    assert path.exists(), f"Golden fixture not found: {path}"
    df = pd.read_csv(path)
    contract = engine.analyze_dataset(df, dataset_id="golden_collinear")
    assert contract.target is not None
    assert contract.target.column == "revenue"
    assert any(iss.code == IssueCode.HIGH_CHANNEL_COLLINEARITY for iss in contract.issues)
    assert contract.suitability[AnalysisType.MMM].verdict == SuitabilityVerdict.SUITABLE_WITH_CAUTION


def test_golden_fixture_invalid_panel(engine):
    """Test engine on canonical golden fixture: pymc_harsh_invalid_panel.csv."""
    path = Path(__file__).parents[3] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_invalid_panel.csv"
    if not path.exists():
        path = Path(__file__).parents[2] / "migration" / "baselines" / "golden_datasets" / "pymc_harsh_invalid_panel.csv"
    assert path.exists(), f"Golden fixture not found: {path}"
    df = pd.read_csv(path)
    contract = engine.analyze_dataset(df, dataset_id="golden_invalid")
    assert contract.suitability[AnalysisType.MMM].verdict == SuitabilityVerdict.NOT_SUITABLE

