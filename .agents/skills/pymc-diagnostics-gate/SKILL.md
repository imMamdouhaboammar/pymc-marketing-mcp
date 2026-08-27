---
name: pymc-diagnostics-gate
description: >
  Statistical quality gate and Bayesian MCMC convergence diagnostic guardian for PyMC-Marketing.
  Use when checking model convergence, interpreting MCMC sampler diagnostics (divergences,
  Gelman-Rubin R-hat, effective sample size / ESS, posterior predictive coverage), evaluating
  time-slice cross-validation, assessing prior sensitivity, comparing models via PSIS-LOO / WAIC,
  or remediating rejected models — even if the user does not explicitly say "diagnostics"
  (e.g., "model has divergences", "R-hat too high", "how do I fix MCMC convergence", "why was my
  model rejected", "improve sampler mixing"). Do NOT use for initial dataset registration and
  fitting (use pymc-mmm-workflow) or for optimizing media spend allocations (use pymc-budget-optimization).
version: 2.0.0
pack: marketing-science
inputs:
  - model_id
  - diagnostic_metrics
  - candidate_model_ids
requires:
  - fitted_model_id
produces:
  - diagnostic_decision_status
  - remediation_recommendations
  - model_comparison_ranking
  - prior_sensitivity_report
gates:
  - no_false_certainty
  - unbypassed_hard_gates
fallback: pymc-mmm-workflow
mutatesWorkspace: false
parallelSafe: true
neural_links:
  precursors:
    - pymc-mmm-workflow
    - pymc-lift-calibration
  continuations:
    - pymc-budget-optimization
    - pymc-lift-calibration
  lateral_peers:
    - pymc-clv-customer-analytics
  recovery: pymc-mmm-workflow
---

# PyMC Diagnostics & Statistical Quality Gate

Enforce mathematical and econometric rigor on fitted Bayesian models. Falsify flawed model specifications, identify geometric sampling bottlenecks, and guarantee that no downstream allocation decision is made on unconverged or misleading posterior distributions.

## Runtime Requirements (pre-flight)

Before executing diagnostics or remediation:
- [ ] A fitted model exists and returns a valid `model_id`
- [ ] Sampler traces and posterior predictive samples are stored in the artifact store
- [ ] Initial call to `diagnose_mmm(model_id=model_id)` has returned the diagnostic envelope

---

## When to Use

- User asks to check if an MMM or CLV model has converged
- User encounters divergences, high $\hat{R}$, or low effective sample size (ESS)
- User asks why a model was marked `rejected` or `approved_with_caution`
- User wants to perform model comparison using PSIS-LOO, WAIC, or Bayesian stacking weights
- User wants to run time-slice cross-validation or evaluate sensitivity to prior distributions

## When NOT to Use

- Initial dataset inspection, schema validation, and model fitting → use `pymc-mmm-workflow`
- Budget optimization or scenario simulations on already approved models → use `pymc-budget-optimization`
- Adding experimental lift test evidence to calibrate a model → use `pymc-lift-calibration`

---

## The Decision Gate Policy

The service separates descriptive model inspection from decision-grade operations. Decision-grade tools (`simulate_budget`, `optimize_budget`, `optimize_flighting`, `get_incremental_roas`) are strictly blocked on rejected models.

```text
               ┌─────────────────────────────────┐
               │     diagnose_mmm(model_id)      │
               └────────────────┬────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
  [Clean Passes]         [Caution Signals]       [Hard Failures]
  • Divergences == 0     • 1.01 < R-hat <= 1.05  • Divergences > 0
  • Max R-hat <= 1.01    • 50 <= Bulk ESS < 400  • Max R-hat > 1.05
  • Bulk ESS >= 400      • 50% <= Cov < 80%      • Min Bulk ESS < 50
  • 94% HDI Cov >= 80%   • NRMSE > 1.0           • 94% HDI Cov < 50%
  • NRMSE <= 1.0         • |Autocorr| >= 0.70
         │                      │                      │
         ▼                      ▼                      ▼
  Status: APPROVED       Status: CAUTION        Status: REJECTED
  (Full decisions)       (Decisions unlocked    (Decision tools
                          with visible caveats)  strictly blocked)
```

---

## Procedure

### Step 1: Read the Diagnostic Envelope
1. **Step:** Call `diagnose_mmm(model_id=model_id)`.
   - **Key point:** Inspect `decision_status`, `divergences`, `max_rhat`, `min_ess_bulk`, `min_ess_tail`, and `posterior_predictive_coverage`.
   - **Why:** Establishes whether the posterior distribution represents a valid exploration of the parameter space.

### Step 2: Classify Failure Modes & Select Remediation

| Failure Symptom | Underlying Statistical Cause | Primary Remediation Action |
|---|---|---|
| **Divergences $> 0$** | High posterior curvature (funnel geometry) | Increase `target_accept` to 0.95–0.98; increase `tune` to 2000; check saturation priors. |
| **Max $\hat{R} > 1.05$** | Non-stationary chains; multimodality; flat ridge | Double `tune` and `draws`; reduce Fourier seasonality modes; resolve channel collinearity. |
| **Bulk ESS $< 50$** | High autocorrelation across NUTS steps | Increase `draws`; reparameterize wide priors; verify channel spend variation. |
| **Tail ESS $< 50$** | Insufficient sampling in extreme credible tails | Increase `draws`; check for extreme outliers in target variable. |
| **Coverage $< 50\%$** | Model misspecification; omitted major drivers | Add missing macro controls, promotion flags, or trend components. |
| **Residual Autocorr $\ge 0.70$** | Temporal autocorrelation unmodeled | Increase `yearly_seasonality` modes or add autoregressive controls. |

→ Full mathematical diagnosis: `references/mcmc-troubleshooting.md`

### Step 3: Execute Remediation Refit
1. **Step:** Update model configuration in `fit_mmm`:
   - Increase `target_accept` (e.g. 0.90 to 0.95).
   - Increase warmup `tune` (e.g. 1000 to 2000).
   - Increase `draws` (e.g. 1000 to 2000).
   - Constrain unidentifiable priors in `channel_priors`.
2. **Step:** Refit the model, generating a new `model_id`.
3. **Step:** Call `diagnose_mmm` on the new `model_id` to verify gate passage.
   - → Remediation template: `templates/remediation-checklist.md`

### Step 4: Model Comparison & Selection
When comparing multiple candidate architectures (e.g. Geometric vs Delayed adstock, or different control sets):
1. **Step:** Call `compare_models(model_ids=["mmm_v1", "mmm_v2", "mmm_v3"])`.
   - **Key point:** Evaluates Expected Log Pointwise Predictive Density (elpd_loo) and Bayesian stacking weights.
   - **Why:** Stacking weights find the optimal combination that minimizes out-of-sample prediction error without overfitting.
   - **Warning:** Verify Pareto $k$ values; if $k > 0.7$, LOO estimates for those observations are flagged as unreliable.
   - → Information criteria guide: `references/information-criteria-guide.md`

### Step 5: Temporal Cross-Validation & Prior Sensitivity
1. **Step:** Validate out-of-sample forecasting with time-slice cross-validation:
   Call `cross_validate_mmm(model_id=model_id, n_init=52, forecast_horizon=8, step_size=4)`.
   - Verifies whether parameter estimates remain stable across rolling evaluation splits.
2. **Step:** Assess prior robustness:
   Call `evaluate_prior_sensitivity(model_id=model_id)`.
   - Confirms that channel ROI rankings do not flip under reasonable prior perturbations.

---

## Common Mistakes & Mitigations

| Mistake | Signal | Mitigation |
|---|---|---|
| **Bypassing the Gate** | User asks to optimize budget on a rejected model | Refuse. The tool strictly blocks rejected models. Execute remediation first. |
| **Hiding Caution Warnings** | Presenting an `approved_with_caution` model without caveats | Keep all cautionary flags (e.g. moderate ESS, high NRMSE) visible in output briefs. |
| **Treating LOO as Causal Proof** | Choosing a model purely on LOO score without checking domain validity | LOO measures predictive accuracy, not causal identification. Check sign & sanity of priors. |
| **Infinite Tuning on Flawed Data** | Increasing `draws` to 10,000 on collinear data | If channels are collinear ($r > 0.90$), more draws will not resolve identification; merge channels. |

---

## Decision Rules

- Any divergence ($> 0$) produces immediate rejection in accordance with project decision integrity policy.
- An approved model does not prove causal identification or absence of confounding; interpretations must state assumptions clearly.
- A model selected as "best" via LOO/WAIC must still independently pass `diagnose_mmm` before unlocking decision tools.
- Never invent MCMC metrics or claim convergence without an official `diagnose_mmm` response.

---

## Neural Connections

- **Upstream Precursors:** `pymc-mmm-workflow`, `pymc-lift-calibration`
- **Downstream Continuations:** `pymc-budget-optimization`, `pymc-lift-calibration`
- **Lateral Peers:** `pymc-clv-customer-analytics`
- **Recovery Handler:** `pymc-mmm-workflow`
