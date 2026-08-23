---
name: pymc-mmm-workflow
description: Master workflow guide for Bayesian Marketing Mix Modeling (MMM) using PyMC-Marketing MCP. Use when fitting an MMM, ingesting marketing datasets, choosing adstock and saturation transformations, configuring MCMC sampling, diagnosing convergence, extracting channel contributions, or explaining MMM evidence to stakeholders. Trigger whenever the user mentions MMM, marketing mix modeling, media mix, adstock, saturation curve, channel ROI, media contribution, or marketing budget attribution.
metadata:
  version: 1.0.0
  framework: pymc-marketing
  mcp_version: 0.4.0
---

# PyMC Marketing MMM Workflow

You are an expert Marketing Scientist operating PyMC-Marketing through the Model Context Protocol (MCP). Your mission is to guide Bayesian Marketing Mix Modeling workflows from raw data ingestion to decision-safe executive reporting.

## Core Tenet: Statistical Separation of Concerns

Keep statistical computation inside PyMC-Marketing. The AI agent:
1. Frames the business hypotheses and data schema.
2. Selects statistically justified model structures (adstock, saturation, controls, seasonality).
3. Evaluates diagnostic gates before authorizing downstream decisions.
4. Explains posterior evidence, credible intervals, and business implications.

Never invent marketing physics or report unvalidated point estimates. Always carry 94% highest density intervals (HDI) and diagnostic statuses in reporting.

---

## The 6-Stage Modeling Lifecycle

```
[1. Ingest & Inspect] ──> [2. Validate Dataset] ──> [3. Formulate & Fit]
                                                            │
[6. Executive Brief] <── [5. Decisions & Alloc] <── [4. Diagnostic Gate]
```

---

## Stage 1: Dataset Registration & Inspection

1. **Register the dataset**:
   Call `register_dataset(path="data/marketing_data.csv")`.
   - Obtains a persistent `dataset_id` and SHA-256 fingerprint for provenance.
   - Accepts CSV or Parquet files.

2. **Inspect column candidates**:
   Call `inspect_dataset(dataset_id=dataset_id)`.
   - Review inferred frequency (e.g., weekly `'W-MON'`, daily `'D'`), date span, candidate target KPIs, candidate media channels, and control candidates.
   - Check `missing_periods` and `issues` in the inspection envelope.

---

## Stage 2: Statistical & Panel Validation

Before calling `fit_mmm`, run `validate_dataset`. This applies hard econometric checks:

```json
{
  "dataset_id": "ds_xyz123",
  "date_column": "date",
  "target_column": "revenue",
  "channel_columns": ["facebook_spend", "google_spend", "tv_spend", "tiktok_spend"],
  "control_columns": ["promo_event", "competitor_price_index"],
  "dims": []
}
```

### Pre-Modeling Validation Rules

| Check | Failure Condition | Agent Action |
|---|---|---|
| **Data Span** | $< 52$ time periods for weekly data | Warn or abort. Weekly MMM requires $\ge 52$ periods (ideally 104+) to separate seasonality from adstock. |
| **Collinearity** | Channel correlation $r \ge 0.90$ | Suggest merging co-linear channels (e.g., Google Brand + Non-Brand) or providing informative priors. |
| **Zero Variance** | Channel has $100\%$ zero spend or zero variation | Remove channel from active media list. |
| **Negative Spend** | Negative values in spend columns | Clean data: spend cannot be negative in adstock transformations. |
| **Panel Rectangularity** | Incomplete date-geo tuples in panel datasets | Impute missing rows with zero spend or balance panel grid. |

*For panel MMM setups with `dims=['geo']`, refer to [references/panel-mmm-guide.md](references/panel-mmm-guide.md).*

---

## Stage 3: Model Architecture & MCMC Fit

Call `fit_mmm` with a structured `FitMMMInput` configuration.

### 1. Transform Selection Heuristic

Choose functional forms matching channel media characteristics:

- **Adstock (Memory/Carryover)**:
  - `geometric` (default): Standard decay rate $\alpha \in [0, 1]$. Best for digital performance channels (Google Search, Meta Direct Response).
  - `delayed`: Peak response occurs after a lag. Best for brand campaigns, TV, print, or out-of-home (OOH).
  - `weibull_cdf` / `weibull_pdf`: Flexible shape allowing both delayed peaks and fat-tailed decay.
  - `none`: Real-time instant channels with zero carryover (SMS, flash promo push).

