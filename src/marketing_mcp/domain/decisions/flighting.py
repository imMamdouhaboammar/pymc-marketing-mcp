"""
Dynamic multi-period media flighting domain logic.

Handles weekly spend schedule construction, carryover-aware allocation,
net-profit computation, and extrapolation risk checks.

Phase 4 — v0.6.0
"""

from __future__ import annotations

import numpy as np


def apply_spend_pattern(
    channel_budget: float,
    planning_weeks: int,
    pattern: str,
) -> list[float]:
    """Distribute a channel budget over weeks according to a spend pattern.

    Args:
        channel_budget: Total budget for this channel over the horizon.
        planning_weeks: Number of weeks to distribute over.
        pattern: One of 'flat', 'frontloaded', 'backloaded', 'pulsed'.

    Returns:
        List of weekly spend amounts summing to channel_budget.
    """
    if planning_weeks < 1:
        return []

    if pattern == "flat":
        weights = np.ones(planning_weeks)

    elif pattern == "frontloaded":
        # Linear decay: week 1 gets highest weight, week N gets lowest
        weights = np.linspace(2.0, 0.5, planning_weeks)

    elif pattern == "backloaded":
        # Linear ramp: week 1 gets lowest weight, week N gets highest
        weights = np.linspace(0.5, 2.0, planning_weeks)

    elif pattern == "pulsed":
        # Alternate high/low every week (burst scheduling)
        weights = np.where(np.arange(planning_weeks) % 2 == 0, 2.0, 0.5)

    else:
        weights = np.ones(planning_weeks)

    weights = weights / weights.sum()
    weekly = (weights * channel_budget).tolist()

    # Ensure exact sum (floating-point correction on last week)
    actual_sum = sum(weekly)
    if abs(actual_sum - channel_budget) > 1e-6 and weekly:
        weekly[-1] += channel_budget - actual_sum

    return weekly


def build_weekly_schedule(
    channel_columns: list[str],
    total_budget: float,
    planning_weeks: int,
    channel_constraints: list[dict],
) -> dict[str, list[float]]:
    """Construct an initial weekly spend schedule from constraints and patterns.

    Budget is split equally across channels by default, then each channel's
    allocation is patterned according to its constraint pattern.

    Args:
        channel_columns: List of channel names.
        total_budget: Total budget to allocate.
        planning_weeks: Number of weeks.
        channel_constraints: List of constraint dicts with keys:
            channel, min_weekly, max_weekly, pattern.

    Returns:
        Dict mapping channel_name → list of weekly spend amounts.
    """
    n_channels = len(channel_columns)
    per_channel_budget = total_budget / max(1, n_channels)

    # Build constraint lookup
    constraint_map: dict[str, dict] = {}
    for c in channel_constraints:
        constraint_map[c["channel"]] = c

    schedule: dict[str, list[float]] = {}
    for ch in channel_columns:
        c = constraint_map.get(ch, {})
        pattern = c.get("pattern", "flat")
        weekly = apply_spend_pattern(per_channel_budget, planning_weeks, pattern)

        # Apply per-week min/max constraints (clip to bounds)
        min_w = c.get("min_weekly")
        max_w = c.get("max_weekly")
        if min_w is not None or max_w is not None:
            weekly = [
                float(
                    np.clip(
                        w,
                        min_w if min_w is not None else 0.0,
                        max_w if max_w is not None else float("inf"),
                    )
                )
                for w in weekly
            ]

        schedule[ch] = weekly

    return schedule


def compute_net_profit(
    total_response: float,
    total_spend: float,
    margin_pct: float,
) -> dict[str, float]:
    """Compute net profit from a response estimate.

    Args:
        total_response: Estimated total revenue/response over the horizon.
        total_spend: Total media spend over the horizon.
        margin_pct: Revenue margin fraction [0, 1].

    Returns:
        Dict with gross_revenue, spend, margin_revenue, net_profit, roas.
    """
    gross_revenue = float(total_response)
    margin_revenue = gross_revenue * float(margin_pct)
    net_profit = margin_revenue - float(total_spend)
    roas = gross_revenue / max(1.0, float(total_spend))

    return {
        "gross_revenue": round(gross_revenue, 2),
        "total_spend": round(float(total_spend), 2),
        "margin_pct": float(margin_pct),
        "margin_revenue": round(margin_revenue, 2),
        "net_profit": round(net_profit, 2),
        "roas": round(roas, 4),
        "is_profitable": net_profit > 0,
    }


def check_extrapolation_risk(
    weekly_schedule: dict[str, list[float]],
    historical_channel_p95: dict[str, float],
    multiplier: float = 1.5,
) -> list[dict]:
    """Identify weekly spends that exceed the historical extrapolation threshold.

    Args:
        weekly_schedule: Dict of channel → list of weekly spends.
        historical_channel_p95: Dict of channel → historical weekly p95 spend.
        multiplier: Risk threshold multiplier above p95.

    Returns:
        List of warning dicts for any at-risk weeks.
    """
    warnings = []
    for ch, weeks in weekly_schedule.items():
        p95 = historical_channel_p95.get(ch)
        if p95 is None or p95 <= 0:
            continue
        threshold = p95 * multiplier
        for week_idx, spend in enumerate(weeks):
            if spend > threshold:
                warnings.append(
                    {
                        "code": "EXTRAPOLATION_RISK",
                        "channel": ch,
                        "week": week_idx + 1,
                        "proposed_spend": round(spend, 2),
                        "historical_p95": round(p95, 2),
                        "threshold": round(threshold, 2),
                        "severity": "warning",
                    }
                )
    return warnings
