---
name: pymc-clv-customer-analytics
version: 3.0.0
description: Use when a user asks about repeat purchase frequency, probability alive, churn, retention, expected spend per order, customer lifetime value, or an affordable acquisition cost.
---
# PyMC CLV Customer Analytics

Estimates how often customers will buy again, whether they are still active, how much they spend per order, and what they are worth over a horizon. PyMC-Marketing's BG/NBD, Shifted Beta-Geometric, and Gamma-Gamma models run on the server. This path is independent of the MMM and its diagnostic gate.

## Entry checks

1. One row per customer, already summarized (RFM format). Duplicate customer IDs fail with `DUPLICATE_CUSTOMER_IDS`.
2. **One dataset for both models.** The purchase and value models must be fitted on the same `dataset_id`; `estimate_customer_lifetime_value` rejects mismatched lineage with `CLV_LINEAGE_MISMATCH`. Put frequency, recency, T, and monetary value in the same file.
3. `list_datasets` to reuse an RFM dataset already on the server.

## Preparing the RFM table

The server fits models on a customer-level summary; it does not summarize transaction logs. Columns (names can differ; map them in the call):

| Column | Meaning |
| --- | --- |
| `customer_id` | Unique customer key |
| `frequency` | Number of **repeat** purchases (total orders minus one) |
| `recency` | BG/NBD: time between the first and the last purchase. Shifted Beta-Geometric: the last period the customer was active (an active subscriber has `recency == T`) |
| `T` | Time between the first purchase and the end of the observation window |
| `monetary_value` | Average value of the repeat purchases |
| `cohort` | Acquisition cohort (needed for the Shifted Beta-Geometric model) |

Use one time unit (days or weeks) for `recency` and `T`, and one currency for `monetary_value`. If the user only has a raw order log, the summary must be built before registering: PyMC-Marketing's `rfm_summary` utility or the user's own pipeline for BG/NBD and Gamma-Gamma. Contractual data for `shifted_beta_geo` is prepared from subscription start, cancellation, and renewal periods; do not run it through `rfm_summary`, which would mark active subscribers as churned. Build it in a code sandbox if you have one, show the method, and never guess values. Register the table through `pymc-dataset-readiness` Step 1.

## Choose the model family

| Business model | Purchase model | Examples |
| --- | --- | --- |
| Customers can buy any time, no contract | `bg_nbd` | E-commerce, food delivery, retail, marketplaces |
| Customers renew or cancel at fixed intervals | `shifted_beta_geo` (needs `cohort_col`) | Subscriptions, memberships, SaaS seats, telecom plans |

Gamma-Gamma (`fit_value_model`) models spend per order for repeat buyers and pairs with a purchase model for CLV.

## Call templates

```json
{"config": {"dataset_id": "<rfm dataset_id>", "customer_id_col": "customer_id", "frequency_col": "frequency",
            "recency_col": "recency", "T_col": "T", "model_type": "bg_nbd"}}
```

```json
{"config": {"dataset_id": "<same rfm dataset_id>", "customer_id_col": "customer_id", "frequency_col": "frequency",
            "monetary_value_col": "monetary_value", "model_type": "gamma_gamma"}}
```

The first goes to `fit_purchase_model`, the second to `fit_value_model`. Keep `purchase_model_id` and `value_model_id` separately in the ledger. Then:

| Question | Tool | Key inputs |
| --- | --- | --- |
| How many orders will each customer place in the next N periods? | `predict_expected_purchases` | `{"config": {"model_id": "<purchase_model_id>", "future_t": 12, "top_n": 100}}` |
| Which customers are still active? | `predict_probability_alive` | `{"config": {"model_id": "<purchase_model_id>", "top_n": 100}}` |
| How much will they spend per order? | `predict_expected_spend` | `{"config": {"model_id": "<value_model_id>", "top_n": 100}}` |
| What is each customer worth? | `estimate_customer_lifetime_value` | `{"config": {"purchase_model_id": "...", "value_model_id": "...", "future_t": 12, "discount_rate": 0.01}}` |
| Who is at risk of churning? | `get_churn_risk_cohorts` (experimental) | `{"model_id": "<purchase_model_id>", "threshold_p_alive": 0.3}` |

- `future_t` uses the same time unit as `recency` and `T` (12 means 12 weeks if the table is in weeks).
- `discount_rate` is per period in that unit. A 10% annual rate on weekly data is roughly 0.0018 per week; confirm the rate with the user.
- `threshold_p_alive` is a business cutoff the user chooses. Report it with the cohorts.

`fit_clv_model` and `predict_customer_clv` are deprecated wrappers. Do not use them for new work.

## Reading the results

- Report model IDs, horizon, discount rate, and the uncertainty or warnings each tool returns.
- P(alive) is a probability that the customer has not silently churned, based on their purchase rhythm. Low values for customers with long gaps are expected behavior.
- CLV here is expected gross value over the horizon (discounted when a rate is given). It measures revenue; it becomes profit only when the user supplies margins.

## Marketing interpretation

- **Segments.** Group customers by CLV and P(alive) for action: high value and active (protect, loyalty perks), high value and fading (win-back now), low value and active (upsell, bundles), low value and fading (low-cost reactivation or none).
- **Affordable CAC.** The server returns CLV; the acquisition ceiling is a business rule the user sets (for example "CAC may not exceed one third of 12-month gross-margin CLV"). Apply only the user's rule, show the formula, and label the result as derived.
- **Retention economics.** A small lift in P(alive) for high-CLV customers is usually worth more than acquiring many low-CLV customers; say it with the numbers the tools return.
- **CLV and MMM.** CLV can inform the value per conversion used in `optimize_flighting.financial` for lead or order targets. Keep media-response cohorts and customer cohorts distinct; they are different populations.

## Stop conditions

Stop when required columns are missing or negative (`MISSING_RFM_COLUMNS`, `INVALID_RFM_DATA`), when purchase and value models come from different datasets, when the model family does not fit the business (contractual data in BG/NBD), or when the user asks for a quantity no tool returns. Never produce CLV, P(alive), or expected spend from prose or formulas.
