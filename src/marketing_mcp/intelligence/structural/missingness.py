"""Missingness profiling across series."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.profile import MissingnessDetail


def profile_missingness(series: pd.Series) -> MissingnessDetail:
    """Calculates null counts, percentage, and longest contiguous missing run."""
    total = len(series)
    if total == 0:
        return MissingnessDetail()

    is_null = series.isna()
    null_count = int(is_null.sum())
    pct = round((null_count / total) * 100.0, 2)

    if null_count == 0:
        return MissingnessDetail(missing_count=0, missing_percentage=0.0, longest_contiguous_missing=0)

    # Calculate longest contiguous run of nulls
    # Cumulative sum of non-nulls acts as group ID for contiguous null runs
    groups = (~is_null).cumsum()
    null_runs = is_null.groupby(groups).sum()
    longest = int(null_runs.max()) if len(null_runs) else 0

    # Check for systematic pattern (e.g. all missing at start, or periodic)
    systematic = False
    if longest >= 10 and (longest / max(1, null_count)) > 0.8:
        systematic = True

    return MissingnessDetail(
        missing_count=null_count,
        missing_percentage=pct,
        longest_contiguous_missing=longest,
        systematic_pattern=systematic,
    )
