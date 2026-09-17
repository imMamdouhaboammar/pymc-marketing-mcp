"""Adversarial Harsh Regression Matrix Test Suite.

Verifies platform behavior against the 6 standardized harsh fixtures:
1. pymc_harsh_observed_daily_panel.csv (234 observed days out of 243 calendar days, tracking gaps, outliers)
2. pymc_harsh_continuous_zero_padded_panel.csv (243 continuous days, zero-padded gaps)
3. pymc_harsh_invalid_panel.csv (duplicate dates, negative spend, non-numeric strings)
4. pymc_harsh_collinear_panel.csv (collinear channels with correlation > 0.99)
5. pymc_harsh_clv_valid_fixture.csv (valid RFM customer transactions for BG/NBD)
6. pymc_harsh_clv_value_fixture.csv (valid customer monetary values for Gamma-Gamma)
"""

from pathlib import Path

import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.domain.datasets.validation import validate_mmm_dataset

FIXTURE_DIR = Path(__file__).parents[2] / "migration" / "baselines" / "golden_datasets"


@pytest.fixture
def app_instance(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path / "inbox",
        max_dataset_mb=10,
        auth_enabled=False,
    )
    return Application(settings)


def test_harsh_fixture_observed_daily_panel_detects_temporal_gaps():
    """Observed daily panel with 234 rows across 243 calendar days must emit MISSING_PERIODS."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_observed_daily_panel.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)
    assert len(df) == 234

    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok"],
        control_columns=[],
    )

    missing_findings = [f for f in findings if f.code == "MISSING_PERIODS"]
    assert len(missing_findings) == 1, "Expected MISSING_PERIODS warning for 9 calendar day gaps"
    evidence = missing_findings[0].evidence
    assert evidence["frequency"] == "daily"
    assert evidence["observed_periods"] == 234
    assert evidence["expected_periods"] == 243
    assert evidence["missing_count"] == 9
    assert missing_findings[0].severity == "warning"


def test_harsh_fixture_continuous_zero_padded_panel_passes_validation():
    """Continuous 243-day panel must pass with zero missing periods."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_continuous_zero_padded_panel.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)
    assert len(df) == 243

    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok"],
        control_columns=[],
    )

    missing_findings = [f for f in findings if f.code == "MISSING_PERIODS"]
    assert len(missing_findings) == 0, "Continuous zero-padded panel should have no missing period findings"


def test_harsh_fixture_invalid_panel_detects_all_structural_violations():
    """Invalid panel must flag duplicate periods, negative spend, and non-numeric values."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_invalid_panel.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)

    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google"],
        control_columns=[],
    )

    codes = {f.code for f in findings}
    assert "DUPLICATE_PERIOD" in codes
    assert "NEGATIVE_MEDIA" in codes
    # At least one finding must be an error
    assert any(f.severity == "error" for f in findings)


def test_harsh_fixture_collinear_panel_detects_high_channel_correlation():
    """Collinear panel (meta and facebook_ads corr > 0.99) must emit HIGH_CHANNEL_CORRELATION."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_collinear_panel.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)

    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "facebook_ads", "search"],
        control_columns=[],
    )

    corr_findings = [f for f in findings if f.code == "HIGH_CHANNEL_CORRELATION"]
    assert len(corr_findings) >= 1
    pair = corr_findings[0].evidence.get("channels", [])
    assert "meta" in pair and "facebook_ads" in pair


def test_harsh_fixture_clv_valid_rfm_contract():
    """Valid CLV RFM fixture must satisfy customer transaction invariants."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_clv_valid_fixture.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)
    assert len(df) == 100
    assert set(df.columns) == {"customer_id", "frequency", "recency", "T", "monetary_value"}

    # Validate mathematical invariants for BG/NBD
    assert (df["frequency"] >= 0).all()
    assert (df["recency"] >= 0).all()
    assert (df["T"] >= df["recency"]).all()
    assert (df["monetary_value"] >= 0).all()


def test_harsh_fixture_clv_value_repeat_spend_contract():
    """Valid CLV spend fixture must contain only customers with repeat transactions."""
    fixture_file = FIXTURE_DIR / "pymc_harsh_clv_value_fixture.csv"
    assert fixture_file.exists(), f"Missing fixture {fixture_file}"

    df = pd.read_csv(fixture_file)
    assert set(df.columns) == {"customer_id", "frequency", "monetary_value"}
    assert (df["frequency"] >= 1).all()
    assert (df["monetary_value"] > 0).all()


def test_app_e2e_register_and_validate_harsh_datasets(app_instance):
    """E2E test: register observed and continuous harsh datasets and verify temporal_summary."""
    obs_bytes = (FIXTURE_DIR / "pymc_harsh_observed_daily_panel.csv").read_bytes()
    reg_obs = app_instance.datasets.register_bytes(obs_bytes, filename="observed_daily.csv")

    val_obs = app_instance.datasets.validate(
        dataset_id=reg_obs.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok"],
        control_columns=[],
    )
    assert val_obs.temporal_summary is not None
    assert val_obs.temporal_summary["missing_period_count"] == 9
    assert val_obs.temporal_summary["observed_periods"] == 234
    assert val_obs.temporal_summary["expected_periods"] == 243

    cont_bytes = (FIXTURE_DIR / "pymc_harsh_continuous_zero_padded_panel.csv").read_bytes()
    reg_cont = app_instance.datasets.register_bytes(cont_bytes, filename="continuous_daily.csv")

    val_cont = app_instance.datasets.validate(
        dataset_id=reg_cont.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok"],
        control_columns=[],
    )
    assert val_cont.temporal_summary is not None
    assert val_cont.temporal_summary["missing_period_count"] == 0
    assert val_cont.temporal_summary["observed_periods"] == 243
    assert val_cont.temporal_summary["expected_periods"] == 243
