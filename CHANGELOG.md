# Changelog

All notable changes to `pymc-marketing-mcp` are documented in this file.

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
- **Diagnostic Engine**: Calibrated R-hat (<= 1.05 for warning, <= 1.01 for clean approval) and bulk ESS thresholds (>= 50 for hard gate, >= 400 for clean approval) with posterior predictive checks.

### Fixed
- Fixed `_response_values` in adapter to correctly unpack `xarray.Dataset` responses containing `total_media_contribution_original_scale`.
- Fixed SQLite scenario persistence schema constraint.
- Fixed MCP resource lookup domain error propagation.

## [0.2.0] - 2026-08-20

### Added
- Initial decision integrity architecture and diagnostic gating.
- Separate total iROAS and marginal iROAS endpoints.
- Multidimensional panel validation and cell-level scenario evaluation.
