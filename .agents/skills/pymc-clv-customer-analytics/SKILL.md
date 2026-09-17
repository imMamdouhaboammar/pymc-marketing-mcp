---
name: pymc-clv-customer-analytics
version: 2.1.0
description: Use when a user asks about purchase frequency, probability alive, churn, expected spend, or customer lifetime value.
---

# PyMC CLV Customer Analytics

Prefer the explicit current tools. `fit_clv_model` and `predict_customer_clv` are deprecated compatibility wrappers and must not be recommended for new work.

## Model families and quantities

- **BG/NBD**: non-contractual repeat-purchase frequency/recency model; use `fit_purchase_model(model_type="bg_nbd")`.
- **Shifted Beta-Geometric**: contractual/cohort retention/churn model; use `fit_purchase_model(model_type="shifted_beta_geo")` with the data fields required by the server.
- **Gamma-Gamma**: transaction monetary-value model; use `fit_value_model`.
- `predict_expected_purchases`: future purchase frequency from a purchase model.
- `predict_probability_alive`: retention/alive probability from a compatible purchase/churn model.
- `predict_expected_spend`: expected transaction value from a value model.
- `estimate_customer_lifetime_value`: combines compatible purchase and value models with the supplied horizon/discount rate.
- `get_churn_risk_cohorts`: server-defined cohort grouping; capability is experimental, so preserve its maturity and threshold assumptions.

Do not mix purchase-model IDs and value-model IDs. Do not invent CLV, P(alive), posterior summaries, or a “maximum CAC” from prose unless a tool actually returns the required quantities and the business formula/inputs are explicitly supplied. Do not impose folklore correlation cutoffs or other Gamma-Gamma checks absent from the current server contract.

Report model IDs, horizon, discount rate, uncertainty/warnings returned by the server, and model-family limitations.
