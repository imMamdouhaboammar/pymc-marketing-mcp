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


**Totals:** 39 capabilities (12 experimental, 25 stable, 2 deprecated).


## Tools

| Name | Domain | Status | Decision gate | Delegates to | Summary | Evidence tests |
|---|---|---|---|---|---|---|
| `estimate_customer_lifetime_value` | clv | stable | not enforced | `clv.estimate_customer_lifetime_value` | Estimate discounted lifetime value by combining a purchase model and monetary value model. | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow` |
| `fit_clv_model` | clv | deprecated | not enforced | `clv.fit_clv` | Fit a PyMC-Marketing CLV model (legacy compatibility wrapper). | none |
| `fit_purchase_model` | clv | stable | not enforced | `clv.fit_purchase_model` | Fit a PyMC-Marketing purchase or churn frequency model (BG/NBD or Shifted Beta-Geometric). | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow`<br>`tests/statistical/test_clv_real_models.py::test_real_shifted_beta_geo_workflow` |
| `fit_value_model` | clv | stable | not enforced | `clv.fit_value_model` | Fit a PyMC-Marketing monetary transaction value model (Gamma-Gamma). | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow` |
| `get_churn_risk_cohorts` | clv | experimental | not enforced | `clv.get_churn_risk_cohorts` | Group customers into churn-risk cohorts from a fitted CLV model. | none |
| `predict_customer_clv` | clv | deprecated | not enforced | `clv.predict_clv` | Produce customer-level predictions from a fitted CLV model (legacy compatibility wrapper). | none |
| `predict_expected_purchases` | clv | stable | not enforced | `clv.predict_expected_purchases` | Predict future purchase frequency per customer from a fitted purchase model. | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow` |
| `predict_expected_spend` | clv | stable | not enforced | `clv.predict_expected_spend` | Predict average transaction monetary spend per customer from a fitted value model. | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow` |
| `predict_probability_alive` | clv | stable | not enforced | `clv.predict_probability_alive` | Estimate probability of customer retention/alive from a fitted purchase or churn model. | `tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow`<br>`tests/statistical/test_clv_real_models.py::test_real_shifted_beta_geo_workflow` |
| `inspect_dataset` | datasets | stable | not enforced | `datasets.inspect` | Report columns, dtypes, ranges, and candidate role assignments for a registered dataset. | `tests/unit/test_dataset_service.py::test_register_and_inspect_dataset`<br>`tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists` |
| `register_dataset` | datasets | stable | not enforced | `datasets.register_file` | Register a CSV/Parquet file from the allowed ingest directory and fingerprint it. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists` |
| `validate_dataset` | datasets | stable | not enforced | `datasets.validate` | Check a dataset against MMM modeling requirements and report blocking issues. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists` |
| `get_channel_contributions` | decisions | stable | not enforced | `decisions.contributions` | Report posterior channel contributions with uncertainty intervals. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling` |
| `get_incremental_roas` | decisions | stable | not enforced | `decisions.iroas` | Report total and marginal incremental ROAS per channel with uncertainty. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling` |
| `get_response_curves` | decisions | experimental | not enforced | `decisions.response_curves` | Report saturation response curves per channel. | none |
| `optimize_budget` | decisions | stable | required | `decisions.optimize` | Allocate a fixed budget under channel constraints using the PyMC-Marketing optimizer. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `optimize_flighting` | decisions | stable | required | `decisions.optimize_flighting` | Build a multi-period weekly spend schedule and evaluate it against the model. | `tests/statistical/test_flighting_optimization.py::test_real_dynamic_flighting_optimization` |
| `recommend_next_measurement` | decisions | experimental | not enforced | `decisions.recommend_measurement` | Suggest the next experiment or lift test that would most reduce decision uncertainty. | none |
| `simulate_budget` | decisions | stable | required | `decisions.simulate` | Evaluate a counterfactual spend scenario against the fitted baseline. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `diagnose_mmm` | diagnostics | stable | not enforced | `diagnostics.diagnose` | Run the mandatory sampler and posterior-predictive gate and set the decision status. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `cancel_job` | jobs | stable | not enforced | `jobs.cancel_job` | Cancel a currently queued or running background job. | `tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_async_job_cancellation` |
| `get_job_status` | jobs | stable | not enforced | `jobs.get_job` | Retrieve the execution status, results, or error details of an asynchronous job. | `tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_create_and_retrieve_job` |
| `list_jobs` | jobs | stable | not enforced | `jobs.list_jobs` | List recent asynchronous background jobs for the active tenant. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_cross_tenant_job_access_blocked` |
| `submit_fit_mmm_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous MMM fitting job to run in the background without blocking. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence` |
| `archive_model` | modeling | experimental | not enforced | `models.archive_model` | Mark a stored model as archived while preserving its artifact and lineage. | none |
| `calibrate_mmm` | modeling | stable | not enforced | `models.calibrate` | Refit a model with experimental lift-test measurements added to the likelihood. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage` |
| `compare_models` | modeling | stable | not enforced | `models.compare_models` | Compare stored models on configuration, diagnostics, and iROAS ordering. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage` |
| `cross_validate_mmm` | modeling | stable | not enforced | `diagnostics.cross_validate` | Evaluate out-of-sample accuracy with PyMC-Marketing time-slice cross-validation. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity` |
| `evaluate_prior_sensitivity` | modeling | stable | not enforced | `diagnostics.prior_sensitivity` | Compare channel rankings under alternative adstock/saturation priors. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity` |
| `fit_mmm` | modeling | stable | not enforced | `models.fit` | Fit a PyMC-Marketing MMM with the requested adstock/saturation configuration. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `get_model_status` | modeling | stable | not enforced | `models.status` | Report stored state, configuration, and diagnostics summary for a model. | `tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `select_best_model` | modeling | experimental | not enforced | `models.select_best_model` | Rank models by information criterion and Bayesian model-averaging weights. | none |
| `get_posterior_plots` | plots | experimental | not enforced | `plots.generate_all` | Render headless posterior plot artifacts (PNG/SVG) for a fitted model. | none |


## Resources

| Name | Domain | Status | Decision gate | Delegates to | Summary | Evidence tests |
|---|---|---|---|---|---|---|
| `marketing://clv/{model_id}` | clv | experimental | not enforced | `` | Stored CLV model record and configuration. | none |
| `marketing://datasets/{dataset_id}` | datasets | experimental | not enforced | `` | Registered dataset metadata and fingerprint. | none |
| `marketing://models/{model_id}/diagnostics` | diagnostics | experimental | not enforced | `` | Persisted diagnostics result and decision status for a model. | none |
| `marketing://models/{model_id}` | modeling | experimental | not enforced | `` | Stored model record, configuration, and provenance. | none |
| `marketing://models/{model_id}/lineage` | modeling | experimental | not enforced | `` | Parent/child lineage chain for a model. | none |
| `marketing://models/{model_id}/plots/{plot_type}` | plots | experimental | not enforced | `plots.get_cached_plot` | Rendered posterior plot artifact for a model. | none |
