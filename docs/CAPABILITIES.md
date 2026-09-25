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


**Totals:** 66 capabilities (30 experimental, 34 stable, 2 deprecated).


## Tools

| Name | Domain | Status | Decision gate | Delegates to | Summary | Evidence tests |
|---|---|---|---|---|---|---|
| `cleanup_server_storage` | artifacts | experimental | not enforced | `artifacts.cleanup_storage` | Run server garbage collection to purge expired, delivered, or orphaned artifacts and temp files. | none |
| `export_artifact_to_sandbox` | artifacts | experimental | not enforced | `artifacts.export_to_sandbox` | Push/stage a model or dataset artifact (up to 1GB) for the AI client sandbox to download. | none |
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
| `list_datasets` | datasets | stable | not enforced | `datasets.list` | List all registered datasets and available inbox files on the server. | `tests/integration/test_data_ingestion_and_error_diagnostics.py::test_list_datasets_discovery` |
| `register_dataset` | datasets | stable | not enforced | `datasets.register_file` | Register a CSV/Parquet file from the allowed ingest directory and fingerprint it. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists` |
| `transform_ad_export` | datasets | stable | not enforced | `datasets.transform_long_form` | Pivot and transform raw ad-network export data into clean MMM modeling format with spend reconciliation. | `tests/unit/test_transform_ad_export_tool.py::test_transform_ad_export_tool_success_and_tenant_isolation`<br>`tests/unit/test_raw_export_transformation.py::test_transform_long_form_export_pivot_and_aggregation` |
| `validate_dataset` | datasets | stable | not enforced | `datasets.validate` | Check a dataset against MMM modeling requirements and report blocking issues. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists` |
| `get_channel_contributions` | decisions | stable | not enforced | `decisions.contributions` | Report posterior channel contributions with uncertainty intervals. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling` |
| `get_incremental_roas` | decisions | stable | required | `decisions.iroas` | Report total and marginal incremental ROAS per channel with uncertainty. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling` |
| `get_response_curves` | decisions | experimental | not enforced | `decisions.response_curves` | Report saturation response curves per channel. | none |
| `optimize_budget` | decisions | stable | required | `decisions.optimize` | Allocate a fixed budget under channel constraints using the PyMC-Marketing optimizer. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `optimize_flighting` | decisions | stable | required | `decisions.optimize_flighting` | Build a multi-period weekly spend schedule and evaluate it against the model. | `tests/statistical/test_flighting_optimization.py::test_real_dynamic_flighting_optimization` |
| `recommend_next_measurement` | decisions | experimental | not enforced | `decisions.recommend_measurement` | Suggest the next experiment or lift test that would most reduce decision uncertainty. | none |
| `simulate_budget` | decisions | stable | required | `decisions.simulate` | Evaluate a counterfactual spend scenario against the fitted baseline. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `diagnose_mmm` | diagnostics | stable | not enforced | `diagnostics.diagnose` | Run the mandatory sampler and posterior-predictive gate and set the decision status. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `get_agent_insights` | insights | stable | not enforced | `insights.list_insights` | Retrieve previously recorded agent insights, filterable by model, dataset, or category. | `tests/unit/test_insight_service.py::test_insight_service_record_and_query` |
| `record_agent_insight` | insights | stable | not enforced | `insights.record_insight` | Record structured findings, hypotheses, diagnostic warnings, or budget decisions. | `tests/unit/test_insight_service.py::test_insight_service_record_and_query` |
| `cancel_job` | jobs | stable | not enforced | `jobs.cancel_job` | Cancel a currently queued or running background job. | `tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_async_job_cancellation` |
| `get_job_status` | jobs | stable | not enforced | `jobs.get_job` | Retrieve the execution status, results, or error details of an asynchronous job. | `tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_create_and_retrieve_job` |
| `list_jobs` | jobs | stable | not enforced | `jobs.list_jobs` | List recent asynchronous background jobs for the active tenant. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_cross_tenant_job_access_blocked` |
| `poll_job_progress` | jobs | experimental | not enforced | `jobs.poll_job` | Non-blocking heartbeat poll waiting up to timeout_seconds for progress to avoid AI client timeout collapses. | none |
| `recover_execution_state` | jobs | experimental | not enforced | `jobs.recover_job_state` | Recover execution state and intermediate checkpoints after an unexpected disconnect or restart. | none |
| `resume_job` | jobs | experimental | not enforced | `jobs.resume_job` | Resume an interrupted or failed job from its last valid checkpoint without repeating completed work. | none |
| `submit_budget_optimization_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous budget optimization job under channel constraints without blocking. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence`<br>`tests/unit/test_heavy_jobs_resilience.py::test_submit_budget_optimization_job_idempotency_and_recovery` |
| `submit_cross_validate_mmm_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous cross-validation job for MMM out-of-sample evaluation. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence`<br>`tests/unit/test_heavy_jobs_resilience.py::test_submit_cross_validate_mmm_job_idempotency_and_recovery` |
| `submit_fit_mmm_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous MMM fitting job to run in the background without blocking. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence` |
| `submit_flighting_optimization_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous flighting optimization job across time periods and channels without blocking. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence`<br>`tests/unit/test_heavy_jobs_resilience.py::test_submit_flighting_optimization_job_idempotency_and_recovery` |
| `submit_prior_sensitivity_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous prior sensitivity evaluation job comparing prior and posterior distributions. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence`<br>`tests/unit/test_heavy_jobs_resilience.py::test_submit_prior_sensitivity_job_idempotency_and_recovery` |
| `submit_transform_ad_export_job` | jobs | stable | not enforced | `jobs.submit_job` | Submit an asynchronous ad export transformation job to pivot and reconcile spend in the background. | `tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence`<br>`tests/unit/test_heavy_jobs_resilience.py::test_submit_transform_ad_export_job_idempotency_and_recovery` |
| `archive_model` | modeling | experimental | not enforced | `models.archive_model` | Mark a stored model as archived while preserving its artifact and lineage. | none |
| `calibrate_mmm` | modeling | stable | not enforced | `models.calibrate` | Refit a model with experimental lift-test measurements added to the likelihood. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage` |
| `compare_models` | modeling | stable | not enforced | `models.compare_models` | Compare stored models on configuration, diagnostics, and iROAS ordering. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage` |
| `cross_validate_mmm` | modeling | stable | not enforced | `diagnostics.cross_validate` | Evaluate out-of-sample accuracy with PyMC-Marketing time-slice cross-validation. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity` |
| `evaluate_prior_sensitivity` | modeling | stable | not enforced | `diagnostics.prior_sensitivity` | Compare channel rankings under alternative adstock/saturation priors. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity` |
| `fit_mmm` | modeling | stable | not enforced | `models.fit` | Fit a PyMC-Marketing MMM with the requested adstock/saturation configuration. | `tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow`<br>`tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling`<br>`tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `get_model_status` | modeling | stable | not enforced | `models.status` | Report stored state, configuration, and diagnostics summary for a model. | `tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts` |
| `select_best_model` | modeling | experimental | not enforced | `models.select_best_model` | Rank models by information criterion and Bayesian model-averaging weights. | none |
| `get_posterior_plots` | plots | experimental | not enforced | `plots.generate_all` | Render headless posterior plot artifacts (PNG/SVG) for a fitted model. | none |
| `get_skill_guidance` | skills | experimental | not enforced | `skillpack.resolve_guidance` | Route a task to one scientific workflow skill or fetch one selected skill package. | none |
| `get_skill_workflow_map` | skills | experimental | not enforced | `skillpack.workflow_map` | Retrieve the dependency graph, prerequisites, and decision gates for all scientific skills. | none |
| `list_agentic_skills` | skills | experimental | not enforced | `skillpack.catalog` | List all registered agentic skills with summaries, maturity, and primary tools. | none |


