# Decision Integrity

This document describes the current decision-safety contract implemented around PyMC-Marketing outputs

The goal is not to label every posterior output as safe for action. The service separates descriptive model evidence from decision-grade operations and blocks the latter when diagnostics reject the model

<!-- drift-check: decision-gated-tools = optimize_budget, optimize_flighting, simulate_budget -->

## Decision states

A fitted MMM is not automatically decision-ready

`diagnose_mmm` evaluates sampler and posterior-predictive evidence and persists one of the decision states used by the decision service

- `approved`: decision-grade tools may run
- `approved_with_caution`: decision-grade tools may run but warnings/caveats must remain visible
- `rejected`: decision-grade tools are blocked

## Current hard rejection rules

The current diagnostic engine rejects decision use when any hard failure is present

- divergences greater than 0
- maximum R-hat greater than 1.05
- minimum effective sample size below 50
- posterior-predictive coverage below 0.50

These are project decision-policy thresholds. They are not claimed as universal scientific cutoffs

## Current caution rules

The model may be approved with caution when hard rejection is absent but weaker evidence exists, including

- maximum R-hat greater than 1.01 and at most 1.05
- minimum ESS below 400 but at least 50
- posterior-predictive coverage below 0.80 but at least 0.50
- normalized posterior-predictive RMSE above 1.0
- absolute lag-1 residual autocorrelation at or above 0.70

Warnings must be surfaced to the user rather than hidden by the agent or tool wrapper

## Decision-gated tools

The current decision service requires an approved or approved-with-caution model before

- `get_incremental_roas`
- `simulate_budget`
- `optimize_budget`
- `optimize_flighting`

`get_incremental_roas` is gated because total/marginal incrementality is intended to support allocation decisions rather than function as an unrestricted descriptive statistic

## Descriptive outputs

The following evidence may be available for diagnosis/inspection even when a model is rejected

- channel contributions
- response-curve information
- diagnostics and model status
- plots where the underlying artifact is available

A rejected model must remain clearly labeled as rejected. Descriptive access does not convert the model into a valid decision model

## Incrementality contract

Total iROAS and marginal iROAS are delegated to the PyMC-Marketing incrementality APIs

The server must not replace model-dependent incrementality with an LLM calculation or a simple spend/revenue division

Marginal iROAS is the relevant quantity when the question is about the next unit of spend. Average/total return must not be presented as a substitute for marginal response

## Scenario contract

`simulate_budget` evaluates the scenario requested by the caller against the fitted model baseline

The optimizer must not be silently used as a substitute for counterfactual evaluation

Scenario outputs include posterior uncertainty and extrapolation caveats when the requested spend moves materially beyond observed support

## Optimization contract

`optimize_budget` and `optimize_flighting` must

- honor the requested total budget
- honor explicit lower/upper constraints
- report infeasible constraints rather than silently relaxing them
- evaluate the recommended allocation through the model response path
- preserve posterior uncertainty and warnings
- keep model/dataset/configuration provenance

Dynamic flighting additionally accounts for time/carryover semantics covered by the statistical flighting tests

## Calibration and lineage

Lift-test calibration creates a child model in the model lineage rather than mutating the parent model artifact in place

The calibrated child must be diagnosed before it is used for decision-grade outputs. Parent/child model identity and dataset fingerprint remain part of provenance

## Model comparison integrity

Models used in comparison must satisfy compatibility requirements such as dataset identity/fingerprint and supported criterion semantics

A model selected by LOO/WAIC/stacking is not automatically decision-ready if its own diagnostic gate is rejected

## What the gate does not prove

A diagnostic approval does not prove

- causal identification is correct
- all confounders were controlled
- the model specification is complete
- historical channel variation is sufficient for every decision
- an extrapolated spend level will behave like the modeled region
- external experiments are unbiased

Those assumptions must stay explicit in interpretations

## Agent rule

No agent skill, user instruction or dashboard action may bypass the persisted diagnostic decision state

A request such as "optimize anyway" or "hide the warning" must not weaken the tool-level gate
