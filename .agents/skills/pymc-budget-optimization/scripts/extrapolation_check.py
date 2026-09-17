#!/usr/bin/env python3
"""Check proposed channel spend against historical spend distributions to detect extrapolation risk.

Flags channels where proposed spend exceeds 1.5x of historical 95th percentile spend.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def check_extrapolation(
    data_path: str,
    channel_spends: dict[str, float],
) -> dict:
    path = Path(data_path)
    if not path.exists():
        return {"error": f"File not found: {data_path}"}

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    report = {}
    has_risk = False

    for ch, proposed in channel_spends.items():
        if ch not in df.columns:
            report[ch] = {"error": f"Channel '{ch}' not found in historical data"}
            continue

        p95 = float(df[ch].quantile(0.95))
        max_val = float(df[ch].max())
        threshold = 1.5 * p95

        exceeds = proposed > threshold
        if exceeds:
            has_risk = True

        report[ch] = {
            "proposed_spend": proposed,
            "historical_p95": round(p95, 2),
            "historical_max": round(max_val, 2),
            "extrapolation_threshold_1_5x": round(threshold, 2),
            "extrapolation_risk": exceeds,
            "ratio_to_p95": round(proposed / p95, 2) if p95 > 0 else None,
        }

    return {
        "has_extrapolation_risk": has_risk,
        "channel_assessment": report,
        "recommendation": (
            "Extrapolation risk detected: proposed spend exceeds 1.5x historical p95. "
            "Consider reducing spend scale or running an incrementality test."
            if has_risk
            else "All proposed spends are within safe historical boundaries."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Check proposed spend against historical boundaries.")
    parser.add_argument("data_file", help="Path to historical CSV or Parquet data")
    parser.add_argument("--spends", required=True, help="JSON string mapping channel -> proposed spend")
    args = parser.parse_args()

    spends = json.loads(args.spends)
    result = check_extrapolation(args.data_file, spends)
    print(json.dumps(result, indent=2))
    if result.get("has_extrapolation_risk"):
        sys.exit(2)


if __name__ == "__main__":
    main()
