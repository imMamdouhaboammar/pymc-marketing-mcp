---
name: pymc-mmm-workflow
version: 3.0.0
description: Use when a user wants to fit a media mix model or continue the principal MMM lifecycle from validated data through diagnosis and downstream evidence.
---
# PyMC MMM Workflow

Runs the main media mix modeling lifecycle through the public MCP API: validated data, one fit, mandatory diagnosis, then the evidence or decision skill the user's question needs. All modeling happens on the server with PyMC-Marketing; the agent writes no model code and no model math.

## Entry checks

1. A `dataset_id` with `valid_for_modeling: true` and a confirmed role mapping from `pymc-dataset-readiness`. If you do not have one, run that skill first.
2. `list_jobs(limit=10)`: if a fit job for the same dataset and spec is already queued, running, or succeeded, continue with it instead of starting another.
3. If the user names an existing model, `get_model_status(model_id)` and skip to diagnosis.

## Step 1: choose the simplest defensible specification

Start from the server defaults and change only what the business context justifies:

| Setting | Default | When to change it |
| --- | --- | --- |
| `adstock.type` | `geometric` | `delayed` or `weibull_*` only when the user expects a lagged peak (TV, outdoor, long consideration cycles) and history is long enough to identify it |
| `adstock.l_max` | `8` periods | Set it to cover the plausible carryover window **in data periods**: weekly data with 8 covers about two months; daily data needs a much larger value for the same window (max 52) |
| `saturation.type` | `logistic` | `hill` or `michaelis_menten` when the user wants an explicit half-saturation shape; keep one family across channels unless there is a reason |
| `yearly_seasonality` | none | Set a small Fourier order (for example 2) when there are two or more years of data and demand is seasonal |
| `control_columns` | none | Always pass the validated controls: promotions, price, event flags (Ramadan, Eid, White Friday), stock-outs |
| `dims` | none | `["geo"]` (or the validated panel dimension) for multi-market data |
| `sampler` | 1000 draws, 1000 tune, 4 chains, `target_accept` 0.9, seed 42 | Raise `target_accept` toward 0.95 only after divergences; keep the seed for reproducibility |
| `channel_priors` | none | Only when the user supplies real prior knowledge for a specific channel (a past experiment, a known carryover). Never invent "industry typical" priors |

Supported enums: adstock `geometric`, `delayed`, `weibull_cdf`, `weibull_pdf`, `binomial`, `none`; saturation `logistic`, `tanh`, `tanh_baselined`, `michaelis_menten`, `hill`, `hill_sigmoid`, `inverse_scaled_logistic`, `log`, `root`, `none`.

## Step 2: fit

On a remote connection, submit a background job so a dropped request does not lose the sampling:

```json
{
  "config": {
    "dataset_id": "<validated dataset_id>",
    "date_column": "date",
    "target_column": "revenue",
    "channel_columns": ["meta_spend", "google_spend", "tiktok_spend", "tv_spend"],
    "control_columns": ["promo_flag", "ramadan_week"],
    "yearly_seasonality": 2,
    "adstock": {"type": "geometric", "l_max": 8, "normalize": true},
    "saturation": {"type": "logistic"},
    "sampler": {"draws": 1000, "tune": 1000, "chains": 4, "target_accept": 0.9, "random_seed": 42},
    "dims": null
  },
  "idempotency_key": "<dataset_id>:fit:<short hash of the full config>"
}
```

- The server matches jobs on `idempotency_key` alone, so the key must change whenever anything in `config` changes (channels, controls, seasonality, transforms, sampler, dims). Derive it from the complete config (for example the first 12 characters of a SHA-256 of the canonical JSON), or bump a revision for every edit. Reusing a key returns the earlier fit.

- Tool: `submit_fit_mmm_job` with the payload above, then hand off to `pymc-job-resilience` to watch it. The succeeded job result carries the `model_id`.
- `fit_mmm(config=...)` takes the same `config` and blocks until sampling ends. Use it only for small local datasets or when the user explicitly wants a synchronous run.
- Channel names in `channel_columns` must match the validated mapping exactly, including the `_spend` suffix added by a transform.

## Step 3: confirm and diagnose

1. `get_model_status(model_id)`: confirm the dataset, config, and provenance are what you intended.
2. `diagnose_mmm(model_id)`: mandatory. Load `pymc-diagnostics-gate` to read the result.
   - `approved`: continue.
   - `approved_with_caution`: continue, and carry every warning into the final answer.
   - `rejected`: stop the decision path and follow the diagnostics remediation.

## Step 4: continue by question

| The user now asks | Next skill |
| --- | --- |
| Is this model trustworthy out of sample, and is it the best of several specs? | `pymc-model-validation` |
| Which channels drive results, what is the iROAS, where is saturation? | `pymc-incrementality-evidence` |
| How should spend change? | `pymc-budget-optimization` |
| We have a lift test | `pymc-lift-calibration` |
| Show me plots or give me the model file | `pymc-artifact-delivery` |

## Marketing interpretation

- A fitted and approved MMM describes how the outcome co-moved with spend and controls in the history provided. It is observational evidence. Experiments and calibration strengthen specific channel claims.
- Tell the user early what the model cannot see: creative and audience differences inside a channel, day-level effects in weekly data, and brand effects longer than `l_max`.
- If the data lacks controls for big events (Ramadan, Eid, White Friday), say that their effects may be absorbed by the channels that spent heavily in those weeks.

## Stop conditions

Stop and report instead of inventing an answer when the dataset is invalid, the fit or job failed, the model artifact cannot be loaded, diagnosis rejects the model for a requested decision, or the quantity the user wants is not returned by any public tool. Descriptive evidence the server allows on a rejected model stays labeled non-decision-grade.

Follow the [scientific answer contract](marketing://skills/references/scientific-answer-contract) for the final write-up and the [agent operating protocol](marketing://skills/references/agent-operating-protocol) for envelopes, IDs, and errors.
