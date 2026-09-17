# Walkthrough: E-Commerce Customer Lifetime Value Analysis

This walkthrough demonstrates CLV analysis from RFM data to cohort evaluation.

---

### Step 1: Convert Transactions to RFM
We use `scripts/rfm_summary.py` to aggregate raw orders into customer-level RFM features (`frequency`, `recency`, `T`, `monetary_value`).

---

### Step 2: Fit Purchase Model (BG/NBD)
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

---

### Step 3: Fit Value Model (Gamma-Gamma)
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

---

### Step 4: Estimate Discounted CLV
Estimate portfolio and customer-level expected future value over the planning horizon.
