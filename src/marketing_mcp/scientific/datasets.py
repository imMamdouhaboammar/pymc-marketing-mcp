"""Pure scientific dataset inspection, validation, and summary functions without MCP or auth context."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset
from marketing_mcp.schemas.models import (
    ColumnSummary,
    DatasetInspection,
    DatasetSummary,
    DatasetValidationResult,
    Finding,
)


def inspect_dataset_frame(df: pd.DataFrame, dataset_id: str = "ad_hoc") -> DatasetInspection:
    """Inspects a pandas DataFrame for candidate targets, channels, frequency, and continuity gaps."""
    possible_dates = []
    for c in df.columns:
        if "date" in c.lower() or "week" in c.lower():
            possible_dates.append(c)
    date_col = possible_dates[0] if possible_dates else None
    freq = None
    start = end = None
    missing: list[str] = []
    issues: list[Finding] = []

    if date_col:
        dates = (
            pd.to_datetime(df[date_col], errors="coerce")
            .dropna()
            .sort_values()
            .drop_duplicates()
        )
        start = dates.min().date().isoformat() if len(dates) else None
        end = dates.max().date().isoformat() if len(dates) else None
        if len(dates) >= 3:
            deltas = dates.diff().dropna().dt.days
            med = float(deltas.median())
            freq = (
                "daily"
                if med <= 1.5
                else "weekly"
                if med <= 8
                else "monthly"
                if med <= 35
                else "irregular"
            )
            if freq == "weekly":
                expected = pd.date_range(
                    dates.min(), dates.max(), freq=pd.Timedelta(days=round(med))
                )
                missing = [d.date().isoformat() for d in expected.difference(dates)[:100]]

    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    targets = [
        c
        for c in numeric
        if any(k in c.lower() for k in ["revenue", "sales", "orders", "target", "conversion"])
    ]
    channels = [
        c
        for c in numeric
        if any(
            k in c.lower()
            for k in [
                "spend",
                "meta",
                "google",
                "tiktok",
                "youtube",
                "facebook",
                "search",
                "media",
                "tv",
                "radio",
            ]
        )
        and c not in targets
    ]
    controls = [
        c
        for c in numeric
        if c not in targets + channels
        and any(
            k in c.lower()
            for k in ["discount", "price", "holiday", "promo", "season", "competitor", "macro"]
        )
    ]

    if missing:
        issues.append(
            Finding(
                severity="warning",
                code="MISSING_PERIODS",
                message="Potential missing periods detected",
                evidence={"count": len(missing)},
                suggested_action="Validate continuity before modeling",
            )
        )

    candidate = bool(date_col and targets and channels and len(df) >= 52)

    return DatasetInspection(
        dataset_id=dataset_id,
        rows=len(df),
        frequency=freq,
        date_range={"start": start, "end": end},
        possible_targets=targets,
        possible_channels=channels,
        possible_controls=controls,
        missing_periods=missing,
        issues=issues,
        mmm_candidate=candidate,
    )


def validate_dataset_frame(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    channel_columns: list[str],
    control_columns: list[str] | None = None,
    dims: list[str] | None = None,
    dataset_id: str = "ad_hoc",
) -> DatasetValidationResult:
    """Runs statistical validation on a DataFrame returning findings and modeling readiness verdict."""
    findings = validate_mmm_dataset(
        df=df,
        date_column=date_column,
        target_column=target_column,
        channel_columns=channel_columns,
        control_columns=control_columns or [],
        dims=dims or [],
    )
    valid = not any(f.severity == "error" for f in findings)
    return DatasetValidationResult(
        dataset_id=dataset_id,
        findings=findings,
        valid_for_modeling=valid,
    )


def summarize_dataset_frame(
    df: pd.DataFrame,
    date_column: str | None = None,
    channel_columns: list[str] | None = None,
    target_column: str | None = None,
) -> DatasetSummary:
    """Computes summary statistics and spend share metrics for a DataFrame."""
    column_summaries: list[ColumnSummary] = []
    for col in df.columns:
        series = df[col]
        is_num = pd.api.types.is_numeric_dtype(series)
        non_null = int(series.count())
        null_count = int(series.isna().sum())
        col_summary = ColumnSummary(
            name=str(col),
            dtype=str(series.dtype),
            non_null_count=non_null,
            null_count=null_count,
            mean=float(series.mean()) if is_num and non_null > 0 else None,
            std=float(series.std()) if is_num and non_null > 1 else None,
            min=float(series.min()) if is_num and non_null > 0 else None,
            max=float(series.max()) if is_num and non_null > 0 else None,
        )
        column_summaries.append(col_summary)

    date_range = None
    if date_column and date_column in df.columns:
        dates = pd.to_datetime(df[date_column], errors="coerce").dropna()
        if len(dates):
            date_range = {
                "start": dates.min().date().isoformat(),
                "end": dates.max().date().isoformat(),
            }

    total_spend = None
    spend_shares: dict[str, float] = {}
    if channel_columns:
        channel_sums = {}
        for ch in channel_columns:
            if ch in df.columns and pd.api.types.is_numeric_dtype(df[ch]):
                channel_sums[ch] = float(df[ch].fillna(0).sum())
        all_spend = sum(channel_sums.values())
        total_spend = all_spend
        if all_spend > 0:
            spend_shares = {ch: round(val / all_spend, 4) for ch, val in channel_sums.items()}

    return DatasetSummary(
        rows=len(df),
        columns=len(df.columns),
        column_summaries=column_summaries,
        date_range=date_range,
        total_spend=total_spend,
        channel_spend_shares=spend_shares,
    )
