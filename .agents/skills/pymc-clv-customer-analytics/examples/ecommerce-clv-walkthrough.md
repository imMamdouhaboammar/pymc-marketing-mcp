# Walkthrough: E-Commerce Customer Lifetime Value Analysis

This walkthrough demonstrates the end-to-end CLV lifecycle from RFM data conversion to cohort segmentation and CAC ceiling formulation.

---

### Step 1: Convert Transactions to RFM
We use `scripts/rfm_summary.py` to aggregate raw orders into customer-level RFM features.

---

### Step 2: Fit Bayesian Purchase Model (BG/NBD)
**Tool Call:**
```json
{
  "tool": "fit_purchase_model",
  "arguments": {
    "dataset_id": "ds_ecom_rfm",
    "model_type": "bg_nbd",
    "customer_id_column": "customer_id",
    "frequency_column": "frequency",
    "recency_column": "recency",
    "T_column": "T"
  }
}
```
**Tool Response:**
```json
{
  "model_id": "clv_bgnbd_v1",
  "status": "fitted"
}
```

---

### Step 3: Fit Bayesian Value Model (Gamma-Gamma)
**Tool Call:**
```json
{
  "tool": "fit_value_model",
  "arguments": {
    "dataset_id": "ds_ecom_rfm",
    "customer_id_column": "customer_id",
    "frequency_column": "frequency",
    "monetary_value_column": "monetary_value"
  }
}
```
**Tool Response:**
```json
{
  "model_id": "clv_gamma_v1",
  "status": "fitted"
}
```

---

### Step 4: Estimate Discounted 12-Month CLV
**Tool Call:**
```json
{
  "tool": "estimate_customer_lifetime_value",
  "arguments": {
    "purchase_model_id": "clv_bgnbd_v1",
    "value_model_id": "clv_gamma_v1",
    "future_t": 52,
    "discount_rate": 0.01
  }
}
```
**Tool Response:**
```json
{
  "total_portfolio_clv": {
    "median": 2840000.0,
    "hdi_94": [2590000.0, 3120000.0]
  },
  "mean_clv_per_customer": 184.17
}
```

---

### Step 5: Cohort Segmentation
We call `get_churn_risk_cohorts` to export at-risk customers with $P(\text{alive}) < 0.35$ for CRM re-engagement.
