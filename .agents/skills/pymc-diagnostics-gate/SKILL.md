---
name: pymc-diagnostics-gate
version: 2.1.0
description: Use when an MMM has divergences, R-hat or ESS concerns, predictive-check warnings, rejection, or unclear decision status.
---

# PyMC Diagnostics Gate

`diagnose_mmm` is the authority for decision status. Do not replace it with prompt-side threshold arithmetic.

## Current repository policy

The diagnostic engine rejects a model when any persisted hard failure occurs: divergences > 0, maximum R-hat > 1.05, minimum bulk ESS < 50, or 94% posterior-predictive coverage < 0.50 when that predictive check is available. It returns `approved_with_caution` for non-blocking warnings such as R-hat above 1.01 up to 1.05, bulk ESS below 400 but at least 50, predictive coverage below 0.80 but at least 0.50, high normalized RMSE, or strong lag-1 residual autocorrelation. These values are the **current server policy**, not universal statistical thresholds.

## Workflow

1. Confirm model identity/state with `get_model_status` when needed.
2. Call `diagnose_mmm` and preserve `decision_status`, metrics, warnings, and failures.
3. If `rejected`, explain the observed failures and route to model/data remediation. Do not call `get_incremental_roas`, `simulate_budget`, `optimize_budget`, or `optimize_flighting`, and never imitate them with manual arithmetic.
4. If `approved_with_caution`, downstream decision tools are server-enabled, but every material warning stays visible.
5. If `approved`, continue to the requested evidence/validation/decision skill while preserving the distinction between convergence, predictive adequacy, identification, and causal evidence.

Descriptive tools that the server permits on a rejected model may be used to inspect why it failed; label those outputs as non-decision-grade. Increasing `target_accept` or draws may sometimes be relevant, but it is not an automatic cure for misspecification or weak identification.
