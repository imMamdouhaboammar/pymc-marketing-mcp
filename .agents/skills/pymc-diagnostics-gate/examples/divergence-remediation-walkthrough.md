# Walkthrough: Remediating MCMC Divergences

This walkthrough demonstrates the workflow when an initial model fit encounters divergences and is remediated.

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
  "divergences": 14,
  "max_rhat": 1.021,
  "min_ess": 310.0,
  "failures": ["Sampler had 14 divergent transition(s)"]
}
```

---

### Step 2: Decision Tools Locked
Because `decision_status` is `rejected`, downstream decision tools (`get_incremental_roas`, `optimize_budget`) are blocked. The agent explains the rejection and plans a refit.

---

### Step 3: Refit with Stepped-Up Sampler Controls
We increase `target_accept` to 0.95 and `tune` to 2000:

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
      "target_accept": 0.95,
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

### Step 4: Re-Diagnosis Confirms Gate Passage
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
  "min_ess": 1240.0,
  "failures": [],
  "warnings": []
}
```
With `decision_status: "approved"`, decision-gated tools are unlocked.
