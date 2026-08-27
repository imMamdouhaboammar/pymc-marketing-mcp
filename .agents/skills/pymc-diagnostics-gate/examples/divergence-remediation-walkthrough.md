# Walkthrough: Remediating MCMC Divergences

This walkthrough shows the complete workflow when a model is initially rejected due to MCMC divergences.

---

### Step 1: Initial Diagnosis Returns Rejection
**Tool Call:**
```json
{
  "tool": "diagnose_mmm",
  "arguments": {"model_id": "mmm_initial_v1"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_initial_v1",
  "decision_status": "rejected",
  "divergences": 18,
  "max_rhat": 1.021,
  "min_ess_bulk": 310.4,
  "posterior_predictive_coverage": 0.84,
  "failures": ["Divergences (18) exceed zero-tolerance project threshold"],
  "warnings": ["Bulk ESS is in caution zone (< 400)"]
}
```

---

### Step 2: Agent Halts Decision Tools
Because `decision_status` is `rejected`, the agent informs the user that budget optimization is locked and proposes a remediation refit.

---

### Step 3: Refit with Stepped-Up Sampler Controls
We increase `target_accept` to 0.96 and `tune` to 2000 to eliminate leapfrog integration overshoot:

**Tool Call:**
```json
{
  "tool": "fit_mmm",
  "arguments": {
    "dataset_id": "ds_retail_data",
    "date_column": "date",
    "target_column": "sales",
    "channel_columns": ["meta", "google", "tv"],
    "yearly_seasonality": 2,
    "adstock": {"type": "geometric", "l_max": 8},
    "saturation": {"type": "logistic"},
    "sampler": {
      "draws": 1000,
      "tune": 2000,
      "chains": 4,
      "target_accept": 0.96,
      "random_seed": 42
    }
  }
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_remediated_v2",
  "status": "fitted"
}
```

---

### Step 4: Verification of Gate Passage
**Tool Call:**
```json
{
  "tool": "diagnose_mmm",
  "arguments": {"model_id": "mmm_remediated_v2"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_remediated_v2",
  "decision_status": "approved",
  "divergences": 0,
  "max_rhat": 1.002,
  "min_ess_bulk": 1420.8,
  "posterior_predictive_coverage": 0.915,
  "failures": [],
  "warnings": []
}
```
With `decision_status: "approved"`, the agent unlocks `get_incremental_roas` and `optimize_budget`.
