"""Scientific long-form marketing export transformation engine.

Separates understanding and mutation:
1. Classifies aggregation semantics (additive vs ratio/rate vs identifier).
2. Generates an explicit, reviewable TransformationPlan.
3. Executes long-to-wide pivots, continuous calendar grids, and safe zero-fills.
4. Returns complete cryptographic provenance and audit lineage.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class AggregationSemantic(str, Enum):
    SUM = "sum"
    RATIO_RECOMPUTE = "ratio_recompute"
    MEAN = "mean"
    EXCLUDE = "exclude"


def classify_metric_aggregation(column_name: str) -> AggregationSemantic:
    """Classify column aggregation behavior with strict non-summation invariants for ratios."""
    cl = column_name.lower().strip()
    # Ratio / rate metrics must NEVER be summed
    if any(r in cl for r in ["ctr", "roas", "cpc", "cpa", "cpm", "cvr", "rate", "ratio", "percentage", "margin"]):
        return AggregationSemantic.RATIO_RECOMPUTE
    # Additive counts and monetary totals
    if any(a in cl for a in ["spend", "cost", "budget", "investment", "revenue", "sales", "order", "conversion", "lead", "click", "impression", "view"]):
        return AggregationSemantic.SUM
    return AggregationSemantic.SUM


@dataclass
class TransformationPlan:
    date_column: str
    channel_column: str
    spend_column: str
    target_columns: list[str]
    dimension_columns: list[str] = field(default_factory=list)
    frequency: str = "D"
    aggregation_rules: dict[str, str] = field(default_factory=dict)
    pivot_channels: list[str] = field(default_factory=list)
    reason: str = "Pivot ad-level granular transaction export to continuous MMM panel format"


@dataclass
class TransformationProvenance:
    rows_before: int
    rows_after: int
    inserted_periods: int
    excluded_rows: int
    channel_columns_created: list[str]
    source_fingerprint: str
    transformed_fingerprint: str
    aggregation_rules_applied: dict[str, str]
    spend_before: float = 0.0
    spend_after: float = 0.0
    spend_delta: float = 0.0
    spend_reconciled: bool = True
    warnings: list[str] = field(default_factory=list)


def _clean_token(name: str) -> str:
    cleaned = re.sub(r"[^\w]+", "_", name.lower().strip()).strip("_")
    return cleaned or "channel"


def generate_transformation_plan(
    df: pd.DataFrame,
    date_column: str,
    channel_column: str,
    spend_column: str,
    target_columns: list[str],
    dimension_columns: list[str] | None = None,
    frequency: str = "D",
) -> TransformationPlan:
    """Generate an inspectable, explicit transformation plan before mutating any data."""
    dims = dimension_columns or []
    unique_channels = sorted([str(c) for c in df[channel_column].dropna().unique()])
    pivoted_names = [f"{_clean_token(c)}_spend" for c in unique_channels]

    rules: dict[str, str] = {
        spend_column: "sum",
    }
    for t in target_columns:
        rules[t] = "sum"

    for c in df.columns:
        if c not in [date_column, channel_column, spend_column] + target_columns + dims:
            semantic = classify_metric_aggregation(c)
            if semantic == AggregationSemantic.RATIO_RECOMPUTE:
                rules[c] = "recompute_or_drop"
            elif pd.api.types.is_numeric_dtype(df[c]):
                rules[c] = "sum"
            else:
                rules[c] = "first"

    return TransformationPlan(
        date_column=date_column,
        channel_column=channel_column,
        spend_column=spend_column,
        target_columns=target_columns,
        dimension_columns=dims,
        frequency=frequency,
        aggregation_rules=rules,
        pivot_channels=pivoted_names,
    )


def transform_long_form_export(
    df: pd.DataFrame,
    plan: TransformationPlan,
) -> tuple[pd.DataFrame, TransformationProvenance]:
    """Execute long-to-wide pivot and panel creation according to plan."""
    raw_csv = df.to_csv(index=False).encode("utf-8")
    source_fp = hashlib.sha256(raw_csv).hexdigest()
    rows_before = len(df)
    warnings: list[str] = []

    # 1. Standardize dates
    df_work = df.copy()
    df_work[plan.date_column] = pd.to_datetime(df_work[plan.date_column], errors="coerce")
    valid_mask = df_work[plan.date_column].notna()
    excluded_rows = int((~valid_mask).sum())
    df_work = df_work[valid_mask]

    index_cols = [plan.date_column] + plan.dimension_columns

    # 2. Pivot channel spend into wide columns
    df_work["_channel_col_clean"] = df_work[plan.channel_column].astype(str).map(
        lambda x: f"{_clean_token(x)}_spend"
    )
    pivoted_spend = df_work.pivot_table(
        index=index_cols,
        columns="_channel_col_clean",
        values=plan.spend_column,
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()

    channel_cols_created = [c for c in pivoted_spend.columns if c.endswith("_spend")]

    # 3. Aggregate target columns
    agg_dict = {t: "sum" for t in plan.target_columns if t in df_work.columns}

    # Also aggregate click/impression components for ratio recomputation if available
    component_cols = [c for c in ["clicks", "impressions", "link_clicks", "views"] if c in df_work.columns]
    for comp in component_cols:
        agg_dict[comp] = "sum"

    aggregated_targets = df_work.groupby(index_cols, as_index=False)[list(agg_dict.keys())].agg(agg_dict)

    # 4. Merge pivoted spend and aggregated targets
    merged = pd.merge(pivoted_spend, aggregated_targets, on=index_cols, how="outer")

    # 5. Handle Ratio Metrics (e.g. CTR = clicks / impressions)
    if "clicks" in merged.columns and "impressions" in merged.columns:
        safe_impr = merged["impressions"].replace(0, float("nan"))
        merged["ctr"] = (merged["clicks"] / safe_impr).fillna(0.0)

    # 6. Ensure continuous date calendar
    min_date = merged[plan.date_column].min()
    max_date = merged[plan.date_column].max()
    full_dates = pd.date_range(min_date, max_date, freq=plan.frequency)

    inserted_periods = 0
    if plan.dimension_columns:
        # Panel cartesian product: full dates x unique dimension values
        unique_dims = [df_work[d].unique() for d in plan.dimension_columns]
        mesh = pd.MultiIndex.from_product([full_dates] + unique_dims, names=index_cols).to_frame().reset_index(drop=True)
        final_df = pd.merge(mesh, merged, on=index_cols, how="left")
    else:
        grid = pd.DataFrame({plan.date_column: full_dates})
        final_df = pd.merge(grid, merged, on=[plan.date_column], how="left")

    inserted_periods = max(0, len(final_df) - len(merged))

    # Safe zero-fill ONLY for channel spend columns (missing row = no spend)
    for c in channel_cols_created:
        final_df[c] = final_df[c].fillna(0.0)

    # Targets filled with 0.0 for continuity
    for t in plan.target_columns:
        if t in final_df.columns:
            final_df[t] = final_df[t].fillna(0.0)

    # Format date string as YYYY-MM-DD
    final_df[plan.date_column] = final_df[plan.date_column].dt.strftime("%Y-%m-%d")
    final_df = final_df.sort_values(by=index_cols).reset_index(drop=True)

    spend_before = float(df_work[plan.spend_column].sum()) if plan.spend_column in df_work.columns else 0.0
    spend_after = float(final_df[channel_cols_created].sum().sum()) if channel_cols_created else 0.0
    spend_delta = float(abs(spend_after - spend_before))
    spend_reconciled = spend_delta < 1e-4

    transformed_csv = final_df.to_csv(index=False).encode("utf-8")
    transformed_fp = hashlib.sha256(transformed_csv).hexdigest()

    provenance = TransformationProvenance(
        rows_before=rows_before,
        rows_after=len(final_df),
        inserted_periods=inserted_periods,
        excluded_rows=excluded_rows,
        channel_columns_created=channel_cols_created,
        source_fingerprint=source_fp,
        transformed_fingerprint=transformed_fp,
        aggregation_rules_applied=plan.aggregation_rules,
        spend_before=spend_before,
        spend_after=spend_after,
        spend_delta=spend_delta,
        spend_reconciled=spend_reconciled,
        warnings=warnings,
    )

    return final_df, provenance
