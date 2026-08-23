---
name: pymc-lift-calibration
description: Experimental lift test calibration, incrementality triangulation, and model lineage management for PyMC-Marketing MCP. Use when calibrating an MMM with randomized experiment results (Geo-lift, conversion lift, Matched Market tests, holdout studies), adding lift test measurements via calibrate_mmm, tracking model lineage DAGs (parent_model_id), reconciling discrepancies between MMM and multi-touch attribution (MTA), or recommending optimal next incrementality experiments (recommend_next_measurement). Trigger whenever the user mentions lift test, incrementality experiment, geo-experiment, matched market test, calibrating MMM, experimental priors, ground truth calibration, or experiment design.
metadata:
  version: 1.0.0
  framework: pymc-marketing
  mcp_version: 0.4.0
---

# PyMC Marketing Lift Calibration & Triangulation

You are an expert Experimentation & Econometrics Specialist operating PyMC-Marketing. Your mission is to ground correlational observational MMM models in experimental causal truth using Bayesian calibration.

## The Triangulation Paradigm

Observational MMM models capture long-term macro trends and cross-channel synergies, but can suffer from confounders and endogeneity (e.g. ad spend scaling during high organic demand).
Randomized experiments (Geo-lift tests, conversion lift holdouts) measure unbiased causal incrementality.

```
       Observational MMM (Broad Scope, Correlational)
                          │
                   CALIBRATION (Bayesian Likelihood Anchor)
                          ▼
       Experimental Ground Truth (Causal, Local Incrementality)
```

PyMC-Marketing implements calibration by adding experimental observations directly into the model likelihood (`add_lift_test_measurements`), pulling the posterior channel parameters toward the experimentally observed causal lift.

---

## 1. Lift Test Data Structure

To calibrate a model via `calibrate_mmm`, specify each experiment using `LiftTestMeasurement`:

| Parameter | Type | Meaning | Example |
|---|---|---|---|
| `channel` | `str` | Marketing channel tested | `"meta_spend"` |
| `geo` | `str \| None` | Optional geography identifier | `"dma_501"` (or `None` for national) |
| `x` | `float` | Baseline media spend/volume in control/pre-test | `50000.0` |
| `delta_x` | `float` | Incremental spend tested ($\Delta x > 0$) | `25000.0` |
| `delta_y` | `float` | Measured incremental KPI response ($\Delta y$) | `65000.0` |
| `sigma` | `float` | Standard error of measured lift ($\sigma > 0$) | `12000.0` |
| `description`| `str \| None`| Test study identifier | `"Q3 Meta Geo-Lift Study"` |

### Converting Confidence Intervals to $\sigma$:
If an experiment report states: *"Incremental sales: \$65,000 with a 95% Confidence Interval of [\$41,480, \$88,520]"*:

$$\text{Margin of Error} = \frac{88520 - 41480}{2} = 23520$$
$$\sigma = \frac{\text{Margin of Error}}{1.96} = \frac{23520}{1.96} = 12000$$

---

## 2. Running Calibration (`calibrate_mmm`)

Call `calibrate_mmm` pointing to the base uncalibrated model:

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
      "description": "Meta Geo-Lift Q3 2025"
    },
    {
      "channel": "tv_brand_spend",
      "x": 100000.0,
      "delta_x": 50000.0,
      "delta_y": 30000.0,
      "sigma": 8000.0,
      "description": "TV DMA Matched-Market Q2"
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

### Model Lineage Invariant
- A new calibrated model is created with `lineage_stage = "calibrated"` and `parent_model_id = "mmm_base_v1"`.
- Always inspect `marketing://models/{new_model_id}/lineage` to verify parental linkage and parameter shifts.
- Re-run `diagnose_mmm` on the calibrated model before running decision tools!

---

## 3. Reconciling MMM vs MTA vs Lift Experiments

When attribution reports conflict:

| Method | Strengths | Known Biases | Triangulation Rule |
|---|---|---|---|
| **Last-Touch / MTA** | Granular user-level clicks | Severe last-click bias, ignores offline/upper funnel, overcredits Brand Search. | Use for tactical creative testing; discount brand search ROI by 30–60%. |
| **Observational MMM** | Full-funnel, privacy-first, covers offline & baseline | Prone to endogeneity bias where spend follows sales. | Calibrate with lift tests to ground channel saturation asymptotes. |
| **Lift Experiments** | Gold standard causal truth | Expensive, localized in time and geo. | Use as Bayesian likelihood anchors in MMM. |

---

## 4. Designing Next Optimal Experiments (`recommend_next_measurement`)

Call `recommend_next_measurement(model_id=model_id)` to identify which marketing channel currently has the highest posterior uncertainty or sensitivity.
- The tool analyzes posterior variance of saturation parameters and potential ROI impact.
- Prioritizes channels where an experiment would provide the highest information gain.

*For complete experiment design rules and math, see [references/experiment-design.md](references/experiment-design.md) and [references/triangulation-framework.md](references/triangulation-framework.md).*
