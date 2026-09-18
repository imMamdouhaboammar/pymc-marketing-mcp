"""Control variable near-zero variance and collinearity preflight."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketing_mcp.intelligence.contracts.issues import (
    IntelligenceIssue,
    IssueCode,
    IssueSeverity,
)


def assess_control_variance(
    df: pd.DataFrame,
    control_columns: list[str],
    min_variance_threshold: float = 1e-6,
) -> list[IntelligenceIssue]:
    """Check candidate control variables for zero or near-zero variance.

    Identifies constants, near-constants, or columns with identical values
    across >98% of rows that would cause singular design matrices or
    excessive posterior parameter variance.
    """
    issues: list[IntelligenceIssue] = []

    for col in control_columns:
        if col not in df.columns:
            continue

        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) < 2:
            continue

        var = float(np.var(s.to_numpy(dtype=float)))
        unique_vals = s.nunique()
        dominant_freq = float(s.value_counts(normalize=True).iloc[0]) if unique_vals > 0 else 1.0

        is_near_zero = (var < min_variance_threshold) or (dominant_freq >= 0.98 and unique_vals <= 2)

        if is_near_zero:
            evidence: dict[str, Any] = {
                "column": col,
                "variance": round(var, 8),
                "unique_values_count": unique_vals,
                "dominant_value_frequency": round(dominant_freq, 4),
            }
            issues.append(
                IntelligenceIssue(
                    code=IssueCode.CONTROL_NEAR_ZERO_VARIANCE,
                    severity=IssueSeverity.WARNING,
                    summary=(
                        f"Control variable '{col}' has near-zero variance (std={np.sqrt(var):.2e}, "
                        f"{dominant_freq * 100:.1f}% constant)."
                    ),
                    evidence=evidence,
                    affected_columns=[col],
                    affected_rows=len(s),
                    why_it_matters=(
                        f"Near-constant control '{col}' becomes collinear with the model intercept (baseline). "
                        "This causes MCMC divergences, inflated posterior uncertainties, and poor sampling efficiency."
                    ),
                    recommended_action=(
                        f"Exclude '{col}' from control_columns unless you intend it as an explicit step/intervention dummy."
                    ),
                    blocking=False,
                )
            )

    return issues
