---
name: pymc-mmm-workflow
description: >
  Execute the full 6-stage Bayesian Media Mix Modeling lifecycle with PyMC-Marketing.
  Use when the user wants to measure marketing channel contributions, calculate total
  or marginal incremental ROAS, fit an MMM model, evaluate advertising carryover and
  saturation, or formulate media mix strategies — even if they don't explicitly say
  "MMM" (e.g., "how much did TV contribute", "which channel has the highest ROI",
  "build a media mix model", "analyze marketing effectiveness"). Do NOT use for customer
  lifetime value or churn prediction (use pymc-clv-customer-analytics) or for diagnosing
  failing MCMC samplers (use pymc-diagnostics-gate).
version: 2.0.0
pack: marketing-science
inputs:
  - dataset_id_or_path
  - target_column
  - channel_columns
  - date_column
  - control_columns
requires:
  - registered_dataset
  - validated_panel_structure
produces:
  - fitted_mmm_model
  - diagnostic_status
  - channel_contributions
  - incremental_roas
  - executive_brief
gates:
  - dataset_validation_passed
  - diagnostic_gate_approved
fallback: pymc-diagnostics-gate
mutatesWorkspace: false
parallelSafe: true
neural_links:
  precursors:
    - fable-research
  continuations:
    - pymc-diagnostics-gate
    - pymc-budget-optimization
    - pymc-lift-calibration
  lateral_peers:
    - pymc-clv-customer-analytics
  recovery: pymc-diagnostics-gate
---

# PyMC Media Mix Modeling (MMM) Workflow

Execute the full 6-stage Bayesian Media Mix Modeling lifecycle using PyMC-Marketing. Translate raw marketing expenditure and business KPI data into causal, uncertainty-calibrated revenue contributions, incremental ROAS (iROAS), and strategic recommendations.

## Runtime Requirements (pre-flight)

Before executing any modeling steps, verify context readiness:
- [ ] Dataset exists in allowed ingest directory (`.csv` or `.parquet`)
- [ ] Time span contains $\ge 52$ weekly periods (or equivalent daily/monthly span)
- [ ] Target KPI is numeric (revenue, conversions, new accounts)
- [ ] Channel spend columns are non-negative with observable historical variation
- [ ] Control variables (macro indicators, promotions, seasonality) are identified

→ Full pre-flight data checks and script: `scripts/dataset_precheck.py`

---

## When to Use

- User asks to estimate revenue or conversion attribution across advertising channels
- User wants to calculate historical or marginal incremental ROAS (iROAS)
- User needs to evaluate ad carryover (adstock) and diminishing returns (saturation)
- User asks "how much revenue did Meta/Google/TV drive last quarter?"
- User wants to configure, fit, or evaluate a Bayesian Media Mix Model

## When NOT to Use

- Customer retention, repeat purchase rate, or CLV estimation → use `pymc-clv-customer-analytics`
- Resolving MCMC divergences, high R-hat, or sampler failure → use `pymc-diagnostics-gate`
- Scenario simulation or budget optimization on an already diagnosed model → use `pymc-budget-optimization`
- Adding geo-experiment lift test calibration to an existing model → use `pymc-lift-calibration`

---

## Core Tenet: Statistical Separation of Concerns

All model-dependent quantities (adstock parameters, saturation thresholds, channel contributions, iROAS, credible intervals) are computed strictly by PyMC-Marketing and ArviZ. The agent frames the problem, validates data integrity, selects transformation families, enforces diagnostic gates, and interprets posterior distributions. The agent never calculates iROAS or posterior numbers through arithmetic or LLM guesswork.

---

## The 6-Stage Modeling Lifecycle

```text
[1. Ingest & Inspect] ──► [2. Validate Dataset] ──► [3. Formulate & Fit MMM]
                                                              │
                                                              ▼
[6. Executive Brief]  ◄── [5. Posterior & iROAS] ◄── [4. Diagnostic Gate]
```

---

## Procedure

### Stage 1: Ingest & Inspect Dataset

Register the dataset to establish server-controlled identity and cryptographic provenance.

1. **Step:** Call `register_dataset(path="data/marketing_data.csv")`.
   - **Key point:** Generates a persistent `dataset_id` and SHA-256 fingerprint that anchors model lineage.
   - **Why:** Protects downstream decisions from silent data drift or unverified file mutation.

2. **Step:** Call `inspect_dataset(dataset_id=dataset_id)`.
   - **Key point:** Verify inferred frequency (`'W-MON'`, `'D'`), date ranges, candidate channels, and null distributions.
   - **Why:** Catching missing intervals or incorrect column typing early avoids wasted MCMC sampling time.

### Stage 2: Statistical & Panel Validation

1. **Step:** Call `validate_dataset(...)` with designated column roles:
   ```json
   {
     "dataset_id": "ds_ecommerce_2026",
     "date_column": "date",
     "target_column": "revenue",
     "channel_columns": ["tv_spend", "search_spend", "meta_spend", "youtube_spend"],
     "control_columns": ["promo_flag", "macro_index"],
     "dims": []
   }
   ```
   - **Key point:** For panel models with geographic or regional splits, specify `dims=["geo"]` and ensure panel rectangularity.
   - **Why:** Irregular panel grids or high channel collinearity ($r \ge 0.90$) distort Bayesian parameter identification.
   - → Panel MMM reference: `references/panel-mmm-guide.md`

### Stage 3: Formulate Model & Fit MCMC

1. **Step:** Select adstock and saturation transformations tailored to channel mechanics:

