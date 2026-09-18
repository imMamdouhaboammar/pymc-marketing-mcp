"""Tracking quality, outages, and target continuity diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity


@dataclass
class TrackingQualityReport:
    zero_target_active_spend_count: int = 0
    zero_target_active_spend_pct: float = 0.0
    tracking_discontinuities_detected: int = 0
    issue: IntelligenceIssue | None = None


def analyze_tracking_quality(
    df: pd.DataFrame,
    target_column: str,
    channel_columns: list[str],
) -> TrackingQualityReport:
    """Detects periods with positive media spend but zero target, and tracking outages."""
    total_periods = len(df)
    if total_periods == 0 or target_column not in df.columns or not channel_columns:
        return TrackingQualityReport()

    target = pd.to_numeric(df[target_column], errors="coerce").fillna(0)
    total_spend = pd.DataFrame({
        c: pd.to_numeric(df[c], errors="coerce").fillna(0)
        for c in channel_columns if c in df.columns
    }).sum(axis=1)

    gap_mask = (total_spend > 0) & (target == 0)
    gap_count = int(gap_mask.sum())
    gap_pct = round((gap_count / max(1, total_periods)) * 100.0, 2)

    issue = None
    if gap_count > 0:
        issue = IntelligenceIssue(
            code=IssueCode.POSSIBLE_TARGET_TRACKING_GAP,
            severity=IssueSeverity.WARNING,
            summary=f"Detected {gap_count} periods ({gap_pct}%) with active media spend but zero '{target_column}'",
            evidence={
                "target_column": target_column,
                "gap_count": gap_count,
                "gap_pct": gap_pct,
            },
            affected_columns=[target_column, *channel_columns],
            why_it_matters="Active ad spend with zero observed revenue suggests telemetry dropouts or delayed conversion attribution",
            recommended_action="Check for analytics tracking outages or seasonal business closures during those periods",
            blocking=False,
        )

    return TrackingQualityReport(
        zero_target_active_spend_count=gap_count,
        zero_target_active_spend_pct=gap_pct,
        issue=issue,
    )
