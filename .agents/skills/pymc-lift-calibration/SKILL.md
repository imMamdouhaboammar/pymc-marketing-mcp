---
name: pymc-lift-calibration
description: >
  Calibrate Bayesian Media Mix Models with experimental lift tests, geo-experiments,
  and holdout studies in PyMC-Marketing. Use when incorporating randomized experiment
  results into an observational MMM, reconciling attribution discrepancies between MMM
  and MTA, managing parent-child model lineage chains, evaluating parameter shifts post-calibration,
  or recommending optimal next incrementality experiments — even if the user does not
  explicitly say "calibration" (e.g., "add geo-test results to our MMM", "our TV lift test showed
  2.3x ROI", "calibrate model with holdout study", "reconcile MMM with incrementality tests").
  Do NOT use for initial uncalibrated MMM model fitting (use pymc-mmm-workflow) or for MCMC
  divergence diagnosis (use pymc-diagnostics-gate).
version: 2.0.0
pack: marketing-science
inputs:
  - model_id
  - lift_tests
  - sampler_config
requires:
  - fitted_parent_model_id
  - validated_lift_test_measurements
produces:
  - calibrated_child_model_id
  - model_lineage_record
  - pre_post_iroas_comparison
  - parameter_shift_analysis
gates:
  - positive_incremental_spend
  - positive_standard_error
  - child_model_diagnosed
fallback: pymc-diagnostics-gate
mutatesWorkspace: false
parallelSafe: true
neural_links:
  precursors:
    - pymc-mmm-workflow
    - pymc-diagnostics-gate
  continuations:
    - pymc-diagnostics-gate
    - pymc-budget-optimization
  lateral_peers:
    - pymc-clv-customer-analytics
  recovery: pymc-diagnostics-gate
---

# PyMC Marketing Lift Calibration & Triangulation

Anchor observational Bayesian Media Mix Models in experimental causal ground truth. Incorporate randomized incrementality measurements (Geo-lift tests, conversion holdouts, matched-market experiments) directly into the PyMC-Marketing model likelihood, track immutable parent-child model lineage, and resolve multi-touch attribution (MTA) discrepancies.

## Runtime Requirements (pre-flight)

Before executing model calibration:
- [ ] A fitted parent model exists with a verified `model_id`
- [ ] Experimental test has non-negative incremental spend ($\Delta x > 0$)
- [ ] Measured incremental response ($\Delta y$) and standard error ($\sigma > 0$) are documented
- [ ] Test duration, target geography, and conversion windows are validated

---

## When to Use

- User wants to calibrate an existing MMM model with results from a geo-lift test or holdout experiment
- User provides experimental lift numbers (e.g. "We ran a Facebook conversion lift study showing $65k lift")
- User needs to reconcile differences between observational MMM and platform click attribution
- User asks which marketing channel to test next using `recommend_next_measurement`
- User wants to inspect or compare parent vs child model lineage

## When NOT to Use

- Initial uncalibrated dataset inspection and model fitting → use `pymc-mmm-workflow`
- Allocating budget on an already calibrated and diagnosed model → use `pymc-budget-optimization`
- Remediating MCMC convergence failures on parent or child models → use `pymc-diagnostics-gate`

---

## The Triangulation Paradigm

Observational MMM captures macro seasonality and cross-channel interactions but can suffer from endogeneity (e.g. ad spend ramping during organic sales surges). Lift experiments provide unbiased local causal truth. Calibration adds experimental evidence into the Bayesian likelihood, shrinking posterior response curves toward experimental truth.

```text
  Observational MMM (Broad Scope, Correlational)
                         │
                  CALIBRATION (Bayesian Likelihood Anchor)
                         ▼
  Experimental Ground Truth (Causal, Local Incrementality)
```

---

## Procedure

### Step 1: Validate Experimental Evidence
1. **Step:** Convert reported confidence intervals into standard error ($\sigma$):
   $$	ext{Margin of Error} = rac{	ext{CI}_{	ext{upper}} - 	ext{CI}_{	ext{lower}}}{2}, \quad \sigma = rac{	ext{Margin of Error}}{1.96}$$
   - **Key point:** Verify that test markets were balanced and uncontaminated by concurrent outlier campaigns.
   - **Why:** Noisy or biased experiments propagate false certainty into the Bayesian posterior.
   - → Experiment design guide: `references/experiment-design.md`

### Step 2: Structure Lift Test Input Payload
1. **Step:** Construct the `LiftTestMeasurement` objects:
   ```json
   {
     "model_id": "mmm_base_v1",
     "lift_tests": [
       {
         "channel": "meta_spend",
         "x": 50000.0,
         "delta_x": 25000.0,
         "delta_y": 65000.0,
         "sigma": 12000.0,
         "description": "Meta Geo-Lift Q3 2026"
       }
     ],
     "sampler": {
       "draws": 1000,
       "tune": 1000,
       "chains": 4,
       "target_accept": 0.92
     }
   }
   ```
   - → Calibration template: `templates/lift-test-input.json`
   - → Pre-calibration checklist: `templates/calibration-checklist.md`

### Step 3: Execute Calibration (`calibrate_mmm`)
1. **Step:** Call `calibrate_mmm(...)`.
   - **Key point:** Generates a new child model (e.g. `mmm_calibrated_v2`) with `parent_model_id = "mmm_base_v1"`.
   - **Lineage Invariant:** Calibration never mutates the parent model in place. The parent artifact and provenance remain immutable.

### Step 4: Mandatory Diagnostic Gating of Calibrated Child
1. **Step:** Immediately call `diagnose_mmm(model_id=new_model_id)`.
   - **Key point:** Parent diagnostic approval does NOT automatically transfer to the child. The child must pass the gate independently.
   - **Why:** Adding experimental likelihood terms can alter the posterior geometry, occasionally introducing divergences.

### Step 5: Compare Parent vs Child Lineage
1. **Step:** Call `compare_models(model_ids=["mmm_base_v1", "mmm_calibrated_v2"])`.
   - Inspect parameter shifts in saturation half-points ($K$) and iROAS rankings.
   - Evaluate whether observational over-crediting of high-intent channels has been corrected.
   - → Complete walkthrough: `examples/tv-geo-experiment-calibration-walkthrough.md`

### Step 6: Recommend Next Incrementality Measurement
1. **Step:** When asked which channel to experiment on next, call `recommend_next_measurement(model_id=model_id)`.
   - Identifies channels with the widest posterior saturation uncertainty where experimental evidence will deliver the highest information gain.

---

## Common Mistakes & Mitigations

| Mistake | Signal | Mitigation |
|---|---|---|
| **Skipping Child Diagnosis** | Proceeding to budget optimization immediately after calibration | Always run `diagnose_mmm` on the child model ID before calling decision tools. |
| **Negative Delta Spend** | Submitting $\Delta x \le 0$ in lift test payload | Ensure $\Delta x > 0$ representing actual incremental spend tested. |
| **Confusing Standard Error with Variance** | Entering $\sigma^2$ instead of $\sigma$ in `sigma` field | Double-check formula: $\sigma = 	ext{Standard Error} = 	ext{Margin of Error} / 1.96$. |
| **Over-Constraining with Tiny $\sigma$** | Artificially setting $\sigma pprox 0$ to force model to match test | Use empirical standard error; zero variance breaks MCMC sampling geometry. |

---

## Decision Rules

- Calibration must preserve parent-child lineage; never attempt to overwrite parent model state.
- All calibrated models must be independently diagnosed before downstream decision tools are unlocked.
- Always report pre-calibration vs post-calibration channel iROAS shifts to verify econometric plausibility.

---

## Neural Connections

- **Upstream Precursors:** `pymc-mmm-workflow`, `pymc-diagnostics-gate`
- **Downstream Continuations:** `pymc-diagnostics-gate`, `pymc-budget-optimization`
- **Lateral Peers:** `pymc-clv-customer-analytics`
- **Recovery Handler:** `pymc-diagnostics-gate`
