#!/usr/bin/env python3
"""Validate lift test measurement inputs and calculate standard error sigma from confidence intervals.

Ensures payload matches PyMC-Marketing LiftTestMeasurement schema.
"""

from __future__ import annotations

import argparse
import json
import sys


def compute_lift_measurement(
    channel: str,
    baseline_x: float,
    delta_x: float,
    delta_y: float | None = None,
    sigma: float | None = None,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    confidence_level: float = 0.95,
    description: str | None = None,
) -> dict:
    if delta_x <= 0:
        return {"valid": False, "error": "delta_x must be strictly greater than 0"}
    if baseline_x < 0:
        return {"valid": False, "error": "baseline_x cannot be negative"}

    # Derive delta_y and sigma from CI if provided
    if ci_lower is not None and ci_upper is not None:
        if ci_lower >= ci_upper:
            return {"valid": False, "error": "ci_lower must be less than ci_upper"}
        derived_delta_y = (ci_upper + ci_lower) / 2.0
        if delta_y is None:
            delta_y = derived_delta_y

        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence_level, 1.96)
        derived_sigma = (ci_upper - ci_lower) / (2.0 * z)
        if sigma is None:
            sigma = derived_sigma

    if delta_y is None or sigma is None:
        return {
            "valid": False,
            "error": "Must provide either (delta_y and sigma) OR (ci_lower and ci_upper)",
        }

    if sigma <= 0:
        return {"valid": False, "error": "sigma must be strictly positive"}

    measurement = {
        "channel": channel,
        "x": baseline_x,
        "delta_x": delta_x,
        "delta_y": round(delta_y, 2),
        "sigma": round(sigma, 2),
        "description": description or f"Lift test on {channel}",
    }

    return {
        "valid": True,
        "measurement": measurement,
        "implied_iroas": round(delta_y / delta_x, 2),
        "iroas_95ci": [
            round((delta_y - 1.96 * sigma) / delta_x, 2),
            round((delta_y + 1.96 * sigma) / delta_x, 2),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Validate lift test measurement and calculate sigma.")
    parser.add_argument("--channel", required=True, help="Marketing channel name")
    parser.add_argument("--baseline-x", type=float, required=True, help="Baseline spend x")
    parser.add_argument("--delta-x", type=float, required=True, help="Incremental spend delta_x")
    parser.add_argument("--delta-y", type=float, help="Incremental KPI delta_y")
    parser.add_argument("--sigma", type=float, help="Standard error of delta_y")
    parser.add_argument("--ci-lower", type=float, help="Lower bound of confidence interval")
    parser.add_argument("--ci-upper", type=float, help="Upper bound of confidence interval")
    parser.add_argument("--confidence", type=float, default=0.95, help="Confidence level (e.g. 0.95)")
    parser.add_argument("--desc", help="Description of experiment")
    args = parser.parse_args()

    res = compute_lift_measurement(
        channel=args.channel,
        baseline_x=args.baseline_x,
        delta_x=args.delta_x,
        delta_y=args.delta_y,
        sigma=args.sigma,
        ci_lower=args.ci_lower,
        ci_upper=args.ci_upper,
        confidence_level=args.confidence,
        description=args.desc,
    )
    print(json.dumps(res, indent=2))
    if not res["valid"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
