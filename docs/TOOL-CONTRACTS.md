# MCP Tool Contracts (v0.4.0)

Every MCP tool returns structured, agent-oriented data wrapped in a standard `ToolEnvelope` (summary, evidence, warnings, provenance, next_actions). Large posterior arrays stay server-side.

## 1. Dataset Tools

### `register_dataset(path: str)`
- Registers a local CSV or Parquet file from the safe ingest root.
- Returns `dataset_id`, format, row count, and SHA-256 fingerprint.

### `inspect_dataset(dataset_id: str)`
- Returns row count, inferred temporal frequency, date range, candidate target/channel/control columns, missing periods, and inspection findings.

### `validate_dataset(dataset_id: str, date_column: str, target_column: str, channel_columns: list[str], control_columns: list[str] | None, dims: list[str] | None)`
- Runs statistical and panel-shape validation: 52+ week minimum, zero-spend variation, extreme channel correlation (>= 0.90), negative spend, duplicate periods, and rectangular panel integrity across dimension cells.

## 2. Modeling & Lineage Tools

### `fit_mmm(config: FitMMMInput)`
- Fits a real Bayesian Marketing Mix Model using PyMC-Marketing.
- Supports full transform zoo:
  - Adstocks: `geometric` (default), `delayed`, `weibull_cdf`, `weibull_pdf`, `binomial`, `none`.
  - Saturations: `logistic` (default), `tanh`, `tanh_baselined`, `michaelis_menten`, `hill`, `hill_sigmoid`, `inverse_scaled_logistic`, `log`, `root`, `none`.
  - `channel_priors`: per-channel overrides for adstock/saturation specifications.
- Controls sampler configuration (draws, tune, chains, target_accept, random_seed), adstock, saturation, and yearly seasonality.
- Automatically hashes semantic configuration, records dataset fingerprint, and attaches package provenance.

### `get_model_status(model_id: str)`
- Returns model record, execution status (`queued`, `running`, `completed`, `failed`, `cancelled`), lineage stage (`initial_fit`, `calibrated`, `refreshed`), and error details.

### `calibrate_mmm(input: CalibrateMMMInput)`
- Calibrates an existing fitted MMM using experimental incrementality lift tests (`add_lift_test_measurements`).
- Produces a new calibrated model artifact with `parent_model_id` lineage linkage.

### `compare_models(input: CompareModelsInput)`
- Compares sampler diagnostics, predictive RMSE/NRMSE, divergences, R-hat, ESS, and lineage stages across multiple fitted models.

### `select_best_model(config: ModelComparisonInput)`
- Information-theoretic model comparison powered by ArviZ.
- Supports PSIS-LOO (`loo`), WAIC (`waic`), and Bayesian Model Averaging stacking weights (`stacking` or `all`).
- Enforces single-dataset comparative validity and surfaces Pareto-k diagnostic warnings ($k > 0.7$).

### `archive_model(input: ArchiveModelInput)`
- Transitions a model record to `cancelled`/archived state.

## 3. Diagnostics & Cross-Validation Tools

### `diagnose_mmm(model_id: str)`
- Mandatory statistical gate. Checks divergences (= 0), R-hat (<= 1.05 fail, <= 1.01 clean), bulk ESS (>= 50 fail, >= 400 clean), 94% posterior predictive coverage (>= 50% fail, >= 80% clean), normalized RMSE, and residual autocorrelation.
- Computes decision status: `approved`, `approved_with_caution`, or `rejected`.

### `cross_validate_mmm(input: CrossValidateMMMInput)`
- Runs rolling Time-Slice Cross-Validation with `TimeSliceCrossValidator`.
- Evaluates out-of-sample predictive RMSE and NRMSE across rolling folds.

### `evaluate_prior_sensitivity(input: PriorSensitivityInput)`
- Evaluates commercial conclusion stability (channel rank ordering and iROAS) under altered adstock and saturation priors across multiple alternative specifications.

## 4. Visual Artifact Tools

### `get_posterior_plots(config: GetPosteriorPlotsInput)`
- Generates headless PNG/SVG visualizations from fitted MMM posterior samples.
- Supported plot types:
  - `saturation_curves`: channel saturation and response curves with 94% HDI.
  - `waterfall_decomposition`: posterior median decomposition waterfall.
  - `actual_vs_predicted`: observed vs posterior predictive samples with credible bands.
  - `channel_contribution_share`: channel percentage contribution shares (bar + pie).
- Returns base64 image strings in evidence envelope and caches artifacts to MCP plot resources.

## 5. Decision & Incrementality Tools

### `get_channel_contributions(model_id: str)`
- Returns posterior channel contribution summaries (median and 94% credible intervals in original scale).

