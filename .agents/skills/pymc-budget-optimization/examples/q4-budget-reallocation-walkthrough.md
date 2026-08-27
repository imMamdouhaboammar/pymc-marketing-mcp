# Walkthrough: Q4 Budget Reallocation & Flighting

This walkthrough demonstrates allocating a $750k budget across 4 channels using an approved MMM model.

---

### Step 1: Pre-Flight Gate Verification
**Tool Call:**
```json
{
  "tool": "get_model_status",
  "arguments": {"model_id": "mmm_ecommerce_q3_2026"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_ecommerce_q3_2026",
  "decision_status": "approved",
  "diagnostic_summary": {
    "divergences": 0,
    "max_rhat": 1.004,
    "min_ess": 950
  }
}
```

---

### Step 2: Run Constrained Budget Optimization
**Tool Call:**
```json
{
  "tool": "optimize_budget",
  "arguments": {
    "model_id": "mmm_ecommerce_q3_2026",
    "budget": 750000.0,
    "planning_periods": 12,
    "constraints": {
      "search_nonbrand_spend": {"min": 150000.0, "max": 350000.0},
      "meta_spend": {"min": 200000.0, "max": 400000.0},
      "search_brand_spend": {"min": 50000.0, "max": 100000.0},
      "tv_spend": {"min": 50000.0, "max": 150000.0}
    }
  }
}
```
**Tool Response:**
```json
{
  "optimal_allocation": {
    "search_nonbrand_spend": 320000.0,
    "meta_spend": 310000.0,
    "search_brand_spend": 70000.0,
    "tv_spend": 50000.0
  },
  "expected_kpi": {
    "median": 2480000.0,
    "hdi_94": [2210000.0, 2750000.0]
  },
  "baseline_kpi_comparison": {
    "delta_revenue": 290000.0,
    "lift_pct": 13.2
  },
  "warnings": []
}
```

---

### Step 3: Strategic Conclusion
The optimization shifts $100k from Linear TV (bounded at its $50k floor due to low marginal iROAS) into Search Non-Brand and Meta, generating an estimated $290k in incremental revenue (+13.2% lift) for the identical $750k total expenditure.
