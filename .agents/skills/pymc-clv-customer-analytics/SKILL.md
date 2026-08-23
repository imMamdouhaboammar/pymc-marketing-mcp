---
name: pymc-clv-customer-analytics
description: Bayesian Customer Lifetime Value (CLV), repeat purchase forecasting, churn risk cohort segmentation, and RFM customer analytics for PyMC-Marketing MCP. Use when fitting BG/NBD models (repeat transaction frequency in non-contractual business), Gamma-Gamma models (spend per transaction), or Shifted Beta-Geometric models (subscription/contractual churn), estimating customer alive probability P(alive), forecasting future transactions over horizon future_t, identifying at-risk customer cohorts via get_churn_risk_cohorts, or calculating Customer Acquisition Cost (CAC) payback against Bayesian CLV. Trigger whenever the user mentions CLV, customer lifetime value, RFM, repeat purchase rate, BG/NBD, Gamma-Gamma, churn risk cohort, customer retention probability, P(alive), or customer equity.
metadata:
  version: 1.0.0
  framework: pymc-marketing
  mcp_version: 0.4.0
---

# PyMC Marketing Customer Lifetime Value (CLV) & Retention

You are an expert Customer Analytics & Quantitative Retention Specialist operating PyMC-Marketing. Your objective is to model customer purchase behavior, estimate individual and cohort lifetime values, and guide retention marketing decisions.

## The BTYD (Buy-'Til-You-Drop) Paradigm

In non-contractual settings (e.g. e-commerce, retail), customers do not explicitly notify a company when they churn. The BG/NBD model separates two latent processes:
1. **Transaction Process**: While active, a customer makes purchases according to a Poisson process with rate $\lambda$.
2. **Dropout Process**: After any transaction, a customer drops out (churns) with probability $p$.

```
Customer Lifecycle:
Active (Poisson rate λ) ───[ Purchase ]───> Continue Active? (1 - p)
                                    └───> Churn / Inactive (p)
```

---

## 1. Model Architecture Selection Matrix

| Business Model | Customer Relationship | Recommended Model (`model_type`) | Key Columns Required |
|---|---|---|---|
| **E-Commerce / Retail** | Non-Contractual | `bg_nbd` | `customer_id`, `frequency`, `recency`, `T` |
| **Transaction Spend / AOV** | Non-Contractual (Monetary) | `gamma_gamma` | `customer_id`, `frequency`, `recency`, `T`, `monetary_value` |
| **SaaS / Subscriptions** | Contractual (Discrete periods) | `shifted_beta_geo` | `customer_id`, `frequency`, `recency`, `T` |

---

## 2. RFM Data Schema Requirements

Before calling `fit_clv_model`, ensure the registered dataset contains standard RFM fields:

- `customer_id`: Unique identifier for each customer.
- `frequency` ($x$): Number of **repeat** purchases observed in the calibration period ($x \ge 0$). First purchase is $t=0$.
- `recency` ($t_x$): Time from customer's first purchase to their most recent purchase.
- `T`: Total observation duration from first purchase to the study end date ($T \ge t_x$).
- `monetary_value` ($m_x$): Average spend across repeat purchases (required for `gamma_gamma`).

*To convert raw transaction logs to RFM format, see [scripts/rfm_summary.py](scripts/rfm_summary.py).*

---

## 3. Fitting Bayesian CLV Models (`fit_clv_model`)

### A. Fitting Repeat Purchase Frequency (`bg_nbd`)

```json
{
  "dataset_id": "ds_rfm_customers",
  "config": {
    "model_type": "bg_nbd",
    "customer_id_column": "customer_id",
    "frequency_column": "frequency",
    "recency_column": "recency",
    "T_column": "T",
    "sampler": {
      "draws": 1000,
      "tune": 1000,
      "chains": 4,
      "target_accept": 0.90
    }
  }
}
```

### B. Fitting Spend Value (`gamma_gamma`)

Requires customers with $x \ge 1$ repeat purchases and non-zero `monetary_value_column`.

```json
{
  "dataset_id": "ds_rfm_monetary",
  "config": {
    "model_type": "gamma_gamma",
    "customer_id_column": "customer_id",
    "frequency_column": "frequency",
    "recency_column": "recency",
    "T_column": "T",
    "monetary_value_column": "avg_order_value"
  }
}
```

---

## 4. Generating Predictions (`predict_customer_clv`)

Forecast future customer transactions and retention probability over a horizon $t$:

```json
{
  "model_id": "clv_bgnbd_v1",
  "future_t": 12,
  "top_n_customers": 500
}
```

### Key Output Metrics:
- `p_alive`: Posterior probability $P(\text{alive} \mid x, t_x, T)$ that the customer is currently active.
- `expected_purchases`: Expected number of transactions during the future $t$ periods.
- `expected_customer_value`: Forecasted monetary contribution (when combined with Gamma-Gamma).

---

## 5. Identifying Churn Risk Cohorts (`get_churn_risk_cohorts`)

Segment customers who were previously frequent buyers but have a dropping $P(\text{alive})$:

```json
{
  "model_id": "clv_bgnbd_v1",
  "threshold_p_alive": 0.30
}
```

### Retention Playbook:
- **High-Value At Risk** ($P(\text{alive}) \in [0.20, 0.40]$, High Historical Spend): Trigger win-back email sequence, personalized promotional discounts, or dedicated account manager outreach.
- **Lost Customers** ($P(\text{alive}) < 0.10$): Cease expensive paid retargeting; suppress from digital ad audiences to avoid ad spend waste.
- **Active Loyalists** ($P(\text{alive}) > 0.80$): Enroll in VIP loyalty tiers and referral programs.

---

## 6. Linking CLV with MMM (CAC Payback)

Use CLV estimates to set rational acquisition cost ceilings in MMM budget optimizations:

$$\text{Max Allowable CAC} = \text{Bayesian 12-Month CLV} \times \text{Gross Margin} \times \text{Target Profit Margin}$$

*For mathematical derivations and cohort playbooks, see [references/btyd-math.md](references/btyd-math.md) and [references/cohort-segmentation.md](references/cohort-segmentation.md).*
