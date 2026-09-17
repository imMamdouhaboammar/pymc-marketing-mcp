"""Channel lifecycle timeline, zero-spend fraction, and overlap matrix."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity


@dataclass
class ChannelLifecycleProfile:
    channel: str
    first_active_date: str | None = None
    last_active_date: str | None = None
    active_period_count: int = 0
    total_periods: int = 0
    active_fraction: float = 0.0
    zero_spend_fraction: float = 0.0
    longest_inactive_gap: int = 0
    spend_min: float = 0.0
    spend_max: float = 0.0
    spend_mean: float = 0.0
    spend_quantiles: dict[str, float] = field(default_factory=dict)


@dataclass
class ChannelLifecycleReport:
    channel_profiles: dict[str, ChannelLifecycleProfile] = field(default_factory=dict)
    overlap_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    issues: list[IntelligenceIssue] = field(default_factory=list)


def analyze_channel_lifecycles(
    df: pd.DataFrame,
    date_column: str,
    channel_columns: list[str],
) -> ChannelLifecycleReport:
    """Profiles active periods, zero spend runs, and pairwise lifecycle overlap across media channels."""
    profiles: dict[str, ChannelLifecycleProfile] = {}
    issues: list[IntelligenceIssue] = []
    total_rows = len(df)
    if total_rows == 0 or not channel_columns:
        return ChannelLifecycleReport()

    dates = pd.to_datetime(df[date_column], errors="coerce") if date_column in df.columns else None
    active_masks: dict[str, pd.Series] = {}

    for ch in channel_columns:
        if ch not in df.columns:
            continue
        s = pd.to_numeric(df[ch], errors="coerce").fillna(0)
        mask = (s > 0)
        active_masks[ch] = mask
        active_count = int(mask.sum())
        active_frac = round(active_count / max(1, total_rows), 4)
        zero_frac = round(1.0 - active_frac, 4)

        # Longest inactive run
        zero_run = (~mask).astype(int)
        longest_gap = int(zero_run.groupby((zero_run == 0).cumsum()).sum().max()) if len(zero_run) else 0

        first_date = None
        last_date = None
        if dates is not None and active_count > 0:
            active_dates = dates[mask].dropna().sort_values()
            if len(active_dates):
                first_date = active_dates.iloc[0].date().isoformat()
                last_date = active_dates.iloc[-1].date().isoformat()

        valid_spends = s[mask]
        spend_min = float(valid_spends.min()) if len(valid_spends) else 0.0
        spend_max = float(valid_spends.max()) if len(valid_spends) else 0.0
        spend_mean = float(valid_spends.mean()) if len(valid_spends) else 0.0
        quantiles = {}
        if len(valid_spends):
            quantiles = {
                "q25": round(float(valid_spends.quantile(0.25)), 2),
                "q50": round(float(valid_spends.quantile(0.50)), 2),
                "q75": round(float(valid_spends.quantile(0.75)), 2),
            }

        profiles[ch] = ChannelLifecycleProfile(
            channel=ch,
            first_active_date=first_date,
            last_active_date=last_date,
            active_period_count=active_count,
            total_periods=total_rows,
            active_fraction=active_frac,
            zero_spend_fraction=zero_frac,
            longest_inactive_gap=longest_gap,
            spend_min=round(spend_min, 2),
            spend_max=round(spend_max, 2),
            spend_mean=round(spend_mean, 2),
            spend_quantiles=quantiles,
        )

        # Warnings on individual channel
        if active_count < 13 and total_rows >= 26:
            issues.append(
                IntelligenceIssue(
                    code=IssueCode.SPARSE_CHANNEL,
                    severity=IssueSeverity.WARNING,
                    summary=f"Channel '{ch}' has only {active_count} active periods in {total_rows} periods ({active_frac:.1%} active)",
                    evidence={"channel": ch, "active_periods": active_count, "total_periods": total_rows},
                    affected_columns=[ch],
                    why_it_matters="Sparse media spend impairs Bayesian posterior shrinkage and adstock estimation",
                    recommended_action="Pool sparse channel into related media category or use informative priors",
                    blocking=False,
                )
            )

    # Pairwise overlap analysis
    overlap_matrix: dict[str, dict[str, float]] = {c: {} for c in channel_columns if c in active_masks}
    channels_list = list(active_masks.keys())

    for i, a in enumerate(channels_list):
        for b in channels_list[i + 1 :]:
            mask_a = active_masks[a]
            mask_b = active_masks[b]
            inter = int((mask_a & mask_b).sum())
            union = int((mask_a | mask_b).sum())
            ratio = round(inter / max(1, union), 4)
            overlap_matrix[a][b] = ratio
            overlap_matrix[b][a] = ratio

            # Staggered lifecycles warning
            if profiles[a].active_period_count >= 5 and profiles[b].active_period_count >= 5 and ratio < 0.25:
                issues.append(
                    IntelligenceIssue(
                        code=IssueCode.STAGGERED_CHANNEL_LIFECYCLE,
                        severity=IssueSeverity.WARNING,
                        summary=f"Channels '{a}' and '{b}' have staggered active windows (overlap: {ratio:.1%})",
                        evidence={
                            "channels": [a, b],
                            "overlap_ratio": ratio,
                            "active_a": profiles[a].active_period_count,
                            "active_b": profiles[b].active_period_count,
                        },
                        affected_columns=[a, b],
                        why_it_matters="Temporal confounding prevents separating distinct channel decay from macroeconomic trends",
                        recommended_action="Align media flighting windows or calibrate with lift tests",
                        blocking=False,
                    )
                )

    return ChannelLifecycleReport(
        channel_profiles=profiles,
        overlap_matrix=overlap_matrix,
        issues=issues,
    )
