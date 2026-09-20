# MCP Tool Contracts (v0.4.0)

This document describes the current public MCP contract

`src/marketing_mcp/capabilities.py` is canonical for capability and resource names and maturity; `docs/CAPABILITIES.md` is the generated human-readable inventory derived from it. This document adds behavioral and safety semantics

All tool results use structured JSON-compatible envelopes and must not fabricate model-dependent quantities

## Common rules

- dataset/model/job IDs are server-controlled identifiers
- model-dependent numerical claims come from PyMC-Marketing/PyMC/ArviZ paths
- domain errors return stable error codes and next actions where available
- decision-grade tools require the persisted diagnostic gate to allow the decision
- warnings such as extrapolation or `approved_with_caution` remain user-visible
- local stdio is a trusted-local context
- remote scope/object authorization is still being hardened end to end, as documented in `docs/SECURITY.md`

## Dataset tools

### `register_dataset`

Register an allowed CSV/Parquet input, persist metadata and fingerprint the content

### `inspect_dataset`

Return schema/dtype/range and candidate-role information without returning the raw dataset as an MCP response

### `validate_dataset`

Validate MMM roles, temporal/panel structure and blocking data-quality conditions before fitting

### `list_datasets`

List all registered datasets and available inbox files on the server

### `transform_ad_export`

Transform raw platform ad export CSV bytes into model-ready weekly or daily panel dataset format

## MMM/model lifecycle tools

### `fit_mmm`

Fit a controlled PyMC-Marketing MMM using typed transform/prior/configuration inputs and persist model identity, artifact and provenance

The synchronous tool remains part of the compatibility surface. Long-running production compute is intended to move behind durable jobs

### `get_model_status`

Return persisted model state, configuration, diagnostic status and provenance summary

### `cross_validate_mmm`

Run PyMC-Marketing time-slice cross-validation and return bounded out-of-sample evidence

### `evaluate_prior_sensitivity`

Evaluate supported alternative prior/transform configurations and report stability/sensitivity evidence

### `calibrate_mmm`

Create a calibrated child model using compatible lift-test evidence. Calibration preserves parent/child lineage and does not mutate the parent model artifact in place

### `compare_models`

Compare compatible stored models using the implemented information-criterion/model-comparison semantics and identity checks

### `select_best_model`

Experimental capability for ranking compatible models by the implemented selection/weighting path. Do not present as verified until executable evidence is linked in the capability inventory

### `archive_model`

Experimental administrative lifecycle operation that marks a model archived while retaining artifact/lineage history

## Diagnostics

### `diagnose_mmm`

Run sampler and posterior-predictive checks, persist the decision status and return diagnostics/warnings

Current hard-rejection conditions include

- divergences `> 0`
- max R-hat `> 1.05`
- min ESS `< 50`
- posterior-predictive coverage `< 0.50`

Current caution conditions include max R-hat above 1.01 but at most 1.05, ESS below 400 but at least 50, weaker predictive coverage, high NRMSE or high residual autocorrelation

See `docs/DECISION-INTEGRITY.md`

## Descriptive and decision tools

### `get_channel_contributions`

Return posterior channel-contribution summaries with uncertainty and provenance

This is descriptive evidence. A rejected model may be inspected for diagnosis, but the response must retain the rejected/caution context

### `get_incremental_roas`

Return total and marginal incremental ROAS from the PyMC-Marketing incrementality path

**Decision gate required**. A rejected/undiagnosed model must not produce decision-grade iROAS

### `get_response_curves`

Experimental descriptive response/saturation evidence sampled from the model path

### `simulate_budget`

Evaluate the caller's counterfactual allocation against the approved fitted model

**Decision gate required**. The tool must evaluate the requested scenario rather than substituting optimizer output

### `optimize_budget`

Run constrained budget allocation through the supported PyMC-Marketing optimizer/response path and compare the recommended allocation with baseline evidence

**Decision gate required**. Budget and explicit constraints must be preserved; infeasible constraints are reported rather than silently relaxed

### `optimize_flighting`

Build/evaluate a multi-period weekly spend schedule with the implemented carryover and constraint semantics

**Decision gate required**. Returns week/channel allocation plus posterior response/decision evidence

### `recommend_next_measurement`

Experimental helper that suggests evidence-gathering options when current model/data uncertainty indicates that another experiment or measurement may be useful

It must be allowed to return that no single experiment is implied

## Plotting

### `get_posterior_plots`

Experimental tool that renders/caches supported posterior/model plots as headless artifacts

Numerical interpretation must still come from the typed/statistical result paths, not from visual guessing

## CLV tools

### `fit_purchase_model`

Fit a supported PyMC-Marketing purchase/churn frequency model such as BG/NBD or Shifted Beta-Geometric according to the input contract

### `fit_value_model`

Fit the Gamma-Gamma monetary-value model using compatible customer data

### `predict_expected_purchases`

Predict future purchase frequency from a compatible fitted purchase model

### `predict_probability_alive`

Return probability-alive/retention evidence only for model families whose semantics support it

### `predict_expected_spend`

Predict expected transaction value from a compatible fitted value model

### `estimate_customer_lifetime_value`

Combine compatible purchase and value models to estimate discounted customer lifetime value over the requested horizon

### `get_churn_risk_cohorts`

Experimental cohort grouping over compatible CLV/churn outputs