### `get_incremental_roas(model_id: str)`
- Returns total iROAS and marginal iROAS from PyMC-Marketing official incrementality API with posterior uncertainty ($P(\text{iROAS} > 1)$, median, 94% CI).

### `get_response_curves(model_id: str)`
- Returns sampled saturation and response curve data.

### `simulate_budget(config: BudgetSimulationInput)`
- Evaluates exact requested channel or dimension-cell spend scenarios with posterior response sampling.
- Emits `EXTRAPOLATION_RISK` warning if spend exceeds 1.5x of historical 95th percentile spend.

### `optimize_budget(config: BudgetOptimizationInput)`
- Computes SLSQP budget optimization subject to channel or cell constraints.
- Compares baseline vs recommended posterior responses with uncertainty intervals.

### `optimize_flighting(config: FlightingOptimizationInput)`
- Optimizes a multi-week media flighting schedule over a planning horizon (2–52 weeks).
- Supports spend patterns: `flat`, `frontloaded`, `backloaded`, `pulsed`.
- Implements net-profit maximization ($\text{Revenue} \times \text{Margin} - \text{Spend}$) and minimum target-iROAS floor constraints.

### `recommend_next_measurement(model_id: str)`
- Recommends evidence-gathering experiments when data or model uncertainties are high.

## 6. Customer Lifetime Value (CLV) Tools

### `fit_purchase_model(config: FitPurchaseModelInput)`
- Fits a Bayesian repeat purchase or contractual churn frequency model (`bg_nbd` or `shifted_beta_geo`).
- Normalizes user column names (`customer_id_col`, `frequency_col`, `recency_col`, `T_col`, `cohort_col`) into canonical RFM schemas.

### `fit_value_model(config: FitValueModelInput)`
- Fits a Bayesian monetary value transaction model (`gamma_gamma`) on repeat transactions (`frequency > 0`).
- Estimates expected average order value / spend per customer.

### `predict_expected_purchases(config: PredictExpectedPurchasesInput)`
- Evaluates expected future transaction counts per customer over horizon `future_t`.
- Returns `total_customers` for full population sizing alongside `top_n` truncation.

### `predict_probability_alive(config: PredictProbabilityAliveInput)`
- Evaluates posterior retention / active probability $P(\text{alive})$ per customer from purchase or churn models.
- Returns summary metrics (`customers_likely_alive`, `customers_at_churn_risk`).

### `predict_expected_spend(config: PredictExpectedSpendInput)`
- Predicts expected monetary spend per transaction for repeat customers using a fitted `gamma_gamma` model.

### `estimate_customer_lifetime_value(config: EstimateCLVInput)`
- Integrates a fitted purchase model (`bg_nbd` or `shifted_beta_geo`) with a monetary value model (`gamma_gamma`).
- Computes discounted net present Customer Lifetime Value (CLV) over forecast horizon `future_t` with discount rate `discount_rate`.

### `get_churn_risk_cohorts(model_id: str, threshold_p_alive: float = 0.3)`
- Segments at-risk customer cohorts with $P(\text{alive}) < \text{threshold}$.

### `fit_clv_model(config: FitCLVInput)`
- (Deprecated compatibility wrapper): Fits Bayesian CLV models on customer RFM data.

### `predict_customer_clv(config: PredictCLVInput)`
- (Deprecated compatibility wrapper): Generates individual-level predictions: $P(\text{alive})$, expected future transactions, and expected customer value.

## 8. Asynchronous Job Tools

### `submit_fit_mmm_job(config: FitMMMInput, idempotency_key: str | None = None)`
- Submits an asynchronous MMM fitting background job without blocking the connection.
- Returns `JobRecord` in `queued` state with `job_id` and tracking metadata.

### `get_job_status(job_id: str)`
- Retrieves execution status (`queued`, `running`, `succeeded`, `cancelling`, `cancelled`, `failed`), progress, results, or error details for an asynchronous job.

### `cancel_job(job_id: str)`
- Cancels a queued or running background job.

### `list_jobs(status: str | None = None, limit: int = 50)`
- Lists recent background jobs for the authenticated caller's tenant.

## 9. MCP Resources

- `marketing://datasets/{dataset_id}`: Full dataset metadata and inspection status.
- `marketing://models/{model_id}`: Full model record and configuration.
- `marketing://models/{model_id}/diagnostics`: Detailed diagnostic metrics and findings.
- `marketing://models/{model_id}/lineage`: Model parent linkage, semantic hash, and package provenance.
- `marketing://models/{model_id}/plots/{plot_type}`: Binary PNG visualization artifact.
- `marketing://clv/{model_id}`: CLV model metadata and lifecycle status.