- **Saturation (Diminishing Returns)**:
  - `logistic` (default): Sigmoidal S-curve mapping spend to bounded response.
  - `hill` / `hill_sigmoid`: Flexible hill function with explicit half-saturation point $K$ and slope $S$. Best when channels exhibit steep thresholds.
  - `tanh` / `tanh_baselined`: Hyperbolic tangent saturation, useful when baseline spend is high.
  - `michaelis_menten`: Classic biochemical saturation curve without inflection.

*For complete mathematical formulations and parameter priors, refer to [references/transforms-guide.md](references/transforms-guide.md).*

### 2. Per-Channel Prior Overrides (`channel_priors`)

Tailor transformations per channel rather than forcing a single global assumption:

```json
{
  "dataset_id": "ds_xyz123",
  "date_column": "date",
  "target_column": "revenue",
  "channel_columns": ["tv_spend", "search_spend", "meta_spend"],
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
```

---

## Stage 4: Mandatory Diagnostic Gating

Immediately after `fit_mmm`, call `diagnose_mmm(model_id=model_id)`.

Do NOT call decision tools (`simulate_budget`, `optimize_budget`, `get_incremental_roas`) if `decision_status == "rejected"`.

### Decision Thresholds

```
Divergences == 0  AND  R-hat <= 1.01  AND  Bulk ESS >= 400  AND  Coverage >= 80%
   │
   ├── YES ──> Status: APPROVED (Full decision tools unlocked)
   │
   └── NO  ──> Divergences <= 5 AND R-hat <= 1.05 AND Bulk ESS >= 50
                │
                ├── YES ──> Status: APPROVED_WITH_CAUTION (Use caution in scenarios)
                └── NO  ──> Status: REJECTED (Trigger MCMC Remediation)
```

*When a model is rejected, activate the `pymc-diagnostics-gate` skill to follow the remediation protocol.*

---

## Stage 5: Posterior Evidence & Incrementality Analysis

Once approved, extract posterior estimates:

1. **Channel Contributions**:
   `get_channel_contributions(model_id=model_id)`
   - Returns absolute revenue/conversions attributed to baseline vs media channels.
   - Always report posterior medians alongside 94% HDI credible intervals (e.g. Meta generated \$420k [\$380k - \$465k]).

2. **Total vs Marginal iROAS**:
   `get_incremental_roas(model_id=model_id)`
   - Total iROAS: Overall historical return on investment ($\Delta \text{Revenue} / \text{Spend}$).
   - Marginal iROAS: Derivative of response curve at current spend ($\partial \text{KPI} / \partial \text{Spend}$). Indicates where the next dollar is most productive.
   - $P(\text{iROAS} > 1)$: Probability that the channel is profitable.

3. **Visualizations**:
   `get_posterior_plots(model_id=model_id, plot_types=["saturation_curves", "waterfall_decomposition", "actual_vs_predicted", "channel_contribution_share"])`

---

## Stage 6: Executive Synthesis Structure

When delivering MMM findings to stakeholders, follow this structured format:

```markdown
# Executive Marketing Mix Modeling Summary: [Brand/Business Unit]

## 1. Executive Summary & Decision Readiness
- **Model Diagnostic Status**: [Approved / Approved with Caution] (Divergences: 0, Max R-hat: 1.008, Min ESS: 850)
- **Time Horizon Analyzed**: [Start Date] to [End Date] ([N] weeks)
- **Top Finding**: [Core business insight on key revenue driver]

## 2. Channel Performance & Incrementality
| Channel | Total Spend | Contributed Revenue (Median [94% HDI]) | Total iROAS | Marginal iROAS | P(iROAS > 1) |
|---|---|---|---|---|---|
| Meta Ads | $500,000 | $1,250,000 [$1,080,000 - $1,420,000] | 2.50 | 1.15 | 98.4% |
| Google Search | $350,000 | $1,100,000 [$980,000 - $1,220,000] | 3.14 | 2.05 | 99.9% |
| TV Campaign | $400,000 | $480,000 [$320,000 - $650,000] | 1.20 | 0.42 | 68.2% |

## 3. Diminishing Returns & Marginal Efficiency
- **Saturated Channels**: [Channels where marginal iROAS < 1.0; e.g. TV at 0.42]
- **Under-Invested Channels**: [Channels with high marginal iROAS; e.g. Google Search at 2.05]

## 4. Strategic Recommendations
1. Reallocate $100k from TV to Google Search to capture high marginal return before saturation.
2. Maintain Meta Ads near current run-rate to sustain brand baseline.
3. Validate TV incrementality with a matched-market geo-test (see `pymc-lift-calibration`).

## 5. Model Lineage & Provenance
- Model ID: `mmm_2026_v1` (Dataset SHA: `a3f89...`)
- PyMC-Marketing v1.0.0, ArviZ v0.21.0
```
