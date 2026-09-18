"""Structural break and changepoint detection in marketing target series."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketing_mcp.intelligence.contracts.issues import (
    IntelligenceIssue,
    IssueCode,
    IssueSeverity,
)


def detect_structural_breaks(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    min_segment_size: int = 8,
) -> list[IntelligenceIssue]:
    """Test for significant regime shifts / structural breaks in the target series.

    Uses a binary segmentation approach evaluating variance shift and mean
    divergence across candidate split points. Emits STRUCTURAL_BREAK issue
    when a break exceeds the empirical threshold.
    """
    issues: list[IntelligenceIssue] = []
    if target_column not in df.columns or len(df) < (min_segment_size * 2):
        return issues

    s = pd.to_numeric(df[target_column], errors="coerce").dropna()
    if len(s) < (min_segment_size * 2):
        return issues

    n = len(s)
    vals = s.to_numpy(dtype=float)
    total_var = float(np.var(vals))
    if total_var < 1e-9:
        return issues

    t_vec = np.arange(n, dtype=float)
    # Fit baseline continuous linear trend
    p_baseline = np.polyfit(t_vec, vals, 1)
    trend_baseline = p_baseline[0] * t_vec + p_baseline[1]
    rss0 = float(np.sum((vals - trend_baseline) ** 2))

    if rss0 < 1e-9:
        return issues

    best_t = -1
    best_improv = 0.0

    for t in range(min_segment_size, n - min_segment_size):
        # Fit two separate segments
        p1 = np.polyfit(t_vec[:t], vals[:t], 1)
        p2 = np.polyfit(t_vec[t:], vals[t:], 1)
        res1 = vals[:t] - (p1[0] * t_vec[:t] + p1[1])
        res2 = vals[t:] - (p2[0] * t_vec[t:] + p2[1])
        rss1 = float(np.sum(res1 ** 2) + np.sum(res2 ** 2))

        improv = (rss0 - rss1) / rss0
        if improv > best_improv:
            best_improv = improv
            best_t = t

    # A genuine regime break explains at least 50% of the unexplained linear trend variance
    if best_improv >= 0.50 and best_t > 0:
        date_str = str(df.iloc[best_t][date_column]) if date_column in df.columns else f"index_{best_t}"
        mean_before = float(np.mean(vals[:best_t]))
        mean_after = float(np.mean(vals[best_t:]))
        pct_change = round(((mean_after - mean_before) / max(1e-6, abs(mean_before))) * 100, 1)

        evidence: dict[str, Any] = {
            "break_index": best_t,
            "break_date": date_str,
            "score": round(best_improv, 2),
            "mean_before": round(mean_before, 2),
            "mean_after": round(mean_after, 2),
            "percent_shift": pct_change,
        }

        issues.append(
            IntelligenceIssue(
                code=IssueCode.STRUCTURAL_BREAK,
                severity=IssueSeverity.WARNING,
                summary=(
                    f"Target '{target_column}' exhibits a structural regime break around "
                    f"'{date_str}' (mean shifted {pct_change:+.1f}%)."
                ),
                evidence=evidence,
                affected_columns=[target_column],
                affected_rows=n,
                why_it_matters=(
                    "A structural shift in baseline response (e.g. macro shock, pandemic, major pricing/product "
                    "re-platforming) invalidates static parameter assumptions in adstock and saturation."
                ),
                recommended_action=(
                    "Consider modeling a time-varying intercept (time_varying_intercept=True), adding an "
                    "intervention dummy indicator, or evaluating if pre-break data should be trimmed."
                ),
                blocking=False,
            )
        )

    return issues
