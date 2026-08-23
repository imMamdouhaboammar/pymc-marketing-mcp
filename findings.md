# Findings — PyMC Marketing MCP v0.4.x Upgrade Research

## Codebase Findings (2026-08-22)

### Test Suite Baseline
- 46 tests pass in 96.79s (`uv run pytest -v`)
- No failures, 64 expected warnings (ArviZ scalar divide, Numba cache, xarray FutureWarning)
- Multi-core via `pytest-xdist`
- Statistical tests take the longest: `test_real_pymc_mmm_end_to_end_statistical_workflow`, `test_real_multidimensional_mmm_panel_sampling`

### Adapter Architecture (PyMCMarketingAdapter)
- `src/marketing_mcp/adapters/pymc_marketing.py` — 659 lines
- Current model instantiation: `MMM(adstock=GeometricAdstock(l_max=...), saturation=LogisticSaturation(), ...)`
- Both are **hardcoded** in `fit()`, `time_slice_cross_validate()`, and `evaluate_prior_sensitivity()` — all three need parametrization
- `AdstockConfig` schema (schemas/models.py L49-51): only `type: Literal["geometric"]` and `l_max: int` — must expand
- `SaturationConfig` schema (schemas/models.py L54-56): only `type: Literal["logistic"]` — must expand
- `FitMMMInput` (L70-97) uses `AdstockConfig` and `SaturationConfig` as typed fields — schema expansion propagates cleanly

### PyMC-Marketing 1.0 Available Transforms
- **Adstock classes (all importable from `pymc_marketing.mmm`):**
  - `GeometricAdstock` (currently used, `l_max`)
  - `DelayedAdstock` (`l_max`, `l_delay`)
  - `WeibullAdstock` (`l_max`, kind: "PDF"|"CDF")
- **Saturation classes (all importable from `pymc_marketing.mmm`):**
  - `LogisticSaturation` (currently used, no required params)
  - `TanhSaturation` (no required params)
  - `TanhSaturationBaseline` (no required params)
  - `MichaelisMentenSaturation` (no required params)
  - `HillSaturation` (no required params)

### MCP Server Tool Count
- 17 tools registered (verified by `test_mcp_stdio_client_discovery_and_tools`)
- 4 MCP resources (`marketing://datasets/{id}`, `marketing://models/{id}`, `marketing://models/{id}/diagnostics`, `marketing://models/{id}/lineage`)
- Adding visual artifact tools → resources will be: `marketing://models/{id}/plots/saturation`, etc.

### Diagnostic Engine
- `src/marketing_mcp/domain/diagnostics/engine.py` — hard gate thresholds: divergences=0, R-hat<=1.01, ESS>=50
- Soft warnings: ESS<400, coverage<80%, NormPPRMSE>1.0, residual autocorr>=0.7
- These thresholds should remain UNTOUCHED in Phase 1 (adstock/saturation zoo)

### Prior Sensitivity (Current)
- `evaluate_prior_sensitivity()` in adapter uses hardcoded `GeometricAdstock(l_max // 2)` as the alt model
- Once Phase 1 lands (multiple adstock types), prior sensitivity should permute over all supported types, not just geometric

### Storage / Persistence
- SQLite metadata at `metadata.db`; NetCDF `.nc` via `h5netcdf` + `h5py`
- `ModelRecord.config` is a free JSON dict persisted in SQLite — adstock/saturation type stored in `config["adstock"]["type"]` and `config["saturation"]["type"]`
- Migration path: fully backward compatible — existing records with `type: "geometric"` still load correctly

### Visual Artifacts
- ArviZ is transitively installed and provides `az.plot_posterior`, `az.plot_trace`
- PyMC-Marketing provides `model.plot_channel_contribution_share_hdi()`, `model.plot_waterfall_components_decomposition()`
- Matplotlib is available (ArviZ dependency)
- Plan: `matplotlib.use("Agg")` for headless PNG rendering → save to `artifacts/plots/{model_id}/` → expose via MCP resource

### CLV (Phase 3 research)
- `pymc_marketing.clv` namespace exists in PyMC-Marketing 1.0
- Classes: `BetaGeoModel`, `GammaGammaModel`, `ModifiedBetaGeoModel`, `ShiftedBetaGeometricModelIndividual`
- CLV requires RFM transaction data (date, customer_id, frequency, recency, T, monetary_value)
- Separate from MMM — no shared model state, different data shape validation
- New dataset format: must extend `DatasetInspection` schema with CLV-specific candidate column detection

### Dynamic Flighting (Phase 4 research)
- PyMC-Marketing `BudgetOptimizerWrapper` currently used for single-period allocation
- Multi-period flighting: extend to `planning_periods` > 1 with time-varying spend arrays
- Carryover from period N affects saturation in period N+1 (adstock propagation)
- Requires extending `allocation_to_xarray` to handle T x C (time x channel) allocation arrays

### LOO/WAIC Model Comparison (Phase 5 research)
- `arviz.compare({"model_A": idata_A, "model_B": idata_B}, ic="loo")` returns comparison DataFrame
- PSIS-LOO via `az.loo(idata)` — fully available, no new deps
- Bayesian stacking weights via `az.compare(..., method="stacking")`
- Only requirement: both models fitted on the same dataset (same `dataset_id`)
