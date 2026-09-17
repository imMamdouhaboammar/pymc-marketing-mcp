#!/usr/bin/env python3
"""Evaluate MCMC diagnostic metrics against PyMC-Marketing decision gates.

Outputs decision status (approved, caution, rejected) and concrete remediation instructions.
"""

from __future__ import annotations

import argparse
import json
import sys


def evaluate_gate(
    divergences: int,
    max_rhat: float,
    min_bulk_ess: float,
) -> dict:
    failures = []
    warnings = []
    remediations = []

    # 1. Divergences
    if divergences > 0:
        failures.append(f"Hard failure: {divergences} divergent transition(s) detected.")
        remediations.append("Increase target_accept from 0.90 to 0.95 or 0.98. Increase tune to 2000.")

    # 2. R-hat
    if max_rhat > 1.05:
        failures.append(f"Hard failure: Max R-hat is {max_rhat:.3f} (> 1.05).")
        remediations.append("Chains have not converged. Check for multicollinearity or increase draws/tune.")
    elif max_rhat > 1.01:
        warnings.append(f"Caution: Max R-hat is {max_rhat:.3f} (1.01-1.05).")
        remediations.append("Consider increasing draws to 2000 for chain stabilization.")

    # 3. Bulk ESS
    if min_bulk_ess < 100:
        failures.append(f"Hard failure: Min Bulk ESS is {min_bulk_ess:.0f} (< 100 critical floor).")
        remediations.append("Samples are highly autocorrelated. Check adstock lag lengths and increase draws.")
    elif min_bulk_ess < 400:
        warnings.append(f"Caution: Min Bulk ESS is {min_bulk_ess:.0f} (< 400 recommended).")

    # Decision logic
    if failures:
        status = "rejected"
        decision_tools_enabled = False
    elif warnings:
        status = "caution"
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
    args = parser.parse_args()

    result = evaluate_gate(
        divergences=args.divergences,
        max_rhat=args.rhat,
        min_bulk_ess=args.ess,
    )
    print(json.dumps(result, indent=2))
    if result["decision_status"] == "rejected":
        sys.exit(1)


if __name__ == "__main__":
    main()
