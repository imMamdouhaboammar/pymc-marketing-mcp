# End-to-End E-Commerce MMM Walkthrough

This walkthrough demonstrates the full lifecycle for an e-commerce brand evaluating marketing spend across channels.

---

### Step 1: Ingest & Inspection
We register the dataset using `register_dataset`:

**Tool Call:**
```json
{
  "tool": "register_dataset",
  "arguments": {
    "file_path": "data/ecommerce_weekly_spend.csv",
    "format": "csv"
  }
}
```
**Tool Response:**
```json
{
  "dataset_id": "ds_ecom_104w",
  "sha256": "8f3b20c918a2456e3b04c8f5d0267329aa28b6d85918e7e29d7249b6b7189190",
  "rows": 104,
  "columns": ["date", "revenue", "meta_spend", "search_spend", "tv_spend", "promo_flag"]
}
```

We inspect the dataset:
**Tool Call:**
```json
{
  "tool": "inspect_dataset",
  "arguments": {"dataset_id": "ds_ecom_104w"}
}
```

---

### Step 2: Validation Gate
We validate column roles and pre-fit requirements:
**Tool Call:**
```json
{
  "tool": "validate_dataset",
  "arguments": {
    "dataset_id": "ds_ecom_104w",
    "date_column": "date",
    "target_column": "revenue",
    "channel_columns": ["meta_spend", "search_spend", "tv_spend"],
    "control_columns": ["promo_flag"],
    "dims": []
  }
}
```
**Tool Response:**
```json
{
  "is_valid": true,
  "findings": []
}
```

---

### Step 3: Model Fitting
We fit the Bayesian MMM with appropriate transformation structure:
**Tool Call:**
```json
{
  "tool": "fit_mmm",
  "arguments": {
    "dataset_id": "ds_ecom_104w",
    "date_column": "date",
    "target_column": "revenue",
    "channel_columns": ["meta_spend", "search_spend", "tv_spend"],
    "control_columns": ["promo_flag"],
    "yearly_seasonality": 2,
    "adstock": {"type": "geometric", "l_max": 8},
    "saturation": {"type": "logistic"},
    "sampler": {
      "draws": 1000,
      "tune": 1000,
      "chains": 4,
      "target_accept": 0.90,
      "random_seed": 42
    }
  }
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_ecom_v1",
  "status": "fitted"
}
```

---

### Step 4: Diagnostic Gate (Mandatory)
Before any downstream interpretation or budget optimization, we evaluate diagnostics:
**Tool Call:**
```json
{
  "tool": "diagnose_mmm",
  "arguments": {"model_id": "mmm_ecom_v1"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_ecom_v1",
  "decision_status": "approved",
  "divergences": 0,
  "max_rhat": 1.004,
  "min_ess": 1120.5,
  "failures": [],
  "warnings": []
}
```

---

### Step 5: Incremental Evidence
With `decision_status: "approved"`, decision-gated tools are unlocked:
**Tool Call:**
```json
{
  "tool": "get_incremental_roas",
  "arguments": {"model_id": "mmm_ecom_v1"}
}
```

---

### Step 6: Artifact Delivery
Results are packaged into posterior plots and executive summaries using `pymc-artifact-delivery`.
