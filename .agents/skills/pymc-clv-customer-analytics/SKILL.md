---
name: pymc-clv-customer-analytics
description: >
  Model customer lifetime value (CLV), forecast repeat purchase frequency, evaluate churn risk,
  and segment customer cohorts using PyMC-Marketing Buy-'Til-You-Drop (BTYD) models. Use when
  the user asks to predict customer lifetime value, fit BG/NBD or Shifted Beta-Geometric purchase
  models, fit Gamma-Gamma monetary spend models, calculate customer retention probability P(alive),
  identify at-risk customer cohorts, or determine maximum allowable CAC — even if they do not
  explicitly say "CLV" (e.g., "how many repeat orders will our customers make", "which customers
  are about to churn", "estimate customer lifetime value", "RFM customer segmentation"). Do NOT
  use for macro Media Mix Modeling or channel attribution (use pymc-mmm-workflow) or for media
  budget optimization (use pymc-budget-optimization).
version: 2.0.0
pack: marketing-science
inputs:
  - dataset_id
  - model_type
  - customer_id_column
  - frequency_column
  - recency_column
  - T_column
  - monetary_value_column
  - future_t
  - discount_rate
requires:
  - registered_rfm_dataset
produces:
  - fitted_purchase_model
  - fitted_value_model
  - expected_purchases_forecast
  - probability_alive_scores
  - discounted_clv_estimates
  - churn_risk_cohorts
gates:
  - non_negative_rfm_values
  - valid_btyd_model_type
  - gamma_gamma_repeat_frequency_check
fallback: pymc-mmm-workflow
mutatesWorkspace: false
parallelSafe: true
neural_links:
  precursors:
    - fable-research
  continuations:
    - pymc-budget-optimization
  lateral_peers:
    - pymc-mmm-workflow
    - pymc-lift-calibration
  recovery: pymc-mmm-workflow
---

# PyMC Customer Lifetime Value (CLV) & Retention Analytics

Model customer transaction dynamics, estimate individual and cohort lifetime values, and guide retention marketing decisions using PyMC-Marketing's Bayesian Buy-'Til-You-Drop (BTYD) models (BG/NBD, Shifted Beta-Geometric, and Gamma-Gamma).

## Runtime Requirements (pre-flight)

Before executing CLV modeling:
- [ ] Dataset exists in customer-level RFM format (`frequency`, `recency`, `T`, `monetary_value`)
- [ ] Non-contractual repeat purchase setting (e-commerce/retail) or contractual subscription setting
- [ ] For Gamma-Gamma monetary models: customers have frequency $x \ge 1$ and non-zero spend
- [ ] Time units ($t$, $T$, $t_x$) are consistent (e.g., weeks, days, or months)

→ Convert raw transaction logs to RFM format: `scripts/rfm_summary.py`

---

## When to Use

- User asks to predict future purchase frequency or transaction count per customer
- User wants to estimate probability that a customer is still active: $P(\text{alive})$
- User wants to estimate average transaction order value via Bayesian Gamma-Gamma
- User asks to estimate discounted Customer Lifetime Value (CLV) over $N$ months/years
- User wants to group customers into churn-risk cohorts for CRM / email marketing campaigns
- User wants to link customer acquisition cost (CAC) ceilings to Bayesian CLV

## When NOT to Use

- Macro channel media mix modeling, adstock, and saturation → use `pymc-mmm-workflow`
- Media spend allocation and campaign flighting → use `pymc-budget-optimization`
- Geo-experiment lift test calibration → use `pymc-lift-calibration`

---

## The BTYD (Buy-'Til-You-Drop) Paradigm

In non-contractual business settings, customers churn silently without explicit cancellation notices. The BG/NBD model decouples two simultaneous latent processes:
1. **Transaction Process**: While active, customer $i$ makes purchases following a Poisson process with rate $\lambda_i \sim \text{Gamma}(r, \alpha)$.
2. **Dropout Process**: After every transaction, customer $i$ churns with probability $p_i \sim \text{Beta}(a, b)$.

```text
Customer Lifecycle:
Active (Poisson rate λ) ───[ Purchase ]───► Continue Active? (1 - p)
                                    └───► Churned / Inactive (p)
```

---

## Procedure

### Step 1: Select Model Family

| Business Setting | Customer Relationship | Purchase Model Tool | Value Model Tool |
|---|---|---|---|
| **E-Commerce / Retail** | Non-Contractual | `fit_purchase_model(model_type="bg_nbd")` | `fit_value_model(...)` |
| **SaaS / Subscriptions** | Contractual (Discrete periods) | `fit_purchase_model(model_type="shifted_beta_geo")` | Contract ARPU |

### Step 2: Fit the Bayesian Purchase Model
1. **Step:** Call `fit_purchase_model`:
   ```json
   {
     "dataset_id": "ds_rfm_2026",
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
   ```
   - **Key point:** Estimates latent transaction rate $\lambda$ and dropout probability $p$ distributions across the customer population.
   - → Mathematical derivations: `references/btyd-math.md`

### Step 3: Fit the Monetary Value Model (Gamma-Gamma)
1. **Step:** Call `fit_value_model`:
   ```json
   {
     "dataset_id": "ds_rfm_monetary",
     "customer_id_column": "customer_id",
     "frequency_column": "frequency",
     "monetary_value_column": "avg_order_value"
   }
   ```
   - **Independence Invariant:** Gamma-Gamma assumes individual monetary value is independent of transaction frequency. Verify correlation before fitting.

### Step 4: Forecast Repeat Purchases & Active Retention
1. **Step:** Predict future transactions over horizon $t$ (e.g. 52 weeks):
   Call `predict_expected_purchases(model_id="clv_purchase_v1", future_t=52)`.
2. **Step:** Estimate customer retention probability:
   Call `predict_probability_alive(model_id="clv_purchase_v1")`.
   - **Restriction:** $P(\text{alive})$ is valid only for purchase models with alive semantics (`bg_nbd` and `shifted_beta_geo`).

### Step 5: Calculate Discounted Customer Lifetime Value
1. **Step:** Combine purchase and spend models with a continuous discount rate:
   Call `estimate_customer_lifetime_value(purchase_model_id="clv_purchase_v1", value_model_id="clv_value_v1", future_t=52, discount_rate=0.01)`.
   - Returns expected net present value of cash flows per customer over future horizon $t$.
   - → Configuration template: `templates/fit-clv-models-input.json`

### Step 6: Segment Customer Churn-Risk Cohorts
1. **Step:** Call `get_churn_risk_cohorts(model_id="clv_purchase_v1", threshold_p_alive=0.30)`.

| Cohort | Profile | Recommended Marketing Action |
|---|---|---|
| **Champions** | High Historical Spend, $P(\text{alive}) > 0.80$ | VIP loyalty perks, referral incentives, early access. |
| **At Risk (High Value)** | High Historical Spend, $P(\text{alive}) \in [0.20, 0.50]$ | Urgent win-back discount, customer service outreach. |
| **About to Sleep** | Low Frequency, $P(\text{alive}) \in [0.20, 0.50]$ | Automated email re-engagement flow. |
| **Lost / Churned** | $P(\text{alive}) < 0.10$ | Suppress from paid retargeting to eliminate ad waste. |

- → Cohort segmentation guide: `references/cohort-segmentation.md`
- → Customer report template: `templates/clv-segment-report.md`
- → Complete walkthrough: `examples/ecommerce-clv-walkthrough.md`

---

## Common Mistakes & Mitigations

| Mistake | Signal | Mitigation |
|---|---|---|
| **Using Deprecated Wrappers** | Calling `fit_clv_model` or `predict_customer_clv` | Use modern explicit tools: `fit_purchase_model`, `fit_value_model`, `predict_expected_purchases`. |
| **First Purchase Counted in Frequency** | Customer with 1 lifetime order has `frequency=1` | Frequency must represent *repeat* purchases ($x = \text{total orders} - 1$). |
| **Calling P(alive) on Value Models** | Passing a Gamma-Gamma model ID to `predict_probability_alive` | $P(\text{alive})$ is exclusively valid for purchase/churn models (`bg_nbd`, `shifted_beta_geo`). |
| **Ignoring Monetary Independence** | High correlation between order value and frequency | Check correlation in `rfm_summary.py`; if $r > 0.30$, flag Gamma-Gamma assumption violation. |

---

## Decision Rules

- Frequency $x$ must count repeat transactions only ($x \ge 0$).
- $P(\text{alive})$ calls are restricted to purchase models.
- Always report posterior medians alongside 94% HDI credible intervals on customer value.
- Never use customer historical total spend as a proxy for future discounted CLV.

---

## Neural Connections

- **Upstream Precursor:** `fable-research`
- **Downstream Continuations:** `pymc-budget-optimization`
- **Lateral Peers:** `pymc-mmm-workflow`, `pymc-lift-calibration`
- **Recovery Handler:** `pymc-mmm-workflow`
