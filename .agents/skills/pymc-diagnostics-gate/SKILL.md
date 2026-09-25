---
name: pymc-diagnostics-gate
version: 3.0.0
description: Use when an MMM has divergences, R-hat or ESS concerns, predictive-check warnings, rejection, or unclear decision status, or when a fitted or calibrated model must be cleared before decisions.
---
# PyMC Diagnostics Gate

`diagnose_mmm` decides whether a model may drive decisions. The agent reads its verdict, explains it, and routes remediation. The agent never recomputes thresholds or overrides the verdict.

## When this skill runs

- Right after every fit, including every calibrated child model and every refit.
- Before any call to `get_incremental_roas`, `simulate_budget`, `optimize_budget`, or `optimize_flighting` when the model's current `decision_status` is unknown.
- When a decision tool returned `MODEL_NOT_DIAGNOSED`, `MODEL_NOT_VALIDATED`, or `MODEL_REJECTED`.

## Call and read

`diagnose_mmm(model_id="<model_id>")`, then branch on `summary.decision_status`:

| `decision_status` | `decision_tools_enabled` | What the agent does |
| --- | --- | --- |
| `approved` | true | Continue to the skill the user's question needs. |
| `approved_with_caution` | true | Continue, and put every entry of `warnings` into the final answer in plain language. |
| `rejected` | false | Stop the decision path. Explain `summary.failures`, then follow the remediation table below. |

`next_actions` on a rejected model still lists descriptive tools and `get_incremental_roas`. The iROAS tool is gated and will refuse; do not call it to "check".

## Current server policy

Hard failures (any one rejects): divergences > 0, maximum R-hat > 1.05, minimum bulk ESS < 50, and 94% posterior-predictive coverage < 0.50 when the predictive check is available. Each failure arrives as `{"metric", "observed", "required"}`.

Cautions (the model passes with `approved_with_caution`): `ELEVATED_RHAT` (1.01 to 1.05), `LOW_EFFECTIVE_SAMPLE_SIZE` (50 to 400), `LOW_POSTERIOR_PREDICTIVE_COVERAGE` (0.50 to 0.80), `HIGH_PREDICTIVE_ERROR` (high normalized RMSE), `RESIDUAL_AUTOCORRELATION` (strong lag-1 residual correlation). `PREDICTIVE_CHECK_UNAVAILABLE`, `SAMPLE_STATS_UNAVAILABLE`, and `POSTERIOR_DIAGNOSTICS_UNAVAILABLE` mean a check could not run; report which evidence is missing.

These numbers are this server's current policy. Changing them is a policy decision for the maintainers; the agent applies them as they are.

## Remediation after rejection

Match the failure to the most likely cause before proposing a refit. Change one thing per refit and keep the rest of the spec fixed so the comparison stays readable.

| Failure or warning | Likely cause in marketing data | Proposed next step |
| --- | --- | --- |
| divergences > 0 | Channels that always move together, a saturation shape the data cannot pin down, or extreme spend spikes | Merge correlated channels or drop a near-constant one; check `HIGH_CHANNEL_CORRELATION` and `EXTREME_OUTLIERS` findings; then consider `target_accept` 0.95 |
| max R-hat > 1.05 | Chains found different explanations (weak identification, multimodal saturation) | Simplify: fewer channels, a simpler adstock (`geometric`), shorter `l_max`; more draws only after that |
| min ESS < 50 | Slow mixing, often from the same identification problems | Same as R-hat; raising `draws` and `tune` helps only when the spec is sound |
| coverage < 0.50 or `HIGH_PREDICTIVE_ERROR` | The model misses structure: missing controls, events, trend, or seasonality | Add event and promo controls (Ramadan, Eid, White Friday), add `yearly_seasonality`, check `POSSIBLE_TARGET_TRACKING_GAP` |
| `RESIDUAL_AUTOCORRELATION` | Slow-moving demand the model does not capture (trend, brand build-up, distribution changes) | Add a trend or distribution control; treat long-term channel claims with care |

Raising `target_accept` or `draws` is sometimes useful and never a cure for misspecification or weak identification. Refits go through `pymc-mmm-workflow` (usually `submit_fit_mmm_job`), and every refit is diagnosed again from scratch.

## What stays allowed on a rejected model

`get_channel_contributions`, `get_response_curves`, `get_model_status`, `get_posterior_plots`, and `recommend_next_measurement` can help explain *why* the model failed. Label anything they return as non-decision-grade and never turn it into a spend recommendation.

## Recording what you learned

When a diagnosis teaches something reusable about this dataset (for example "tiktok and snapchat spend correlate at 0.93; merged for v2"), store it so the next session starts informed:

```json
{"category": "diagnostic_warning", "summary": "Merged tiktok_spend and snapchat_spend after divergences in v1", "model_id": "<model_id>", "dataset_id": "<dataset_id>", "severity": "warning", "tags": ["remediation", "correlation"]}
```

Call `record_agent_insight` with that payload, and `get_agent_insights(dataset_id=...)` at the start of later work on the same dataset. Valid categories: `eda_finding`, `prior_selection`, `diagnostic_warning`, `budget_strategy`, `clv_insight`, `hypothesis`, `general_note`. Valid severities: `info`, `warning`, `critical`. `summary` holds 3 to 500 characters.

## Explaining the verdict to a marketer

- Approved: "The model's statistical health checks passed, so its estimates can inform budget decisions, with the uncertainty ranges shown."
- Approved with caution: name the caution in one sentence and what it means for trust, for example "predictions miss some weekly swings, so read channel figures as ranges."
- Rejected: "The model did not pass its health checks, so it cannot be used to move budget yet." Then give the one or two concrete fixes from the table.
- Always keep three ideas apart: sampler health, predictive accuracy, and causal evidence. Passing the gate proves the first two within policy; it never proves causality.
