"""Tests for structural profiling capabilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def test_temporal_profiling_weekly_with_missing_periods():
    from marketing_mcp.intelligence.structural.dates import detect_temporal_profile

    # 10 weeks, but week 4 is missing
    dates = pd.date_range("2025-01-06", periods=5, freq="W-MON").tolist()
    dates.extend(pd.date_range("2025-02-17", periods=5, freq="W-MON").tolist())
    df = pd.DataFrame({"ds": dates, "y": range(len(dates))})

    temporal = detect_temporal_profile(df, date_column="ds")
    assert temporal.date_column == "ds"
    assert temporal.frequency == "weekly"
    assert temporal.observed_periods == 10
    assert temporal.expected_periods == 11
    assert len(temporal.missing_periods) == 1
    assert "2025-02-10" in temporal.missing_periods
    assert temporal.is_continuous is False


def test_missingness_profiling_contiguous_runs():
    from marketing_mcp.intelligence.structural.missingness import profile_missingness

    s = pd.Series([1.0, 2.0, np.nan, np.nan, np.nan, 3.0, np.nan, 4.0])
    detail = profile_missingness(s)
    assert detail.missing_count == 4
    assert detail.missing_percentage == 50.0
    assert detail.longest_contiguous_missing == 3


def test_numeric_profiling_zeros_negatives_and_outliers():
    from marketing_mcp.intelligence.structural.numeric import profile_numeric

    vals = [10.0] * 50 + [0.0] * 5 + [-5.0] + [5000.0]  # has zeros, negative, extreme outlier
    s = pd.Series(vals)
    dist = profile_numeric(s)
    assert dist is not None
    assert dist.zeros_count == 5
    assert dist.negatives_count == 1
    assert dist.outlier_candidate_count >= 1
    assert dist.min == -5.0
    assert dist.max == 5000.0


def test_structural_profiler_single_pass():
    from marketing_mcp.intelligence.structural.profiler import profile_structure

    df = pd.DataFrame({
        "event_date": pd.date_range("2025-01-01", periods=30, freq="D"),
        "channel": ["google", "meta", "tiktok"] * 10,
        "spend": [100.0, 200.0, 0.0] * 10,
        "revenue": [500.0 + i for i in range(30)],
    })

    profile = profile_structure(df)
    assert profile.rows == 30
    assert profile.columns == 4
    assert profile.duplicate_rows == 0
    assert profile.temporal.frequency == "daily"
    assert profile.temporal.is_continuous is True
    assert "spend" in profile.column_profiles
    assert profile.column_profiles["spend"].numeric.zeros_count == 10
    assert profile.column_profiles["channel"].categorical.cardinality == 3
