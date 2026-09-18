import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset


def test_fixture_a_clean_single_market():
    """Fixture A: Clean single-market revenue MMM without confounding."""
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=60, freq="W-MON"),
        "revenue": [1000.0 + i * 10.0 for i in range(60)],
        "meta_spend": [200.0 + (i % 5) * 20.0 for i in range(60)],
        "google_spend": [150.0 + (i % 3) * 30.0 for i in range(60)],
    })
    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "google_spend"],
        control_columns=[],
        dims=[],
    )
    errors = [f for f in findings if f.severity == "error"]
    assert len(errors) == 0

def test_fixture_b_mixed_campaign_objectives():
    """Fixture B: Mixed campaign objectives (Awareness with 0 revenue mixed with Sales)."""
    dates = pd.date_range("2025-01-01", periods=60, freq="W-MON")
    df = pd.DataFrame({
        "date": list(dates) * 2,
        "objective": ["Sales"] * 60 + ["Awareness"] * 60,
        "revenue": [1000.0] * 60 + [0.0] * 60,
        "meta_spend": [200.0] * 60 + [150.0] * 60,
        "google_spend": [100.0] * 60 + [80.0] * 60,
    })
    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "google_spend"],
        control_columns=[],
        dims=[],
    )
    codes = [f.code for f in findings]
    assert "MIXED_CAMPAIGN_OBJECTIVES" in codes

def test_fixture_c_staggered_channel_lifecycles():
    """Fixture C: Staggered channel starts/stops creating temporal confounding."""
    dates = pd.date_range("2025-01-01", periods=60, freq="W-MON")
    # Channel A active first 30 weeks only; Channel B active last 30 weeks only
    meta = [200.0] * 30 + [0.0] * 30
    snapchat = [0.0] * 30 + [180.0] * 30
    df = pd.DataFrame({
        "date": dates,
        "revenue": [1000.0] * 60,
        "meta_spend": meta,
        "snapchat_spend": snapchat,
    })
    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "snapchat_spend"],
        control_columns=[],
        dims=[],
    )
    codes = [f.code for f in findings]
    assert "STAGGERED_CHANNEL_LIFECYCLES" in codes

def test_fixture_f_unmodeled_market_heterogeneity():
    """Fixture F: Dataset has market/country columns but dims was not supplied."""
    dates = pd.date_range("2025-01-01", periods=60, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "market": ["Canada", "Egypt", "Saudi Arabia", "UAE", "Qatar"] * 12,
        "revenue": [1000.0] * 60,
        "meta_spend": [200.0] * 60,
        "google_spend": [100.0] * 60,
    })
    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "google_spend"],
        control_columns=[],
        dims=[],
    )
    codes = [f.code for f in findings]
    assert "UNMODELED_MARKET_HETEROGENEITY" in codes
