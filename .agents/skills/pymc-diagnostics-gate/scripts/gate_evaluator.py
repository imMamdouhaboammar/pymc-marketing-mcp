#!/usr/bin/env python3
"""Evaluate MCMC diagnostic metrics against PyMC-Marketing decision gates.

Outputs decision status (approved, approved_with_caution, rejected) and concrete remediation instructions.
"""

from __future__ import annotations

import argparse
import json
import sys


def evaluate_gate(
    divergences: int,
    max_rhat: float,
    min_bulk_ess: float,
    min_tail_ess: float = 400.0,
    coverage_94: float = 0.85,
    nrmse: float = 0.08,
) -> dict:
    failures = []
    warnings = []
    remediations = []

    # 1. Divergences
    if divergences > 5:
        failures.append(f"Hard failure: {divergences} divergences (> 5).")
        remediations.append("Increase target_accept from 0.90 to 0.95 or 0.98. Increase tune to 2000.")
    elif divergences > 0:
        warnings.append(f"Caution: {divergences} divergences (1-5).")
        remediations.append("Consider increasing target_accept to 0.95.")

    # 2. R-hat
    if max_rhat > 1.05:
        failures.append(f"Hard failure: Max R-hat is {max_rhat:.3f} (> 1.05).")
        remediations.append("Chains have not converged. Check for multicollinear channels, simplify saturation priors, or double draws/tune.")
    elif max_rhat > 1.01:
        warnings.append(f"Caution: Max R-hat is {max_rhat:.3f} (1.01-1.05).")
        remediations.append("Increase draws to 2000 to ensure chain stabilization.")

    # 3. Bulk ESS
    if min_bulk_ess < 50:
        failures.append(f"Hard failure: Min Bulk ESS is {min_bulk_ess:.0f} (< 50).")
        remediations.append("Posterior samples highly autocorrelated. Check adstock lag lengths and increase draws.")
    elif min_bulk_ess < 400:
        warnings.append(f"Caution: Min Bulk ESS is {min_bulk_ess:.0f} (< 400).")

    # 4. Posterior Coverage
    if coverage_94 < 0.50:
        failures.append(f"Hard failure: 94% HDI coverage is {coverage_94*100:.1f}% (< 50%).")
        remediations.append("Model underfits data severely. Check seasonality specification and missing control variables.")
    elif coverage_94 < 0.80:
        warnings.append(f"Caution: 94% HDI coverage is {coverage_94*100:.1f}% (< 80%).")

    # Decision logic
    if failures:
        status = "rejected"
        decision_tools_enabled = False
    elif warnings:
        status = "approved_with_caution"
        decision_tools_enabled = True
    else:
        status = "approved"
        decision_tools_enabled = True

    return {
        "decision_status": status,
        "decision_tools_enabled": decision_tools_enabled,
        "failures": failures,
        "warnings": warnings,
        "recommended_remediations": remediations,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate MCMC diagnostics against statistical gates.")
    parser.add_argument("--divergences", type=int, required=True, help="Number of divergent transitions")
    parser.add_argument("--rhat", type=float, required=True, help="Maximum R-hat across all parameters")
    parser.add_argument("--ess", type=float, required=True, help="Minimum Bulk ESS")
    parser.add_argument("--coverage", type=float, default=0.85, help="94 percent HDI empirical coverage")
    parser.add_argument("--nrmse", type=float, default=0.08, help="Normalized RMSE")
    args = parser.parse_args()

    result = evaluate_gate(
        divergences=args.divergences,
        max_rhat=args.rhat,
        min_bulk_ess=args.ess,
        coverage_94=args.coverage,
        nrmse=args.nrmse,
    )
    print(json.dumps(result, indent=2))
    if result["decision_status"] == "rejected":
        sys.exit(1)


if __name__ == "__main__":
    main()
