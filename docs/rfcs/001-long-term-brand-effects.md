# RFC 001: Long-Term Brand Effects — Current Prototype and Bayesian VARX Target

- **Status**: Draft / Experimental
- **Date**: 2026-09-18
- **Target seam**: `src/marketing_mcp/domain/long_term/`

## Current executable truth

The current repository implementation is a **deterministic ridge-regularized VARX(1) prototype** named `DeterministicVARLongTermEngine`.

It does not define probabilistic priors, run PyMC sampling, create `InferenceData`, propagate posterior parameter uncertainty, or report posterior diagnostics. Its outputs are therefore descriptive point estimates only and must not be presented as Bayesian evidence.

The engine:

- coerces the selected columns, forms adjacent VARX lag pairs in original row order, then filters incomplete transitions so rows with missing selected values cannot be bridged;
- estimates one VARX(1) coefficient matrix with ridge-regularized least squares;
- marks explosive dynamics as rejected for downstream decision rollup when the maximum transition-matrix eigenvalue is at least 1;
- computes deterministic exogenous impulse-response curves;
- reports a finite-horizon multiplier as cumulative target response divided by contemporaneous target response; and
- refuses to attach deterministic point estimates to decision-grade provenance with `LONG_TERM_UNCERTAINTY_REQUIRED`.

## Current deterministic formulation

For endogenous vector `Y_t` and exogenous media vector `X_t`:

```text
Y_t = c + A Y_(t-1) + B X_t + error_t
```

The current estimator solves a ridge-regularized least-squares system for `A`, `B`, and the intercept. The ridge penalty is a numerical regularizer, **not a Bayesian Minnesota prior**.

### Stability

The transition matrix must satisfy:

```text
max(abs(eigenvalues(A))) < 1
```

A non-stationary result is rejected for downstream rollup.

### Dynamic multiplier

For target response `psi_k(h)` to a unit shock in channel `k` over horizon `H`:

```text
multiplier_k(H) = sum(psi_k(h), h=0..H) / psi_k(0)
```

This ratio may be below 1 when later responses offset the contemporaneous effect. If `psi_k(0)` is effectively zero, the ratio is undefined and the engine fails closed instead of inventing a multiplier.

## Decision-safety boundary

Stationarity alone is not sufficient evidence for a marketing decision. Because this prototype has no posterior distribution, credible interval, R-hat/ESS, divergence evidence, or posterior predictive validation, `rollup_into_decision` refuses all otherwise-stationary deterministic rollups.

A future Bayesian implementation must have its own executable diagnostics and uncertainty contract before long-term effects can modify MMM optimization or other decision-grade outputs.

## Reuse audit

The reuse decision was made against current executable and primary-source evidence, not names or roadmap claims.

| Candidate | Evidence | Decision |
|---|---|---|
| Current repository engine | Direct source inspection shows a NumPy ridge solve and deterministic IRFs; no sampling or posterior object | Keep only as an honestly named descriptive prototype |
| PyMC-Marketing 1.1.0 installed here | Local package inspection found no `VARData`, `VAR`, `MinnesotaPrior`, or `dynamic_multiplier_draws` API | Cannot delegate to the installed release today |
| Current PyMC-Marketing upstream | The current long-term brand-metrics notebook demonstrates Bayesian VARX with `VARData`, `VAR`, `MinnesotaPrior`, NUTS sampling, posterior diagnostics, and posterior dynamic multipliers | Preferred future authority once the supported release/API is available |
| pymc-extras 0.14.0 installed transitively | `BayesianVARMAX` supports endogenous/exogenous state-space models and real PyMC sampling, but the caller must still define priors and the marketing multiplier/diagnostic contract | Viable fallback adapter candidate, not a zero-cost delegation |
| Impulso 0.0.13 | Public package provides PyMC BVAR/VARX, Minnesota priors, posterior IRFs/dynamic multipliers, but explicitly labels itself experimental and under heavy development | Do not add as a dependency in this slice |

Primary references:

- PyMC-Marketing long-term brand metrics notebook: https://github.com/pymc-labs/pymc-marketing/blob/main/docs/source/notebooks/mmm/mmm_brand_metrics_long_term.ipynb
- PyMC-Marketing project documentation: https://www.pymc-marketing.io/en/latest/
- PyMC Extras VARMAX implementation: https://github.com/pymc-devs/pymc-extras/blob/main/pymc_extras/statespace/models/VARMAX.py
- Impulso project: https://github.com/thomaspinder/Impulso

## Bayesian target — not implemented by this RFC revision

The desired decision-grade model remains a Bayesian VARX family with explicit priors, posterior sampling, posterior stability evaluation, uncertainty-bearing dynamic multipliers, convergence diagnostics, and posterior predictive checks.

A Minnesota-style prior may be appropriate, but its exact parameterization must come from the chosen upstream implementation or a separately reviewed scientific design. This repository must not simulate Bayesian maturity by renaming ridge penalties as priors.

## Non-goals of the current refinement

This refinement deliberately does **not**:

- add a second statistical engine;
- add Impulso or another new dependency;
- hand-write a VAR sampler;
- expose a new MCP tool;
- modify budget optimization, portfolio effects, cohort accounting, or prior recommendation; or
- claim that deterministic long-term point estimates are decision-ready.
