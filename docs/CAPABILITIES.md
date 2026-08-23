# MCP Capability Inventory

<!-- GENERATED FILE - do not edit by hand. -->

This document is generated from `src/marketing_mcp/capabilities.py` by
`scripts/generate_capability_inventory.py`. Regenerate it with:

```bash
uv run python scripts/generate_capability_inventory.py
```

`tests/unit/test_capabilities_doc.py` fails when this file drifts from the registry, and
`tests/integration/test_capability_inventory.py` fails when the registry drifts from real MCP
discovery.

Status meanings:

- `experimental` — exposed, but behavior is not yet proven by a referenced executable test. Do not
  present it as verified.
- `stable` — behavior is covered by at least one referenced executable evidence test.
- `deprecated` — still exposed for compatibility, scheduled for removal.

`Decision gate` marks capabilities that the code refuses to execute until `diagnose_mmm` has
approved the model.


**Totals:** 29 capabilities (29 experimental).


## Tools

| Name | Domain | Status | Decision gate | Summary | Evidence tests |
|---|---|---|---|---|---|
| `fit_clv_model` | clv | experimental | not enforced | Fit a PyMC-Marketing CLV model (BG/NBD, Gamma-Gamma, or shifted beta-geometric). | none |
| `get_churn_risk_cohorts` | clv | experimental | not enforced | Group customers into churn-risk cohorts from a fitted CLV model. | none |
| `predict_customer_clv` | clv | experimental | not enforced | Produce customer-level predictions from a fitted CLV model. | none |
| `inspect_dataset` | datasets | experimental | not enforced | Report columns, dtypes, ranges, and candidate role assignments for a registered dataset. | none |
| `register_dataset` | datasets | experimental | not enforced | Register a CSV/Parquet file from the allowed ingest directory and fingerprint it. | none |
| `validate_dataset` | datasets | experimental | not enforced | Check a dataset against MMM modeling requirements and report blocking issues. | none |
| `get_channel_contributions` | decisions | experimental | not enforced | Report posterior channel contributions with uncertainty intervals. | none |
| `get_incremental_roas` | decisions | experimental | not enforced | Report total and marginal incremental ROAS per channel with uncertainty. | none |
| `get_response_curves` | decisions | experimental | not enforced | Report saturation response curves per channel. | none |
| `optimize_budget` | decisions | experimental | required | Allocate a fixed budget under channel constraints using the PyMC-Marketing optimizer. | none |
| `optimize_flighting` | decisions | experimental | required | Build a multi-period weekly spend schedule and evaluate it against the model. | none |
| `recommend_next_measurement` | decisions | experimental | not enforced | Suggest the next experiment or lift test that would most reduce decision uncertainty. | none |
| `simulate_budget` | decisions | experimental | required | Evaluate a counterfactual spend scenario against the fitted baseline. | none |
| `diagnose_mmm` | diagnostics | experimental | not enforced | Run the mandatory sampler and posterior-predictive gate and set the decision status. | none |
| `archive_model` | modeling | experimental | not enforced | Mark a stored model as archived while preserving its artifact and lineage. | none |
| `calibrate_mmm` | modeling | experimental | not enforced | Refit a model with experimental lift-test measurements added to the likelihood. | none |
| `compare_models` | modeling | experimental | not enforced | Compare stored models on configuration, diagnostics, and iROAS ordering. | none |
| `cross_validate_mmm` | modeling | experimental | not enforced | Evaluate out-of-sample accuracy with PyMC-Marketing time-slice cross-validation. | none |
| `evaluate_prior_sensitivity` | modeling | experimental | not enforced | Compare channel rankings under alternative adstock/saturation priors. | none |
| `fit_mmm` | modeling | experimental | not enforced | Fit a PyMC-Marketing MMM with the requested adstock/saturation configuration. | none |
| `get_model_status` | modeling | experimental | not enforced | Report stored state, configuration, and diagnostics summary for a model. | none |
| `select_best_model` | modeling | experimental | not enforced | Rank models by information criterion and Bayesian model-averaging weights. | none |
| `get_posterior_plots` | plots | experimental | not enforced | Render headless posterior plot artifacts (PNG/SVG) for a fitted model. | none |


## Resources

| Name | Domain | Status | Decision gate | Summary | Evidence tests |
|---|---|---|---|---|---|
| `marketing://clv/{model_id}` | clv | experimental | not enforced | Stored CLV model record and configuration. | none |
| `marketing://datasets/{dataset_id}` | datasets | experimental | not enforced | Registered dataset metadata and fingerprint. | none |
| `marketing://models/{model_id}/diagnostics` | diagnostics | experimental | not enforced | Persisted diagnostics result and decision status for a model. | none |
| `marketing://models/{model_id}` | modeling | experimental | not enforced | Stored model record, configuration, and provenance. | none |
| `marketing://models/{model_id}/lineage` | modeling | experimental | not enforced | Parent/child lineage chain for a model. | none |
| `marketing://models/{model_id}/plots/{plot_type}` | plots | experimental | not enforced | Rendered posterior plot artifact for a model. | none |
