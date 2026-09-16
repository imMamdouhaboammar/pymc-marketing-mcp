from __future__ import annotations

import pandas as pd
import pytest

from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.scientific.datasets import (
    inspect_dataset_frame,
    summarize_dataset_frame,
    validate_dataset_frame,
)


@pytest.fixture
def synthetic_mmm_df() -> pd.DataFrame:
    df = generate_synthetic_mmm(n=104, seed=42)
    assert isinstance(df, pd.DataFrame)
    return df


def test_inspect_dataset_frame_pure(synthetic_mmm_df: pd.DataFrame):
    """Verifies inspection executes purely on a DataFrame with zero MCP or auth context."""
    inspection = inspect_dataset_frame(synthetic_mmm_df, dataset_id="test_pure_1")

    assert inspection.dataset_id == "test_pure_1"
    assert inspection.rows == 104
    assert inspection.frequency == "weekly"
    assert inspection.date_range["start"] is not None
    assert inspection.date_range["end"] is not None
    assert "revenue" in inspection.possible_targets
    assert "meta" in inspection.possible_channels
    assert "google" in inspection.possible_channels
    assert "discount" in inspection.possible_controls
    assert inspection.mmm_candidate is True
    assert len(inspection.missing_periods) == 0


def test_validate_dataset_frame_pure_valid_case(synthetic_mmm_df: pd.DataFrame):
    """Verifies that a valid MMM dataset passes validation with zero errors."""
    result = validate_dataset_frame(
        df=synthetic_mmm_df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
        dataset_id="test_valid_1",
    )

    assert result.dataset_id == "test_valid_1"
    assert result.valid_for_modeling is True
    error_findings = [f for f in result.findings if f.severity == "error"]
    assert len(error_findings) == 0


def test_validate_dataset_frame_detects_negative_media(synthetic_mmm_df: pd.DataFrame):
    """Verifies that negative spend triggers a fatal error finding."""
    corrupted_df = synthetic_mmm_df.copy()
    corrupted_df.loc[10, "meta"] = -500.0

    result = validate_dataset_frame(
        df=corrupted_df,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
    )

    assert result.valid_for_modeling is False
    error_codes = [f.code for f in result.findings if f.severity == "error"]
    assert "NEGATIVE_MEDIA" in error_codes


def test_validate_dataset_frame_detects_missing_columns(synthetic_mmm_df: pd.DataFrame):
    """Verifies that missing mapped columns trigger MISSING_COLUMNS error."""
    result = validate_dataset_frame(
        df=synthetic_mmm_df,
        date_column="date",
        target_column="revenue",
        channel_columns=["non_existent_channel"],
        control_columns=[],
    )

    assert result.valid_for_modeling is False
    error_codes = [f.code for f in result.findings if f.severity == "error"]
    assert "MISSING_COLUMNS" in error_codes


def test_summarize_dataset_frame_pure(synthetic_mmm_df: pd.DataFrame):
    """Verifies statistical summarization of dataset channels and targets."""
    summary = summarize_dataset_frame(
        df=synthetic_mmm_df,
        date_column="date",
        channel_columns=["meta", "google"],
        target_column="revenue",
    )

    assert summary.rows == 104
    assert summary.columns == len(synthetic_mmm_df.columns)
    assert summary.total_spend is not None
    assert summary.total_spend > 0
    assert "meta" in summary.channel_spend_shares
    assert "google" in summary.channel_spend_shares
    total_share = sum(summary.channel_spend_shares.values())
    assert pytest.approx(total_share, rel=1e-3) == 1.0

    meta_col = next(c for c in summary.column_summaries if c.name == "meta")
    assert meta_col.sparkline is not None
    assert len(meta_col.sparkline) > 0
