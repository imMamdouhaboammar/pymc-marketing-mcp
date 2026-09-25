# Changelog

All notable changes to `pymc-marketing-mcp` are documented in this file.

## [Unreleased] - Stabilization and Hardening Program

The v0.4.x codebase is in release-candidate state with all Hardening Waves (Waves A through G) completed and verified with machine release evidence.

See `docs/PRODUCTION-READINESS.md` and `docs/release-evidence/cb1d75d1fb82.md`.

### Added
- **Gate H0 (Runtime Truth Baseline)**: Version synchronization, CI workflows (`ci.yml`, `statistical.yml`, `security.yml`, `upstream-canary.yml`, `release.yml`), `scripts/render_production_readiness.py`, and release evidence generation.
- **Gate H1 & H2 / G3 (Request-Scoped Auth & Object Isolation)**: `_current_execution_context` (`ContextVar[ExecutionContext]`) and `RequestScopedContextProvider` propagating authenticated HTTP principals into MCP tool execution; `AuthorizationService` enforcing scopes and multi-tenant isolation across all MCP tools and resources (`marketing://models/{model_id}`, `marketing://datasets/{dataset_id}`, diagnostics, lineage, plots, CLV).
- **Gate H3 (Credential Control Plane)**: `CredentialService` with 256-bit entropy token generation (`mcp_live_...`), salted SHA-256 verifier storage (`SQLiteCredentialRepository`), constant-time hash verification, `/control/credentials` HTTP control endpoints, and dashboard migration removing browser key generation and Firestore raw-secret storage.
- **Gate H4 / G2 (Durable Jobs & Worker Separation)**: `ProcessJobWorker` and `marketing-mcp-worker` CLI for process-isolated statistical execution; canonical semantic idempotency key generation (`compute_semantic_idempotency_key`); `UnsupportedTasksExtensionAdapter` boundary.
- **Gate G4 (Observability & Tracing)**: Structured single-line JSON logging with secret scrubbing (`StructuredJSONFormatter`), low-cardinality metrics (`MetricsCollector`), and distributed trace context propagation (`trace_span`, `current_trace_id`, `current_span_id`).
- **Gate H5 / AQG (Agent Quality Gate)**: Trace-driven eval suites verifying tool trace capture, Bayesian diagnostic gating, and negative security boundaries.
- **Gate H6 (Upstream Compatibility)**: Compatibility canary test suite and capability inventory checks against the active PyMC-Marketing stack.

### Security
- `/control/credentials` refuses to issue API keys while server authentication is off; keys minted anonymously used to remain valid after auth was enabled.
- The HTTP auth middleware no longer skips authentication for any path ending in `.json`, `.js`, `.html` and similar extensions.
- Artifact downloads require a signed token or the caller's own tenant namespace; signed links work with authentication enabled.
- Artifact download tokens no longer fall back to a hardcoded signing key.
- Deploy scripts and `cloudbuild.yaml` default to API-key authentication with secrets from Secret Manager.

### Added
- `MARKETING_MCP_METADATA_SNAPSHOT`: durable SQLite snapshot restored at startup and refreshed on an interval and at shutdown.
- `docs/OPERATIONS.md` single-instance runbook.

### Changed
- Container runs as a non-root user with a `HEALTHCHECK`; `docker-compose.yml` starts in API-key mode on the correct port.
- `scripts/deploy_cloud_run.sh` is the single deploy path; `scripts/fast_deploy.sh` forwards to it.
- Production readiness documentation is machine-audited against executed evidence bundles (`render_production_readiness.py --check`).
- Security architecture updated to reflect verifier-only credential persistence and request-scoped execution contexts.
- Full fast test suite: 446 passed in ~23s with 0 ruff and 0 pyright errors.

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
