# Walkthrough: Calibrating MMM with TV Matched-Market Experiment

This walkthrough demonstrates calibrating an observational MMM using a 6-week matched-market TV experiment.

---

### Step 1: Base Model Diagnosis Verified
Base model `mmm_base_v1` is diagnosed as `approved`. Observational iROAS estimates TV at $1.20, but the marketing team suspects endogeneity.

---

### Step 2: Execute Calibration
We calibrate with the matched-market test results ($\Delta x = $50,000, $\Delta y = $30,000, $\sigma = $8,000):

**Tool Call:**
```json
{
  "tool": "calibrate_mmm",
  "arguments": {
    "model_id": "mmm_base_v1",
    "lift_tests": [
      {
        "channel": "tv_spend",
        "x": 100000.0,
        "delta_x": 50000.0,
        "delta_y": 30000.0,
        "sigma": 8000.0,
        "description": "TV DMA Matched-Market Test"
      }
    ]
  }
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_calibrated_tv_v2",
  "parent_model_id": "mmm_base_v1",
  "lineage_stage": "calibrated",
  "status": "fitted"
}
```

---

### Step 3: Diagnose Calibrated Child Model
**Tool Call:**
```json
{
  "tool": "diagnose_mmm",
  "arguments": {"model_id": "mmm_calibrated_tv_v2"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_calibrated_tv_v2",
  "decision_status": "approved",
  "divergences": 0,
  "max_rhat": 1.003,
  "min_ess_bulk": 1180
}
```

---

### Step 4: Compare Pre vs Post iROAS
**Tool Call:**
```json
{
  "tool": "compare_models",
  "arguments": {"model_ids": ["mmm_base_v1", "mmm_calibrated_tv_v2"]}
}
```
**Tool Response:**
```json
{
  "comparisons": {
    "tv_spend": {
      "base_marginal_iroas": {"median": 1.15, "hdi_94": [0.85, 1.45]},
      "calibrated_marginal_iroas": {"median": 0.62, "hdi_94": [0.45, 0.81]}
    }
  }
}
```
The experimental likelihood anchor corrected the observational over-estimation of TV, pulling marginal iROAS to $0.62 and preventing budget waste in future allocation cycles.
