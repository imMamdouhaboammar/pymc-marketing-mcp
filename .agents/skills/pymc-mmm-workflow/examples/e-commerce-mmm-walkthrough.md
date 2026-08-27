# End-to-End E-Commerce MMM Walkthrough

This walkthrough demonstrates the full 6-stage lifecycle for an e-commerce retailer evaluating 104 weeks of marketing spend across 4 channels.

---

### Step 1: Ingest & Inspection
We register the CSV data containing weekly observations:

**Tool Call:**
```json
{
  "tool": "register_dataset",
  "arguments": {"path": "data/ecommerce_weekly_spend.csv"}
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

We inspect the dataset to ensure inferred frequency is weekly (`W-MON`) with zero missing date periods:
**Tool Call:**
```json
{
  "tool": "inspect_dataset",
  "arguments": {"dataset_id": "ds_ecom_104w"}
}
```

---

### Step 2: Statistical Validation
We run pre-fit econometric checks:
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
  "status": "valid",
  "checks": {
    "sample_size": {"status": "passed", "n_obs": 104},
    "zero_variance": {"status": "passed"},
    "collinearity": {"status": "passed", "max_vif": 2.1},
    "non_negative_spend": {"status": "passed"}
  }
}
```

---

### Step 3: Model Formulation & Fitting
We configure Geometric adstock for digital channels and Delayed adstock for TV, with Logistic saturation across channels:
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
    "channel_priors": {
      "tv_spend": {
        "adstock": {"type": "delayed", "l_max": 12},
        "saturation": {"type": "hill"}
      }
    },
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
  "status": "fitted",
  "sampling_duration_seconds": 45.2
}
```

---

### Step 4: Diagnostic Gate
We immediately evaluate MCMC health:
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
  "min_ess_bulk": 1120.5,
  "posterior_predictive_coverage": 0.942,
  "warnings": []
}
```
`decision_status: "approved"` confirms that convergence is clean and downstream decision tools are unlocked.

---

### Step 5: Posterior Contributions & iROAS
**Tool Call:**
```json
{
  "tool": "get_incremental_roas",
  "arguments": {"model_id": "mmm_ecom_v1"}
}
```
**Tool Response:**
```json
{
  "channels": {
    "search_spend": {
      "total_iroas": {"median": 3.42, "hdi_94": [2.95, 3.91]},
      "marginal_iroas": {"median": 2.10, "hdi_94": [1.72, 2.48]},
      "prob_profitable": 0.999
    },
    "meta_spend": {
      "total_iroas": {"median": 2.65, "hdi_94": [2.20, 3.12]},
      "marginal_iroas": {"median": 1.75, "hdi_94": [1.38, 2.12]},
      "prob_profitable": 0.995
    },
    "tv_spend": {
      "total_iroas": {"median": 0.85, "hdi_94": [0.45, 1.25]},
      "marginal_iroas": {"median": 0.42, "hdi_94": [0.18, 0.68]},
      "prob_profitable": 0.320
    }
  }
}
```

---

### Step 6: Strategic Delivery
The findings are synthesized into `templates/executive-brief.md` highlighting the strategic reallocation of TV budget into Search and Meta.