## Resources

| Name | Domain | Status | Decision gate | Delegates to | Summary | Evidence tests |
|---|---|---|---|---|---|---|
| `marketing://clv/{model_id}` | clv | experimental | not enforced | `` | Stored CLV model record and configuration. | none |
| `marketing://datasets/{dataset_id}` | datasets | experimental | not enforced | `` | Registered dataset metadata and fingerprint. | none |
| `marketing://models/{model_id}/diagnostics` | diagnostics | experimental | not enforced | `` | Persisted diagnostics result and decision status for a model. | none |
| `marketing://models/{model_id}` | modeling | experimental | not enforced | `` | Stored model record, configuration, and provenance. | none |
| `marketing://models/{model_id}/lineage` | modeling | experimental | not enforced | `` | Direct model record and parent_model_id provenance for a model. | none |
| `marketing://models/{model_id}/plots/{plot_type}` | plots | experimental | not enforced | `plots.get_cached_plot` | Rendered posterior plot artifact for a model. | none |
| `marketing://skills` | skills | experimental | not enforced | `` | Compact deterministic catalog of available scientific workflow skills. | none |
| `marketing://skills/decision-gates` | skills | experimental | not enforced | `` | Decision-gated tool map derived from the public capability registry. | none |
| `marketing://skills/references/agent-operating-protocol` | skills | experimental | not enforced | `` | Shared protocol for operating the server: bootstrap, envelopes, IDs, jobs, and error recovery. | none |
| `marketing://skills/references/marketing-decision-playbook` | skills | experimental | not enforced | `` | Shared playbook translating marketing questions into server workflows and decision-ready answers. | none |
| `marketing://skills/references/scientific-answer-contract` | skills | experimental | not enforced | `` | Shared contract for communicating scientific analytical results and uncertainty. | none |
| `marketing://skills/references/scientific-source-ledger` | skills | experimental | not enforced | `` | Versioned source ledger for scientific rules used by the Skill Pack. | none |
| `marketing://skills/tool-map` | skills | experimental | not enforced | `` | Machine-readable classification of every public MCP tool into skill guidance. | none |
| `marketing://skills/workflow-map` | skills | experimental | not enforced | `` | Compact prerequisites, gates, continuations, and fallback workflow map. | none |
| `marketing://skills/{skill_name}` | skills | experimental | not enforced | `` | Canonical operational SKILL.md content for one allowed skill name. | none |
| `marketing://skills/{skill_name}/manifest` | skills | experimental | not enforced | `` | Machine-readable manifest for one allowed scientific workflow skill. | none |
