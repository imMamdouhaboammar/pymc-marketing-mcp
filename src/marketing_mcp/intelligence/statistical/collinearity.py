"""Collinearity and co-moving media channel diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity


@dataclass
class CollinearityReport:
    max_correlation: float = 0.0
    highly_correlated_pairs: list[tuple[str, str, float]] = field(default_factory=list)
    condition_index: float = 1.0
    issues: list[IntelligenceIssue] = field(default_factory=list)


def assess_collinearity(df: pd.DataFrame, channel_columns: list[str], threshold: float = 0.90) -> CollinearityReport:
    """Calculates pairwise correlation and condition number across channels."""
    if len(channel_columns) < 2:
        return CollinearityReport()

    numeric_df = df[channel_columns].apply(pd.to_numeric, errors="coerce").fillna(0)
    corr = numeric_df.corr().abs()

    max_corr = 0.0
    pairs: list[tuple[str, str, float]] = []
    issues: list[IntelligenceIssue] = []

    for i, a in enumerate(channel_columns):
        for b in channel_columns[i + 1 :]:
            val = float(corr.loc[a, b]) if (a in corr.index and b in corr.columns and pd.notna(corr.loc[a, b])) else 0.0
            if val > max_corr:
                max_corr = val
            if val >= threshold:
                pairs.append((a, b, round(val, 4)))
                issues.append(
                    IntelligenceIssue(
                        code=IssueCode.HIGH_CHANNEL_COLLINEARITY,
                        severity=IssueSeverity.WARNING,
                        summary=f"Channels '{a}' and '{b}' move together strongly (correlation r={val:.3f})",
                        evidence={"channels": [a, b], "correlation": round(val, 4)},
                        affected_columns=[a, b],
                        why_it_matters="Strong collinearity between media channels creates posterior confounding and wide credible intervals",
                        recommended_action="Calibrate at least one channel with incrementality test priors or combine channels",
                        blocking=False,
                    )
                )

    # Calculate condition number of normalized spend matrix
    cond_num = 1.0
    try:
        matrix = numeric_df.values
        norms = np.linalg.norm(matrix, axis=0)
        norms[norms == 0] = 1.0
        normalized = matrix / norms
        singular_values = np.linalg.svd(normalized, compute_uv=False)
        if len(singular_values) and singular_values[-1] > 0:
            cond_num = float(singular_values[0] / singular_values[-1])
    except Exception:
        cond_num = 1.0

    return CollinearityReport(
        max_correlation=round(max_corr, 4),
        highly_correlated_pairs=pairs,
        condition_index=round(cond_num, 2),
        issues=issues,
    )
