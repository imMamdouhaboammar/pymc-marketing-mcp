---
name: pymc-model-validation
version: 2.0.0
description: Use when a user asks about cross-validation, prior sensitivity, comparing MMM specifications, information criteria, or selecting among fitted models.
---
# PyMC Model Validation

Answers "can we trust this model beyond the data it saw?" and "which of these models should we use?". Each question has its own server tool, and none of them replaces the diagnostic gate.

## Four questions, four tools

| Question | Tool | Background job |
| --- | --- | --- |
| Does the model predict weeks it did not train on? | `cross_validate_mmm` | `submit_cross_validate_mmm_job` |
| Do the business conclusions change under reasonable alternative priors or transforms? | `evaluate_prior_sensitivity` | `submit_prior_sensitivity_job` |
| How do stored models differ in diagnostics, predictive evidence, config, and lineage? | `compare_models` | none |
| Which model does the server's information-criterion ranking prefer? | `select_best_model` (experimental) | none |

Cross-validation and prior sensitivity refit the model several times. On a remote connection always use the job form and hand off to `pymc-job-resilience`.

## Call templates

Cross-validation (rolling time slices):

```json
{"input": {"model_id": "<model_id>", "n_init": 40, "forecast_horizon": 10, "step_size": 10},
 "idempotency_key": "<model_id>:cv:40-10-10"}
```

- `n_init` is the first training window in data periods and must leave room for at least one forecast window. With 104 weekly rows, `n_init` 52, `forecast_horizon` 8, `step_size` 8 gives several folds.
- Match `forecast_horizon` to the planning cycle the user cares about (a quarter of weekly data is about 13).

Prior sensitivity:

```json
{"input": {"model_id": "<model_id>"}, "idempotency_key": "<model_id>:prior-sensitivity:v1"}
```

Comparison and selection:

```json
{"input": {"model_ids": ["<model_a>", "<model_b>"]}}
{"config": {"model_ids": ["<model_a>", "<model_b>", "<model_c>"], "criterion": "loo", "weighting": "stacking"}}
```

The first goes to `compare_models`, the second to `select_best_model`. `criterion` accepts `loo`, `waic`, or `both`; `weighting` accepts `stacking`, `bb-pseudo-bma`, or `pseudo-bma`. `method` is deprecated.

## Gate: same dataset before any comparison

Before `compare_models` or `select_best_model`, call `get_model_status` for each model and confirm they share the same `dataset_id` and the same target. Information criteria computed on different data are not comparable. If the server returns `INCOMPATIBLE_MODELS`, report which models differ; never rank them yourself.

## Reading the results

- Cross-validation returns out-of-sample error metrics and stability findings (surfaced in `warnings`). Report the error in business units where the tool gives them, and say whether errors cluster in specific periods (promotions, Ramadan, Q4), which points to missing controls.
- Prior sensitivity returns findings on whether channel rankings and effect sizes move under the alternative settings. If rankings flip, the data alone does not settle which channel is stronger; that is the moment to suggest a lift test (`pymc-lift-calibration`, `recommend_next_measurement`).
- Comparison and selection return per-model criteria, weights, and warnings (including Pareto-k warnings for LOO). A model with a high stacking weight is the better predictor on this data; it still needs its own `approved` or `approved_with_caution` diagnosis before driving decisions.

Keep these properties separate in every answer:

- Convergence (diagnostics gate) tells you the sampler explored the posterior.
- Predictive accuracy tells you the model forecasts unseen periods.
- Prior robustness tells you conclusions hold under reasonable alternative assumptions.
- Causal identification needs design (experiments, calibration).
- Commercial usefulness needs all of the above plus a decision that the evidence can actually support.

## Marketing interpretation

- "The model predicted the last N weeks it never saw within X%" is a strong, understandable trust signal. Quote the server's metric.
- When two specs predict equally well but disagree on a channel's return, tell the user the data cannot distinguish them for that channel and recommend an experiment instead of picking one silently.
- A simpler model that predicts as well is easier to explain and usually safer for budget decisions.

## Administrative operations

`archive_model` hides a model from normal use while keeping its artifacts and lineage. Run it only when the user explicitly asks and is authorized:

```json
{"input": {"model_id": "<model_id>"}}
```

## Stop conditions

Stop when models do not share a dataset, when a validation job failed (report the recorded error), or when a selected model has not passed its own diagnosis. Do not import ArviZ behavior the tools do not expose.
