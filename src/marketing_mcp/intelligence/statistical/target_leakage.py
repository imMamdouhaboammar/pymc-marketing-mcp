"""Target leakage detection in marketing regression candidate controls and features."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from marketing_mcp.intelligence.contracts.issues import (
    IntelligenceIssue,
    IssueCode,
    IssueSeverity,
)


def check_target_leakage(
    df: pd.DataFrame,
    target_column: str,
    candidate_controls: list[str],
    candidate_channels: list[str] | None = None,
    correlation_threshold: float = 0.98,
) -> list[IntelligenceIssue]:
    """Identify candidate controls or features that leak the target outcome.

    Detects post-treatment variables, downstream conversion proxies, or contemporaneous
    totals (e.g. total_orders, raw_revenue) improperly proposed as exogenous controls.
    """
    issues: list[IntelligenceIssue] = []
    if target_column not in df.columns:
        return issues

    target_s = pd.to_numeric(df[target_column], errors="coerce")
    if target_s.isna().all() or target_s.std() < 1e-9:
        return issues

    # Semantic substring leakage flags
    leakage_keywords = {"total_sales", "total_orders", "total_conversions", "gross_revenue", "net_revenue"}
    target_lower = target_column.lower()

    for col in candidate_controls:
        if col not in df.columns or col == target_column:
            continue

        col_s = pd.to_numeric(df[col], errors="coerce")
        if col_s.isna().all() or col_s.std() < 1e-9:
            continue

        # Check correlation
        valid_mask = target_s.notna() & col_s.notna()
        if valid_mask.sum() < 6:
            continue

        r = float(np.corrcoef(target_s[valid_mask], col_s[valid_mask])[0, 1])

        # Check keyword semantics
        col_lower = col.lower()
        semantic_leak = any(kw in col_lower for kw in leakage_keywords if kw not in target_lower)

        is_leakage = (abs(r) >= correlation_threshold) or (semantic_leak and abs(r) >= 0.90)

        if is_leakage:
            evidence: dict[str, Any] = {
                "control_column": col,
                "target_column": target_column,
                "correlation": round(r, 4),
                "semantic_flag": semantic_leak,
            }
            issues.append(
                IntelligenceIssue(
                    code=IssueCode.TARGET_LEAKAGE,
                    severity=IssueSeverity.HIGH,
                    summary=(
                        f"Candidate control '{col}' exhibits near-perfect correlation (r={r:.3f}) "
                        f"with target '{target_column}', indicating probable target leakage."
                    ),
                    evidence=evidence,
                    affected_columns=[col, target_column],
                    affected_rows=int(valid_mask.sum()),
                    why_it_matters=(
                        f"Including '{col}' as a control absorbs true media treatment effect. The model will "
                        "attribute response variance to the control rather than marketing channels, causing severe "
                        "underestimation of channel ROAS."
                    ),
                    recommended_action=(
                        f"Exclude '{col}' from control_columns. If '{col}' is a post-treatment outcome or aggregate "
                        "volume metric, it must not be conditioned on in causal MMM."
                    ),
                    blocking=False,
                )
            )

    return issues
