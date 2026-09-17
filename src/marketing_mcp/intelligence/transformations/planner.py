"""Explainable transformation planning for marketing datasets."""

from __future__ import annotations

import pandas as pd
from marketing_mcp.intelligence.contracts.contract import TransformationPlan, TransformationStep


def build_transformation_plan(
    df: pd.DataFrame,
    date_column: str | None = None,
    platform_col: str | None = None,
    spend_col: str | None = None,
    market_col: str | None = None,
    target_col: str | None = None,
) -> TransformationPlan:
    """Generates proposed non-destructive transformation steps for downstream modeling."""
    steps: list[TransformationStep] = []
    explanations: list[str] = []

    # 1. Long-form platform unpivoting
    if platform_col and spend_col:
        steps.append(
            TransformationStep(
                operation="pivot_channels",
                reason=f"Raw dataset is long-form with channel names in '{platform_col}' and spend in '{spend_col}'. PyMC MMM requires wide media channels.",
                details={
                    "index": [date_column] if date_column else [],
                    "columns": platform_col,
                    "values": spend_col,
                },
            )
        )
        explanations.append(f"Pivot '{platform_col}' into distinct wide channel columns.")

    # 2. Campaign-level to date/market aggregation
    if df is not None and date_column:
        has_campaign_id = any(k in c.lower() for c in df.columns for k in ["campaign_id", "ad_id", "placement"])
        if has_campaign_id:
            steps.append(
                TransformationStep(
                    operation="aggregate_time_series",
                    reason="Raw dataset is campaign/ad-level. MMM requires macro time-series aggregation to avoid distorted noise.",
                    details={"group_by": [date_column] + ([market_col] if market_col else [])},
                )
            )
            explanations.append("Aggregate campaign rows by date and market.")

    requires_mutation = len(steps) > 0
    return TransformationPlan(
        requires_mutation=requires_mutation,
        proposed_steps=steps,
        human_explanation=" ".join(explanations) if explanations else "Dataset already matches required modeling shape.",
    )
