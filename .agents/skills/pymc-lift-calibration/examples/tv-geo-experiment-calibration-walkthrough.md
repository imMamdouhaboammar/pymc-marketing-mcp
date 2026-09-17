# Walkthrough: Calibrating MMM with Geo-Lift Experiment

This walkthrough demonstrates calibrating an existing MMM model with a matched-market experiment.

---

### Step 1: Base Model Verified
Base model `mmm_base_v1` is diagnosed and approved.

---

### Step 2: Execute Calibration
We calibrate with experiment measurements:
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
Calibration does not inherit approval; the child model must be diagnosed independently:
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
  "min_ess": 1180.0
}
```