| Channel Type | Recommended Adstock | Recommended Saturation | Typical $l_{\max}$ |
|---|---|---|---|
| **Google Search / Direct** | `geometric` ($\alpha \approx 0.2$) | `logistic` or `michaelis_menten` | 2–4 wks |
| **Meta / Social Performance**| `geometric` ($\alpha \approx 0.4$) | `logistic` or `hill` | 4–8 wks |
| **Linear & Connected TV** | `delayed` or `weibull_pdf` | `hill` ($S > 1$) | 8–16 wks |
| **Out-of-Home / Print** | `delayed` ($\theta \ge 2$) | `tanh` | 8–14 wks |

2. **Step:** Construct the configuration and submit the fit:
   - For fast fits / synchronous sessions: call `fit_mmm(...)`.
   - For long-running sampling in production: call `submit_fit_mmm_job(...)` and poll `get_job_status(job_id)`.
   - **Key point:** Always set `yearly_seasonality` (typically 2–4 Fourier modes) and configure informative `channel_priors`.
   - **Why:** Unconstrained priors on small spend channels lead to wide posterior variance and unidentifiable saturation parameters.
   - → Detailed mathematical formulas and priors: `references/transforms-guide.md`
   - → Configuration template: `templates/fit-mmm-input.json`

### Stage 4: Mandatory Diagnostic Gating

1. **Step:** Immediately call `diagnose_mmm(model_id=model_id)`.
   - **Key point:** Evaluate `decision_status` against hard and caution thresholds:
     - `approved`: Divergences $= 0$, $\hat{R} \le 1.01$, Bulk ESS $\ge 400$, Posterior-predictive coverage $\ge 80\%$.
     - `approved_with_caution`: Divergences $= 0$, $\hat{R} \le 1.05$, Bulk ESS $\ge 50$, Coverage $\ge 50\%$.
     - `rejected`: Divergences $> 0$, $\hat{R} > 1.05$, ESS $< 50$, or Coverage $< 50\%$.
   - **Why:** Decision-grade tools (`simulate_budget`, `optimize_budget`, `optimize_flighting`, `get_incremental_roas`) fail closed if called on a rejected model.
   - → If rejected, switch immediately to: `pymc-diagnostics-gate`

### Stage 5: Posterior Evidence & Incrementality Analysis

1. **Step:** Extract channel contributions:
   Call `get_channel_contributions(model_id=model_id)`.
   - Returns absolute attributed KPI and percentage shares per media channel with 94% highest density intervals (HDI).

2. **Step:** Extract total and marginal incremental ROAS:
   Call `get_incremental_roas(model_id=model_id)`.
   - **Total iROAS:** $\frac{\Delta \text{Revenue}}{\text{Spend}}$ over the entire evaluated window.
   - **Marginal iROAS:** $\left.\frac{\partial \text{Revenue}}{\partial \text{Spend}}\right|_{\text{current spend}}$. Indicates where the *next dollar* generates the highest return.
   - **$P(\text{iROAS} > 1)$:** Bayesian posterior probability that channel is value-accretive.

3. **Step:** Generate visual plots:
   Call `get_posterior_plots(model_id=model_id, plot_types=["saturation_curves", "waterfall_decomposition", "actual_vs_predicted"])`.

### Stage 6: Executive Synthesis & Brief Formulation

1. **Step:** Synthesize findings into the standardized executive briefing format.
   - Include diagnostic health, historical channel ROI table with credible intervals, diminishing returns analysis, and recommended reallocations.
   - **Key point:** Never present a point estimate without its 94% HDI. Never treat correlation as absolute causal proof.
   - **Why:** Decision-makers need to understand parameter uncertainty before committing advertising capital.
   - → Executive brief template: `templates/executive-brief.md`
   - → Complete walkthrough example: `examples/e-commerce-mmm-walkthrough.md`

---

## Common Mistakes & Mitigations

| Mistake | Signal | Mitigation |
|---|---|---|
| **Using Point Estimates Only** | Reporting "Meta iROAS is 2.4" without intervals | Always report posterior median alongside 94% HDI: `2.4 [1.9 - 2.9]` |
| **Conflating Total & Marginal iROAS** | Recommending budget based on total historical ROI | Use marginal iROAS to direct future budget; total ROI to evaluate past efficiency |
| **Bypassing Rejected Diagnostics** | Attempting optimization after MCMC convergence failure | Stop. Activate `pymc-diagnostics-gate` to reparameterize and refit |
| **Over-Parameterized Adstock** | Setting $l_{\max}=26$ weeks for fast digital channels | Restrict $l_{\max} \le 4$ for search; use delayed adstock only for TV/Brand |
| **Unchecked Channel Collinearity** | Two channels with $r > 0.90$ causing wide variance | Combine channels or add informative priors / lift tests |

---

## Decision Rules

- Weekly models require $\ge 52$ observations; reject or flag weekly data with $< 52$ weeks.
- Always run `validate_dataset` before `fit_mmm`.
- Always run `diagnose_mmm` before drawing business conclusions or calling decision tools.
- Never report model numbers from manual arithmetic; all figures must originate from MCP tool outputs.
- If `decision_status == "approved_with_caution"`, all stakeholder summaries must highlight the cautionary warnings.

---

## Evidence Requirements

- Dataset ID with SHA-256 fingerprint verified.
- Model ID with recorded MCMC configuration and random seed.
- Validated `diagnose_mmm` response envelope showing MCMC convergence metrics.
- Complete table of channel contributions and iROAS with 94% HDI bounds.

---

## Neural Connections

- **Upstream Precursor:** `fable-research`
- **Downstream Continuations:** `pymc-diagnostics-gate`, `pymc-budget-optimization`, `pymc-lift-calibration`
- **Lateral Peers:** `pymc-clv-customer-analytics`
- **Recovery Handler:** `pymc-diagnostics-gate`
