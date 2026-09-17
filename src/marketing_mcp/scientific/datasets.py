"""Pure scientific dataset inspection, validation, and summary functions without MCP or auth context."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset
from marketing_mcp.intelligence.contracts.semantics import SemanticRole
from marketing_mcp.intelligence.contracts.suitability import AnalysisType
from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine
from marketing_mcp.schemas.models import (
    ColumnSummary,
    DatasetInspection,
    DatasetSummary,
    DatasetValidationResult,
    Finding,
)


def inspect_dataset_frame(df: pd.DataFrame, dataset_id: str = "ad_hoc") -> DatasetInspection:
    """Inspects a pandas DataFrame for candidate targets, channels, frequency, and continuity gaps."""
    engine = MarketingDataIntelligenceEngine()
    contract = engine.analyze_dataset(df, dataset_id=dataset_id)

    findings: list[Finding] = []
    for iss in contract.issues:
        sev = "error" if iss.blocking else ("warning" if iss.severity in ("warning", "high") else "info")
        findings.append(
            Finding(
                severity=sev,
                code=iss.code.value if hasattr(iss.code, "value") else str(iss.code),
                message=iss.summary,
                evidence=iss.evidence,
                suggested_action=iss.recommended_action,
            )
        )

    date_col = contract.structural.temporal.date_column
    if not date_col:
        findings.append(
            Finding(
                severity="error",
                code="MISSING_DATE_COLUMN",
                message="No recognizable date or week column found in dataset",
                suggested_action="Ensure dataset contains a temporal column (e.g. 'date', 'week')",
            )
        )

    targets = [c.column for c in contract.columns.values() if c.role == SemanticRole.TARGET]
    if not targets:
        findings.append(
            Finding(
                severity="error",
                code="MISSING_TARGET_COLUMN",
                message="No recognizable KPI or sales target column detected",
                suggested_action="Ensure dataset contains a numeric KPI column (e.g. 'sales', 'revenue')",
            )
        )

    channels = [c.column for c in contract.channels]

    # Check long-form platform detection
    is_long_form = False
    detected_cat_channels = []
    detected_dims = [c.column for c in contract.dimensions]

    cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and c != date_col]
    for col in cat_cols:
        uniques = df[col].dropna().unique()
        if len(uniques) <= 50:
            cl = col.lower()
            if any(k in cl for k in ["channel", "platform", "media", "source", "network"]):
                is_long_form = True
                detected_cat_channels.extend([str(v) for v in uniques])
            elif any(k in cl for k in ["market", "country", "geo", "region", "state", "city", "segment"]) and col not in detected_dims:
                detected_dims.append(col)

    if not channels and not is_long_form:
        findings.append(
            Finding(
                severity="error",
                code="MISSING_CHANNEL_COLUMNS",
                message="No recognizable media spend or impression columns detected",
                suggested_action="Ensure dataset contains media channel columns (e.g. 'meta_spend', 'search_spend')",
            )
        )

    if len(df) < 52:
        findings.append(
            Finding(
                severity="warning",
                code="INSUFFICIENT_OBSERVATIONS",
                message=f"Dataset has {len(df)} rows; PyMC MMM recommends at least 52 periods",
                evidence={"row_count": len(df), "recommended_min": 52},
                suggested_action="Collect at least 52 weekly observations for robust MCMC inference",
            )
        )

    candidate = bool(date_col and targets and (channels or is_long_form) and len(df) >= 52)
    controls = [c.column for c in contract.controls]

    return DatasetInspection(
        dataset_id=dataset_id,
        rows=contract.structural.rows,
        frequency=contract.structural.temporal.frequency,
        date_range={"start": contract.structural.temporal.start_date, "end": contract.structural.temporal.end_date},
        possible_targets=targets,
        possible_channels=channels,
        possible_controls=controls,
        missing_periods=contract.structural.temporal.missing_periods,
        issues=findings,
        mmm_candidate=candidate,
        is_long_form=is_long_form,
        detected_dimensions=detected_dims,
        detected_categorical_channels=detected_cat_channels,
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
    """Generates a comprehensive statistical and structural summary of the dataset."""
    cols: list[ColumnSummary] = []
    total_spend = 0.0
    channel_spends: dict[str, float] = {}

    target_channels = set(channel_columns) if channel_columns is not None else {
        c for c in df.columns if any(k in c.lower() for k in ["spend", "cost", "investment", "meta", "google", "tiktok", "youtube"])
        and not any(k in c.lower() for k in ["revenue", "sales", "discount", "target"])
    }

    for c in df.columns:
        s = df[c]
        non_null = int(s.count())
        null_count = int(s.isna().sum())
        mean_val = std_val = min_val = max_val = None

        sparkline = None
        if pd.api.types.is_numeric_dtype(s):
            clean = s.dropna()
            if len(clean) > 0:
                mean_val = float(clean.mean())
                std_val = float(clean.std()) if len(clean) > 1 else 0.0
                min_val = float(clean.min())
                max_val = float(clean.max())

                try:
                    from marketing_mcp.accelerators import generate_sparkline
                    vals = [float(x) for x in clean]
                    if vals:
                        sparkline = generate_sparkline(vals)
                except Exception:
                    sparkline = None

                if c in target_channels:
                    sp = float(clean.sum())
                    if sp > 0:
                        channel_spends[c] = sp
                        total_spend += sp

        cols.append(
            ColumnSummary(
                name=c,
                dtype=str(s.dtype),
                non_null_count=non_null,
                null_count=null_count,
                mean=mean_val,
                std=std_val,
                min=min_val,
                max=max_val,
                sparkline=sparkline,
            )
        )

    shares = {}
    if total_spend > 0:
        shares = {k: round(v / total_spend, 4) for k, v in channel_spends.items()}

    date_range = None
    if date_column and date_column in df.columns:
        dates = pd.to_datetime(df[date_column], errors="coerce").dropna().sort_values()
        if len(dates):
            date_range = {"start": dates.iloc[0].date().isoformat(), "end": dates.iloc[-1].date().isoformat()}

    return DatasetSummary(
        rows=len(df),
        columns=len(df.columns),
        column_summaries=cols,
        date_range=date_range,
        total_spend=round(total_spend, 2) if total_spend > 0 else None,
        channel_spend_shares=shares,
    )
