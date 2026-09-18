"""Temporal profiling: calendar frequency, gaps, and continuity."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.profile import TemporalProfile


def find_candidate_date_column(df: pd.DataFrame) -> str | None:
    """Find the most plausible date column in the dataframe."""
    # First priority: column names containing date keywords
    date_keywords = ("date", "week", "day", "time", "period", "timestamp", "ds")
    for col in df.columns:
        cl = col.lower()
        if any(k == cl or cl.startswith(k + "_") or cl.endswith("_" + k) for k in date_keywords):
            return col

    # Second priority: any column with datetime dtype
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col

    # Third priority: general substring match
    for col in df.columns:
        if any(k in col.lower() for k in date_keywords):
            return col

    return None


def detect_temporal_profile(df: pd.DataFrame, date_column: str | None = None) -> TemporalProfile:
    """Extract temporal features, frequency, gaps, and missing periods."""
    date_col = date_column or find_candidate_date_column(df)
    if not date_col or date_col not in df.columns:
        return TemporalProfile()

    parsed = pd.to_datetime(df[date_col], errors="coerce")
    valid_dates = parsed.dropna()
    dup_count = int(parsed.duplicated().sum())

    if len(valid_dates) == 0:
        return TemporalProfile(date_column=date_col, duplicate_dates_count=dup_count, is_continuous=False)

    sorted_dates = valid_dates.sort_values().drop_duplicates()
    start_date = sorted_dates.min().date().isoformat()
    end_date = sorted_dates.max().date().isoformat()
    observed_count = len(sorted_dates)

    if observed_count < 3:
        return TemporalProfile(
            date_column=date_col,
            frequency="irregular",
            start_date=start_date,
            end_date=end_date,
            observed_periods=observed_count,
            expected_periods=observed_count,
            duplicate_dates_count=dup_count,
            is_continuous=True,
        )

    deltas = sorted_dates.diff().dropna().dt.days
    median_days = float(deltas.median())

    if median_days <= 1.5:
        freq = "daily"
        step_days = 1
    elif median_days <= 8.5:
        freq = "weekly"
        step_days = round(median_days) if round(median_days) in (7, 6, 8) else 7
    elif median_days <= 35:
        freq = "monthly"
        step_days = round(median_days)
    else:
        freq = "irregular"
        step_days = None

    missing_periods: list[str] = []
    expected_count = observed_count
    is_continuous = True

    if freq in ("daily", "weekly"):
        expected_range = pd.date_range(
            sorted_dates.min(),
            sorted_dates.max(),
            freq=pd.Timedelta(days=step_days),
        )
        expected_count = len(expected_range)
        missing_set = expected_range.difference(sorted_dates)
        if len(missing_set) > 0:
            is_continuous = False
            missing_periods = [d.date().isoformat() for d in missing_set[:200]]

    return TemporalProfile(
        date_column=date_col,
        frequency=freq,
        start_date=start_date,
        end_date=end_date,
        observed_periods=observed_count,
        expected_periods=expected_count,
        missing_periods=missing_periods,
        duplicate_dates_count=dup_count,
        is_continuous=is_continuous,
        granularity_days_median=median_days,
    )
