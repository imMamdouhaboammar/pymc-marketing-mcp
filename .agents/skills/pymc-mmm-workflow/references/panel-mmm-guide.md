# Multi-Dimensional Panel MMM Guide

When marketing data is available across granular dimensions (e.g. Geographic Designated Market Areas [DMAs], states, countries, product categories, or retail channels), Panel MMM pools statistical power across units while estimating unit-specific parameters.

---

## 1. Why Panel MMM?

National aggregate MMM models often suffer from small sample sizes (e.g. 104 weekly observations over 2 years).
Panel MMM expands sample size by $G \times T$ (e.g. 50 DMAs $\times$ 104 weeks = 5,200 observations), enabling:
- Disentangling media effects from macroeconomic trends.
- Estimating regional baseline differences.
- More precise posterior estimates with tighter credible intervals.

---

## 2. Rectangular Panel Invariant

PyMC-Marketing requires **rectangular panels**. Every cross-sectional unit must have an entry for every timestamp in the dataset.

$$\text{Total Rows} = N_{\text{dates}} \times N_{\text{dims}_1} \times \dots \times N_{\text{dims}_k}$$

### Common Violations & Solutions:
1. **Missing Geo-Date Rows**: If a DMA had zero sales in a given week, the row is missing rather than containing $0$.
   - *Fix*: Reindex the DataFrame using `pd.MultiIndex.from_product([dates, geos])` and fill missing sales/spend with $0.0$.
2. **Unbalanced Geographies**: New markets launched halfway through the observation window.
   - *Fix*: Filter analysis to continuous operating markets, or impute pre-launch periods with zero revenue and zero spend.

---

## 3. Configuring Panel MMM in MCP

In `validate_dataset` and `fit_mmm`, specify the dimension columns in `dims`:

```json
{
  "dataset_id": "ds_panel_dma",
  "date_column": "week_start",
  "target_column": "sales_units",
  "channel_columns": ["tv_grp", "digital_impressions", "local_radio_spend"],
  "control_columns": ["unemployment_rate", "avg_temperature"],
  "dims": ["dma"],
  "sampler": {
    "draws": 1000,
    "tune": 1000,
    "chains": 4,
    "target_accept": 0.92
  }
}
```

---

## 4. Multi-Level Hierarchical Shrinkage

In panel models, PyMC-Marketing applies Bayesian hierarchical shrinkage:
- Individual geo parameters $\beta_{c, g}$ are drawn from a shared national distribution:
  $$\beta_{c, g} \sim \text{HalfNormal}(\mu_c, \sigma_c)$$
- Markets with low spend or high noise shrink toward the national mean $\mu_c$.
- Markets with high spend and clean data maintain distinct local response estimates.
