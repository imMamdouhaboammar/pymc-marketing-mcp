#!/usr/bin/env python3
"""Pre-check marketing dataset for MMM readiness before MCP registration.

Validates date continuity, spend columns, negative values, pairwise collinearity,
and panel rectangularity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def precheck_dataset(
    file_path: str,
    date_col: str,
    target_col: str,
    channel_cols: list[str],
    dim_cols: list[str] | None = None,
) -> dict:
    dim_cols = dim_cols or []
    path = Path(file_path)
    if not path.exists():
        return {"valid": False, "error": f"File not found: {file_path}"}

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    findings = []

    # 1. Date checks
    if date_col not in df.columns:
        return {"valid": False, "error": f"Date column '{date_col}' missing"}

    df[date_col] = pd.to_datetime(df[date_col])
    unique_dates = int(df[date_col].nunique())
    if unique_dates < 52:
        findings.append({
            "code": "SHORT_TIME_SERIES",
            "severity": "warning",
            "message": f"Only {unique_dates} unique dates found. 52+ weeks recommended for seasonality.",
        })

    # 2. Target checks
    if target_col not in df.columns:
        return {"valid": False, "error": f"Target column '{target_col}' missing"}

    if (df[target_col] < 0).any():
        findings.append({
            "code": "NEGATIVE_TARGET",
            "severity": "error",
            "message": "Target column contains negative values.",
        })

    # 3. Channel checks
    for ch in channel_cols:
        if ch not in df.columns:
            return {"valid": False, "error": f"Channel column '{ch}' missing"}
        if (df[ch] < 0).any():
            findings.append({
                "code": "NEGATIVE_SPEND",
                "severity": "error",
                "message": f"Channel '{ch}' contains negative spend values.",
            })
        if df[ch].std() == 0 or df[ch].sum() == 0:
            findings.append({
                "code": "ZERO_VARIANCE_CHANNEL",
                "severity": "error",
                "message": f"Channel '{ch}' has zero variance or zero total spend.",
            })

    # 4. Collinearity check
    if len(channel_cols) > 1:
        corr_matrix = df[channel_cols].corr().abs()
        np.fill_diagonal(corr_matrix.values, 0)
        high_corr = np.where(corr_matrix >= 0.90)
        seen_pairs = set()
        for r, c in zip(*high_corr, strict=False):
            pair = tuple(sorted([channel_cols[r], channel_cols[c]]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                findings.append({
                    "code": "HIGH_COLINEARITY",
                    "severity": "warning",
                    "message": (
                        f"Channels '{pair[0]}' and '{pair[1]}' have correlation "
                        f"r={corr_matrix.iloc[r, c]:.2f} >= 0.90."
                    ),
                })

    # 5. Panel Rectangularity
    if dim_cols:
        expected_rows = unique_dates
        for d in dim_cols:
            if d not in df.columns:
                return {"valid": False, "error": f"Dimension column '{d}' missing"}
            expected_rows *= int(df[d].nunique())
        if len(df) != expected_rows:
            findings.append({
                "code": "NON_RECTANGULAR_PANEL",
                "severity": "error",
                "message": f"Panel is non-rectangular. Found {len(df)} rows, expected {expected_rows}.",
            })

    has_errors = any(f["severity"] == "error" for f in findings)
    return {
        "valid": not has_errors,
        "rows": len(df),
        "unique_dates": unique_dates,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description="Pre-check marketing dataset for MMM readiness.")
    parser.add_argument("file", help="Path to CSV or Parquet file")
    parser.add_argument("--date", required=True, help="Date column name")
    parser.add_argument("--target", required=True, help="Target KPI column name")
    parser.add_argument("--channels", nargs="+", required=True, help="Channel spend column names")
    parser.add_argument("--dims", nargs="*", default=[], help="Dimension columns for panel MMM")
    args = parser.parse_args()

    res = precheck_dataset(args.file, args.date, args.target, args.channels, args.dims)
    print(json.dumps(res, indent=2))
    if not res["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
