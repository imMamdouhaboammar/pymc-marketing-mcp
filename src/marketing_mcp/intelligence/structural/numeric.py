"""Numeric distribution and outlier profiling."""

from __future__ import annotations

import numpy as np
import pandas as pd
from marketing_mcp.intelligence.contracts.profile import NumericDistribution


def profile_numeric(series: pd.Series) -> NumericDistribution | None:
    """Calculates non-copy descriptive statistics, zero count, negatives, and outliers."""
    numeric_s = pd.to_numeric(series, errors="coerce")
    valid = numeric_s.dropna()
    total_valid = len(valid)
    if total_valid == 0:
        return None

    non_finite = int(np.isneginf(valid).sum() + np.isposinf(valid).sum())
    finite_s = valid[np.isfinite(valid)]
    if len(finite_s) == 0:
        return NumericDistribution(non_finite_count=non_finite)

    min_val = float(finite_s.min())
    max_val = float(finite_s.max())
    mean_val = float(finite_s.mean())
    median_val = float(finite_s.median())
    std_val = float(finite_s.std()) if len(finite_s) > 1 else 0.0

    q25 = float(finite_s.quantile(0.25))
    q75 = float(finite_s.quantile(0.75))
    iqr = q75 - q25

    zeros_count = int((finite_s == 0).sum())
    zeros_fraction = round(zeros_count / len(series), 4) if len(series) > 0 else 0.0
    negatives_count = int((finite_s < 0).sum())

    outliers_count = 0
    if iqr > 0:
        lower_bound = q25 - 3.0 * iqr
        upper_bound = q75 + 3.0 * iqr
        outliers_count = int(((finite_s < lower_bound) | (finite_s > upper_bound)).sum())
    elif std_val > 0:
        # Fallback to 3-sigma if IQR is collapsed due to repeated values
        outliers_count = int((np.abs(finite_s - mean_val) > 3.0 * std_val).sum())

    return NumericDistribution(
        min=min_val,
        max=max_val,
        mean=round(mean_val, 4),
        median=round(median_val, 4),
        std=round(std_val, 4),
        q25=round(q25, 4),
        q75=round(q75, 4),
        iqr=round(iqr, 4),
        zeros_count=zeros_count,
        zeros_fraction=zeros_fraction,
        negatives_count=negatives_count,
        non_finite_count=non_finite,
        outlier_candidate_count=outliers_count,
    )
