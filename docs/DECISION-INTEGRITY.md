# Decision Integrity

## Purpose

The decision layer must answer two separate questions:

1. What does the posterior say about marketing contribution and efficiency?
2. Is the fitted model sufficiently healthy to use for a spend decision?

A successful fit alone is not an approval signal.

## Total and marginal iROAS

`get_incremental_roas` delegates to PyMC-Marketing incrementality methods:

- `contribution_over_spend(frequency="all_time")` for total iROAS
- `marginal_contribution_over_spend(frequency="all_time")` for marginal iROAS

Each returned distribution is summarized with mean, median, 94% interval, and `probability_gt_1`. The MCP does not reconstruct iROAS from an unrelated posterior quantity.

## Scenario simulation

`simulate_budget` does not call the optimizer. It builds the requested allocation and samples the response distribution for:

- the recent historical allocation
- the exact requested scenario

The comparison is draw-wise when the returned posterior arrays are aligned. It reports the posterior distribution of the difference, the probability that the scenario beats baseline, and the median percentage change when the baseline median is non-zero.

## Budget allocation

`optimize_budget` uses PyMC-Marketing's budget optimizer, then samples two response distributions:

- historical channel or cell shares scaled to the requested total budget
- the optimizer's recommended allocation

The recommendation therefore includes both an allocation and evidence about the expected response distribution relative to a concrete baseline.

## Multidimensional allocation contract

For a model with no extra dimensions, allocations remain:

```json
{"meta": 100000, "google": 200000}
```

For `dims=["geo"]`, allocations become explicit cells:

```json
{
  "dimensions": ["geo"],
  "cells": [
    {
      "channel": "meta",
      "dimensions": {"geo": "riyadh"},
      "amount": 100000
    }
  ]
}
```

Every allocation must cover the complete `channel x dims` grid exactly once. Unknown dimensions, unknown values, missing cells, duplicate cells, and negative spend fail closed.

A channel-level scenario change can apply to every dimension cell for that channel. `cell_changes` are then applied to exact cells. Duplicate cell changes are rejected.

For multidimensional optimization, `cell_constraints` must specify every model dimension. Legacy channel-only `min/max/fixed` constraints are rejected for dimensional models because an aggregate constraint cannot be safely translated into per-cell bounds without additional semantics.

## Diagnostic policy

The current decision gate combines:

### Sampler hard failures

- divergences must equal 0
- maximum R-hat must be `<= 1.01`

### Sampler warnings

- minimum bulk ESS below 400
- missing sampler or posterior diagnostic information

### Predictive hard failure

- 94% posterior predictive interval coverage below 50%

### Predictive warnings

- coverage below 80%
- normalized posterior-predictive RMSE above 1.0
- absolute lag-1 residual autocorrelation at or above 0.70
- posterior predictive samples unavailable

These thresholds are product safety policy, not a universal statistical definition of a good MMM. The tool returns the individual metrics and findings so an expert can review them.

## Decision states

```text
hard failure present      -> rejected
warnings but no failures  -> approved_with_caution
no findings               -> approved
```

`simulate_budget` and `optimize_budget` require either `approved` or `approved_with_caution`. `rejected` models fail with `MODEL_NOT_VALIDATED`.

## Not yet treated as hard gates

The following are intentionally left for the next maturity stage rather than being faked with weak heuristics:

- time-slice cross-validation
- prior sensitivity analysis
- posterior parameter stability across refits
- experiment or lift-test calibration
- causal identification review
- extrapolation risk beyond historical support
