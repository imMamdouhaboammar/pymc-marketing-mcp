# Changelog

All notable changes to `pymc-marketing-mcp` are documented in this file.

## [Unreleased] - Stabilization and Hardening Program

The v0.4.x codebase remains advanced beta / release-candidate implementation. New public capability work is frozen until the original G0-G5/AQG gates and the 2026-08-26 H0-H6 hardening gates are proven from current-head evidence.

See `docs/PRODUCTION-READINESS.md` and `docs/superpowers/plans/README.md`.

### Added
- SQLite schema migrations and persistent job records.
- Asynchronous job tools: `submit_fit_mmm_job`, `get_job_status`, `cancel_job`, and `list_jobs`.
- Local job cancellation/idempotency primitives and stale-job recovery on application startup.
- Security profiles for trusted stdio, private API-key HTTP, and production OAuth configuration.
- Scope policy and principal/tenant ownership helpers.
- Header-only credential policy with query-string credential rejection.
- Request-safety and recursive secret-redaction foundations.
- Structured logging, metrics, liveness, and readiness foundations.
- Release-gate and agent-behavior test scaffolding for G2-G5/AQG.
- 2026-08-26 H0-H6 hardening program covering runtime truth, remote identity propagation, resource isolation, dashboard credentials, durable jobs, agent evals, and upstream compatibility.
- Documentation truth model in `docs/README.md`.

### Changed
- Corrected production-readiness language so implemented primitives are not presented as completed end-to-end production properties.
- Current documentation now distinguishes `verified`, `implemented`, `partial`, `blocked`, `historical`, and `target` states.
- Cloud Run guidance is classified as development/staging until durable storage, worker isolation, remote authorization, observability, and release-evidence gates are proven.
- Statistical policy documentation now matches the current diagnostics engine and includes incremental ROAS in the decision-gated surface.
- Historical v0.3 final-review and fixed PASS verification claims are explicitly historical rather than current release evidence.

### Known hardening blockers
- Authenticated Streamable HTTP identity is not yet proven to propagate into every MCP tool execution context.
- MCP resources do not yet enforce the same request-scoped scope/ownership policy as tools.
- Ownership helpers require full dataset/model/scenario/CLV lifecycle wiring and E2E tenant evidence.
- Dashboard API-key management still stores raw secret material independently of the server credential authority.
- Current jobs execute inside the API process rather than isolated durable statistical workers.
- Production Postgres/object-storage adapters, backup/restore, traces, runbooks, required GitHub Actions workflows, compatibility canary, and current-head generated release evidence remain target work.
- Agent eval fixtures still require conversion from pre-marked pass data to runtime trace evidence.

## [0.4.0] - 2026-08-22

### Added
- **Adstock & Saturation Model Zoo (Phase 1)**: Expanded from fixed Geometric/Logistic to full PyMC-Marketing transform suite (`delayed`, `weibull_cdf`, `weibull_pdf`, `binomial`, `none` adstocks; `tanh`, `tanh_baselined`, `michaelis_menten`, `hill`, `hill_sigmoid`, `inverse_scaled_logistic`, `log`, `root` saturations) with per-channel custom prior overrides via `channel_priors`.
- **Visual Posterior Artifact Delivery (Phase 2)**: Added `get_posterior_plots` tool and `marketing://models/{model_id}/plots/{plot_type}` MCP resources for headless rendering of saturation curves, waterfall decompositions, actual vs predicted fits, and channel contribution shares in PNG/SVG.
- **Customer Lifetime Value (CLV) Suite (Phase 3)**: Added `fit_clv_model`, `predict_customer_clv`, `get_churn_risk_cohorts` tools and `CLVService` / `CLVAdapter` wrapping PyMC-Marketing BG/NBD (`BetaGeoModel`), Gamma-Gamma, and Shifted Beta Geometric models with RFM dataset validation.
- **Dynamic Multi-Period Flighting (Phase 4)**: Added `optimize_flighting` tool with weekly spend schedule construction across flat, frontloaded, backloaded, and pulsed patterns, accounting for adstock carryover, net-profit maximization (margin revenue - spend), and target-iROAS floor constraints.
- **Bayesian Model Comparison & Stacking (Phase 5)**: Added `select_best_model` tool powered by `arviz.compare` (PSIS-LOO, WAIC, Bayesian model averaging stacking weights) with cross-dataset validation and Pareto-k diagnostic warnings.

## [0.3.0] - 2026-08-21

### Added
- **Time-Slice Cross-Validation**: Added `cross_validate_mmm` tool powered by PyMC-Marketing `TimeSliceCrossValidator` calculating out-of-sample RMSE and NRMSE across temporal rolling folds.
- **Prior Sensitivity Analysis**: Added `evaluate_prior_sensitivity` tool assessing channel rank order and iROAS sensitivity under alternative adstock and saturation priors.
- **Experimental Lift Test Calibration**: Added `calibrate_mmm` tool incorporating incrementality lift test data directly into model likelihood via `add_lift_test_measurements`.
- **Model Lineage & Multi-Model Ops**: Added `compare_models` and `archive_model` tools, semantic configuration hashing, dataset fingerprinting, parent-model tracking, and `marketing://models/{model_id}/lineage` MCP resource.
- **Extrapolation Risk Guard**: Added `check_extrapolation_risk` automatically warning when simulated or optimized spend exceeds 1.5x of historical 95th percentile spend.
- **Multi-Core Accelerated Testing**: Added `pytest-xdist` support executing all 46 unit, integration, and full Bayesian sampling tests concurrently in ~50s.
- **Official MCP 2.0.0 Protocols**: Added full stdio and Streamable HTTP client roundtrip verification with dynamic port discovery and structured error envelopes.

### Changed
- **PyMC-Marketing 1.0.0 Alignment**: Migrated from legacy `pymc_marketing.mmm.multidimensional` imports to unified canonical `from pymc_marketing.mmm import MMM, BudgetOptimizerWrapper`.
- **NetCDF Artifact Backend**: Added `h5netcdf` and `h5py` for robust xarray DataTree model serialization and reloading.
- **Diagnostic Engine**: At that historical release, documented R-hat/ESS approval tiers were introduced and later refined; use current `docs/DECISION-INTEGRITY.md` for active thresholds.

### Fixed
- Fixed `_response_values` in adapter to correctly unpack `xarray.Dataset` responses containing `total_media_contribution_original_scale`.
- Fixed SQLite scenario persistence schema constraint.
- Fixed MCP resource lookup domain error propagation.

## [0.2.0] - 2026-08-20

### Added
- Initial decision integrity architecture and diagnostic gating.
- Separate total iROAS and marginal iROAS endpoints.
- Multidimensional panel validation and cell-level scenario evaluation.
