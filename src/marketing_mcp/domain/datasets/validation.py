from __future__ import annotations

from itertools import product

import pandas as pd

from marketing_mcp.schemas.models import Finding


def _f(severity, code, message, evidence=None, action=None):
    return Finding(
        severity=severity,
        code=code,
        message=message,
        evidence=evidence or {},
        suggested_action=action,
    )


def _panel_findings(df: pd.DataFrame, dates: pd.Series, dims: list[str]) -> list[Finding]:
    if not dims or dates.isna().any() or any(df[dim].isna().any() for dim in dims):
        return []
    panel = df[dims].copy()
    panel["__date"] = dates.values

    findings: list[Finding] = []
    actual_combos = set(panel[dims].drop_duplicates().itertuples(index=False, name=None))
    dim_values = [df[dim].drop_duplicates().tolist() for dim in dims]
    expected_combos = set(product(*dim_values))
    missing_combos = expected_combos - actual_combos

    grouped = panel.groupby(dims, dropna=False, sort=False)["__date"]
    date_sets = {
        key if isinstance(key, tuple) else (key,): frozenset(values.tolist())
        for key, values in grouped
    }
    all_dates = frozenset(dates.dropna().unique().tolist())
    incomplete = {
        str(key): len(all_dates - values)
        for key, values in date_sets.items()
        if values != all_dates
    }
    if missing_combos or incomplete:
        findings.append(
            _f(
                "error",
                "NON_RECTANGULAR_PANEL",
                "Multidimensional MMM data must contain the same dates for every dimension combination",
                {
                    "dims": dims,
                    "missing_dimension_combinations": [
                        list(x) for x in sorted(missing_combos, key=str)
                    ][:20],
                    "groups_with_missing_dates": dict(list(incomplete.items())[:20]),
                },
                "Complete the date × dimension grid or remove unsupported panel slices",
            )
        )
    return findings