### `fit_clv_model`

Deprecated compatibility wrapper. New callers should use model-specific CLV tools

### `predict_customer_clv`

Deprecated compatibility wrapper. New callers should use the explicit purchase/value/LTV prediction tools

## Asynchronous job tools

### `submit_fit_mmm_job`

Submit an MMM fitting job and return a persisted job record without waiting for the fit to finish

Current implementation note: the job repository is SQLite and execution uses the in-process async executor/thread delegation. This is **not yet production worker isolation** and is not MCP Tasks extension support

### `submit_transform_ad_export_job`

Submit an asynchronous ad export transformation job to pivot and reconcile spend in the background

### `submit_budget_optimization_job`

Submit an asynchronous budget optimization job under channel constraints without blocking

### `submit_flighting_optimization_job`

Submit an asynchronous flighting optimization job across time periods and channels without blocking

### `submit_cross_validate_mmm_job`

Submit an asynchronous cross-validation job for MMM out-of-sample evaluation

### `submit_prior_sensitivity_job`

Submit an asynchronous prior sensitivity evaluation job comparing prior and posterior distributions

### `get_job_status`

Return the persisted job state/result/error for an authorized job

### `cancel_job`

Request cancellation of a queued/running job and persist the resulting state transition

Current in-process cancellation cannot be presented as proof that a separate statistical worker can always be terminated/recovered

### `list_jobs`

List recent jobs for the current execution context/tenant according to the implemented job repository policy

### `poll_job_progress`

Non-blocking heartbeat poll waiting up to timeout_seconds for progress to avoid AI client timeout collapses

### `recover_execution_state`

Recover execution state and intermediate checkpoints after an unexpected disconnect or restart

### `resume_job`

Resume an interrupted or failed job from its last valid checkpoint without repeating completed work.

If a completed result checkpoint already exists in the job repository, the job is marked `succeeded`
and that result is returned immediately without re-executing computation. If no completed checkpoint
exists, execution restarts/retries the uncompleted stage with the persisted payload, configuration,
and ownership. Intra-MCMC step resumption is not supported — uncompleted sampling stages restart.

**Valid resume sources**: `failed`, `cancelled`, `queued`.

## Artifact and storage tools

### `export_artifact_to_sandbox`

Push/stage a model or dataset artifact (up to 1GB) for the AI client sandbox to download

### `cleanup_server_storage`

Run server garbage collection to purge expired, delivered, or orphaned artifacts and temp files

## Agent insight tools

### `record_agent_insight`

Record an analytical, operational, or strategic observation about a model, dataset, or run

### `get_agent_insights`

Retrieve previously recorded agent insights, filterable by model, dataset, or category

## Scientific skill guidance tools

### `get_skill_guidance`

Route a task to one scientific workflow skill or fetch one selected skill package

### `list_agentic_skills`

List all registered agentic skills with summaries, maturity, and primary tools

### `get_skill_workflow_map`

Retrieve the dependency graph, prerequisites, and decision gates for all scientific skills

## MCP resources

`src/marketing_mcp/capabilities.py` is canonical for capability and resource names and maturity; `docs/CAPABILITIES.md` is the generated human-readable inventory derived from it. Public MCP resources are partitioned by discovery mechanism into parameterized resource templates and fixed static resources.

### Resource templates

Parameterized URIs discovered through MCP `list_resource_templates()`:

- `marketing://clv/{model_id}`: Stored CLV model record and configuration.
- `marketing://datasets/{dataset_id}`: Registered dataset metadata and fingerprint.
- `marketing://models/{model_id}`: Stored model record, configuration, and provenance.
- `marketing://models/{model_id}/diagnostics`: Persisted diagnostics result and decision status for a model.
- `marketing://models/{model_id}/lineage`: Direct model record and parent_model_id provenance (single record, no traversed lineage chain).
- `marketing://models/{model_id}/plots/{plot_type}`: Rendered posterior plot artifact for a model.
- `marketing://skills/{skill_name}`: Canonical operational SKILL.md content for one allowed skill name.
- `marketing://skills/{skill_name}/manifest`: Machine-readable manifest for one allowed scientific workflow skill.

### Static resources

Fixed URIs discovered through MCP `list_resources()`:

- `marketing://skills`: Compact deterministic catalog of available scientific workflow skills.
- `marketing://skills/decision-gates`: Decision-gated tool map derived from the public capability registry.
- `marketing://skills/references/scientific-answer-contract`: Shared contract for communicating scientific analytical results and uncertainty.
- `marketing://skills/references/scientific-source-ledger`: Versioned source ledger for scientific rules used by the Skill Pack.
- `marketing://skills/tool-map`: Machine-readable classification of every public MCP tool into skill guidance.
- `marketing://skills/workflow-map`: Compact prerequisites, gates, continuations, and fallback workflow map.

Current hardening note: these resources are public MCP resource contracts, but their request-scoped principal/scope/object-authorization path is not yet proven to match protected tool authorization. Remote production release is blocked until H2 closes

## Maturity semantics

- `stable`: capability behavior has referenced executable evidence, subject to the wider release/security/runtime status
- `experimental`: exposed but not yet evidenced strongly enough to present as verified
- `deprecated`: retained for compatibility and scheduled for removal

A stable individual tool does not imply the service is production-ready. Service readiness is governed by `docs/PRODUCTION-READINESS.md`
