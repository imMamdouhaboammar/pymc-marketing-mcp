# Walkthrough: Budget Reallocation & Optimization

This walkthrough demonstrates allocating a budget across channels using an approved MMM model.

---

### Step 1: Pre-Flight Gate Verification
Confirm the model is diagnosed and approved:
**Tool Call:**
```json
{
  "tool": "get_model_status",
  "arguments": {"model_id": "mmm_retail_v1"}
}
```
**Tool Response:**
```json
{
  "model_id": "mmm_retail_v1",
  "decision_status": "approved"
}
```

---

### Step 2: Run Constrained Budget Optimization
**Tool Call:**
```json
{
  "tool": "optimize_budget",
  "arguments": {
    "model_id": "mmm_retail_v1",
    "budget": 500000.0,
    "planning_periods": 8,
    "constraints": {
      "meta_spend": {"min": 100000.0, "max": 250000.0},
      "search_spend": {"min": 150000.0, "max": 300000.0},
      "tv_spend": {"min": 50000.0, "max": 150000.0}
    }
  }
}
```
**Tool Response:**
```json
{
  "optimal_allocation": {
    "search_spend": 220000.0,
    "meta_spend": 210000.0,
    "tv_spend": 70000.0
  },
  "expected_kpi": {
    "median": 1650000.0,
    "hdi_94": [1480000.0, 1820000.0]
  },
  "warnings": []
}
```