def validate_mmm_dataset(
    df: pd.DataFrame,
    date_column: str,
    target_column: str,
    channel_columns: list[str],
    control_columns: list[str],
    dims: list[str] | None = None,
) -> list[Finding]:
    dims = dims or []
    findings = []
    required = [date_column, target_column, *channel_columns, *control_columns, *dims]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return [
            _f(
                "error",
                "MISSING_COLUMNS",
                "Required columns are missing",
                {"columns": missing},
                "Map valid dataset columns and retry",
            )
        ]

    dates = pd.to_datetime(df[date_column], errors="coerce")
    if dates.isna().any():
        findings.append(
            _f(
                "error",
                "INVALID_DATE",
                "Date column contains invalid values",
                {"count": int(dates.isna().sum())},
                "Parse dates before modeling",
            )
        )

    key_frame = df[dims].copy() if dims else pd.DataFrame(index=df.index)
    key_frame["__date"] = dates
    duplicate_keys = key_frame.duplicated(subset=["__date", *dims])
    if duplicate_keys.any():
        findings.append(
            _f(
                "error",
                "DUPLICATE_PERIOD",
                "Dataset contains duplicate date/dimension keys",
                {"count": int(duplicate_keys.sum()), "key": [date_column, *dims]},
                "Aggregate or disambiguate duplicate observations",
            )
        )

    for dim in dims:
        if df[dim].isna().any():
            findings.append(
                _f(
                    "error",
                    "MISSING_DIMENSION_VALUE",
                    f"{dim} contains missing dimension values",
                    {"dimension": dim, "count": int(df[dim].isna().sum())},
                    "Fill or remove incomplete dimension values",
                )
            )
        if df[dim].nunique(dropna=True) < 1:
            findings.append(
                _f(
                    "error",
                    "EMPTY_DIMENSION",
                    f"{dim} has no usable dimension values",
                    {"dimension": dim},
                )
            )

    findings.extend(_panel_findings(df, dates, dims))

    time_periods = int(dates.nunique(dropna=True))
    if time_periods < 52:
        findings.append(
            _f(
                "error",
                "INSUFFICIENT_DATA",
                "Fewer than 52 unique time periods are available",
                {"time_periods": time_periods, "rows": len(df)},
                "Provide more history before fitting MMM",
            )
        )
    elif time_periods < 104:
        findings.append(
            _f(
                "warning",
                "LIMITED_HISTORY",
                "Less than two years of time periods are available",
                {"time_periods": time_periods, "rows": len(df)},
                "Interpret seasonality and long carryover cautiously",
            )
        )

    # Check temporal continuity (daily, weekly, monthly calendar gaps)
    clean_dates = dates.dropna().sort_values().drop_duplicates()
    if len(clean_dates) >= 3:
        deltas = clean_dates.diff().dropna().dt.days
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
        if freq in ("daily", "weekly"):
            step = pd.Timedelta(days=round(med)) if freq == "weekly" else pd.Timedelta(days=1)
            expected_index = pd.date_range(clean_dates.min(), clean_dates.max(), freq=step)
            missing_dates = expected_index.difference(clean_dates)
            if len(missing_dates) > 0:
                findings.append(
                    _f(
                        "warning",
                        "MISSING_PERIODS",
                        f"Detected {len(missing_dates)} missing {freq} calendar periods in date range",
                        {
                            "frequency": freq,
                            "observed_periods": len(clean_dates),
                            "expected_periods": len(expected_index),
                            "missing_count": len(missing_dates),
                            "first_missing_dates": [d.date().isoformat() for d in missing_dates[:10]],
                        },
                        "Inspect or impute missing observation dates before fitting MMM to avoid distorted adstock",
                    )
                )

    for column in [target_column, *channel_columns, *control_columns]:
        if df[column].isna().any():
            findings.append(
                _f(
                    "error",
                    "MISSING_VALUES",
                    f"{column} contains missing values",
                    {"column": column, "count": int(df[column].isna().sum())},
                    "Impute or repair upstream",
                )
            )

    for column in channel_columns:
        series = pd.to_numeric(df[column], errors="coerce")
        if series.isna().any():
            findings.append(
                _f(
                    "error",
                    "NON_NUMERIC_MEDIA",
                    f"{column} is not fully numeric",
                    {"column": column},
                )
            )
        if (series < 0).any():
            findings.append(
                _f(
                    "error",
                    "NEGATIVE_MEDIA",
                    f"{column} contains negative media values",
                    {"column": column, "count": int((series < 0).sum())},
                    "Correct spend or media units",
                )
            )
        if series.nunique(dropna=True) <= 1:
            findings.append(
                _f(
                    "error",
                    "NO_SPEND_VARIATION",
                    f"{column} has no useful variation",
                    {"column": column},
                    "Add periods with spend variation or remove channel",
                )
            )
        zero_run = (series.fillna(0) == 0).astype(int)
        longest = int(zero_run.groupby((zero_run == 0).cumsum()).sum().max()) if len(series) else 0
        if longest >= 13:
            findings.append(
                _f(
                    "warning",
                    "LONG_ZERO_SPEND_RUN",
                    f"{column} has a long zero-spend run",
                    {"column": column, "periods": longest},
                    "Check launch/offline periods and identifiability",
                )
            )

    target = pd.to_numeric(df[target_column], errors="coerce")
    if target.nunique(dropna=True) <= 2:
        findings.append(
            _f(
                "error",
                "BAD_TARGET",
                "Target has insufficient numeric variation",
                {"unique": int(target.nunique(dropna=True))},
            )
        )

    # Check for target tracking gaps: significant media spend with zero or missing target
    if len(channel_columns) > 0:
        total_media_spend = df[channel_columns].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
        target_series = target.fillna(0)
        gap_mask = (total_media_spend > 0) & (target_series == 0)
        gap_count = int(gap_mask.sum())
        if gap_count > 0:
            findings.append(
                _f(
                    "warning",
                    "POSSIBLE_TARGET_TRACKING_GAP",
                    f"Detected {gap_count} periods with active media spend but zero {target_column}",
                    {
                        "target_column": target_column,
                        "zero_target_active_spend_count": gap_count,
                        "pct_of_periods": round((gap_count / max(1, len(df))) * 100, 2),
                    },
                    "Verify telemetry, tracking outages, or seasonal closure periods",
                )
            )

    if len(channel_columns) > 1:
        corr = df[channel_columns].apply(pd.to_numeric, errors="coerce").corr().abs()
        for i, a in enumerate(channel_columns):
            for b in channel_columns[i + 1 :]:
                value = float(corr.loc[a, b]) if pd.notna(corr.loc[a, b]) else 0.0
                if value >= 0.90:
                    findings.append(
                        _f(
                            "warning",
                            "HIGH_CHANNEL_CORRELATION",
                            f"{a} and {b} move together strongly",
                            {"channels": [a, b], "correlation": round(value, 4)},
                            "Interpret separate channel effects cautiously or calibrate with experiments",
                        )
                    )

    for column in [target_column, *channel_columns]:
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(series) > 10:
            q1, q3 = series.quantile([0.25, 0.75])
            iqr = q3 - q1
            if iqr > 0:
                outliers = ((series < q1 - 3 * iqr) | (series > q3 + 3 * iqr)).sum()
                if outliers > 0:
                    findings.append(
                        _f(
                            "warning",
                            "EXTREME_OUTLIERS",
                            f"{column} contains extreme values",
                            {"column": column, "count": int(outliers)},
                            "Verify whether these periods are genuine events or data errors",
                        )
                    )

    # Check for mixed campaign objectives (e.g. upper-funnel awareness vs lower-funnel sales)
    for col in df.columns:
        if col in required:
            continue
        cl = col.lower()
        if any(k in cl for k in ["objective", "goal", "funnel", "campaign_type"]):
            vals = [str(v).lower() for v in df[col].dropna().unique()]
            has_upper = any(k in v for v in vals for k in ["aware", "traffic", "reach", "brand", "view"])
            has_lower = any(k in v for v in vals for k in ["sale", "purchase", "lead", "conversion", "revenue"])
            if has_upper and has_lower:
                findings.append(
                    _f(
                        "warning",
                        "MIXED_CAMPAIGN_OBJECTIVES",
                        f"Column '{col}' indicates mixed campaign objectives (upper-funnel brand/awareness and lower-funnel conversion/sales). "
                        "Pooling non-revenue upper-funnel campaigns into a revenue MMM distorts adstock decay and sales response curves.",
                        evidence={"column": col, "detected_objectives": list(vals[:10])},
                        action="Filter dataset to conversion-oriented campaigns or model awareness as an upstream KPI",
                    )
                )

    # Check for staggered channel lifecycles and temporal confounding
    if len(channel_columns) > 1:
        active_masks = {}
        for ch in channel_columns:
            s = pd.to_numeric(df[ch], errors="coerce").fillna(0)
            active_masks[ch] = (s > 0)

        for i, a in enumerate(channel_columns):
            for b in channel_columns[i + 1 :]:
                mask_a = active_masks[a]
                mask_b = active_masks[b]
                count_a = int(mask_a.sum())
                count_b = int(mask_b.sum())
                if count_a >= 5 and count_b >= 5:
                    union = int((mask_a | mask_b).sum())
                    inter = int((mask_a & mask_b).sum())
                    overlap_ratio = inter / max(1, union)
                    if overlap_ratio < 0.25:
                        findings.append(
                            _f(
                                "warning",
                                "STAGGERED_CHANNEL_LIFECYCLES",
                                f"Channels '{a}' and '{b}' exhibit staggered or largely disjoint active periods (overlap: {overlap_ratio:.1%}). "
                                "Temporal confounding can prevent cleanly separating channel response from macro time trends.",
                                evidence={
                                    "channels": [a, b],
                                    "overlap_ratio": round(overlap_ratio, 3),
                                    "active_periods": {a: count_a, b: count_b},
                                },
                                action="Align observation windows across media channels or supply informative priors on adstock decay",
                            )
                        )

    # Check for unmodeled market heterogeneity
    if not dims:
        for col in df.columns:
            if col in required:
                continue
            cl = col.lower()
            if any(k in cl for k in ["market", "country", "geo", "region"]):
                unique_vals = df[col].dropna().unique()
                if 2 <= len(unique_vals) <= 50:
                    findings.append(
                        _f(
                            "warning",
                            "UNMODELED_MARKET_HETEROGENEITY",
                            f"Dataset contains geographic/market column '{col}' with {len(unique_vals)} unique values, but 'dims' was not provided. "
                            "Fitting a single pooled global MMM may hide material market-level heterogeneity.",
                            evidence={"column": col, "unique_markets": [str(v) for v in unique_vals[:10]]},
                            action=f"Specify dims=['{col}'] to fit a hierarchical/panel MMM or fit separate models per market",
                        )
                    )

    return findings
