# Failure Lesson 12: Saturation Curve Rendering, Response Curve Granularity, and Decision Identifiability Caveats

**Date**: 2026-09-16  
**Severity**: High (Plot rendering failure, decision-quality risk, and endpoint over-aggregation)  
**Components**: `PlottingService`, `PyMCMarketingAdapter`, `DecisionService`, `FastMCP Tools`  
**Test Context**: Claude.ai Chat Session executing PyMC Marketing MCP full capability verification on 243-row x 6-channel daily panel data.

---

## 1. Problem Context

During independent end-to-end verification of the deployed Cloud Run MCP connector (`pymc-marketing-mcp`), an external evaluator ran the complete Bayesian marketing workflow (data registration, inspection, validation, MCMC sampling, ArviZ diagnostics, channel contributions, marginal iROAS, response curves, posterior plots, and budget optimization).

The evaluation confirmed the core statistical engine functioned with real MCMC sampling, but revealed four significant defects and two UX gaps:
1. **Saturation Curves Plot Failure (TypeError)**: Calling `get_posterior_plots(plot_types=["saturation_curves"])` failed with `TypeError: Transformation.plot_curve_hdi() got an unexpected keyword argument 'ax...'` and misleading `next_action: "Ensure the model was fitted with posterior predictive samples"`.
2. **Collapsed Response Curves**: `get_response_curves` collapsed a 4D posterior array `(chain, draw, channel, spend_grid)` across 6 channels and 100 spend points into 3 scalar summary numbers (`median`, `lower_94`, `upper_94`), making it impossible to see per-channel curves.
3. **Budget Optimizer Blind to Upstream Sparse Data Risks**: `validate_dataset` flagged `google_spend` with `LONG_ZERO_SPEND_RUN` (109 zero-spend days out of 243). However, `optimize_budget` recommended allocating $4,981 to Google (from $0 baseline) predicting 714% uplift with 99.975% probability without any caveat or warning about this sparse history.
4. **Schema Discoverability**: In certain client sessions, tool schemas generated without explicit parameter descriptions obscured `content` and `filename` parameters.
5. **Phantom Tool Suggestion**: `inspect_dataset` and `validate_dataset` suggested `repair_dataset` as a `next_action`, which was not an exposed tool on the server.

---

## 2. Root Cause Analysis

### A. Plotting Wrapper Kwarg & Positional Signature Mismatch
In `PlottingService._render_saturation_curves`:
```python
# BROKEN ORIGINAL
if hasattr(model, "saturation") and hasattr(model.saturation, "plot_curve_hdi"):
    fig, axes = plt.subplots(figsize=(10, 4))
    model.saturation.plot_curve_hdi(ax=axes)
```
- In PyMC-Marketing 1.0.0+, `Transformation.plot_curve_hdi` requires `curve: xr.DataArray` as the first positional argument.
- The keyword parameter is named `axes` (an ndarray of axes), NOT `ax`.
- Furthermore, PyMC-Marketing's `model.plot.saturation_curves(curve=curve)` is the canonical API that generates multi-channel subplots with scatter points and credible intervals.

### B. Premature Flattening in Response Curves
In `PyMCMarketingAdapter.response_curves`:
```python
# BROKEN ORIGINAL
def response_curves(self, model) -> dict[str, Any]:
    if hasattr(model, "sample_saturation_curve"):
        da = model.sample_saturation_curve()
        return {"summary": self._small_summary(da), "method": "sample_saturation_curve"}
```
`_small_summary` called `np.nanmedian(arr)` on the flattened 4D array, throwing away the channel coordinate and spend grid dimension.

### C. Siloed Decision Pipeline (Identifiability Gaps)
In `DecisionService.optimize` and `simulate`:
- The service only invoked `check_extrapolation_risk`.
- It never queried the dataset validation findings stored on the model's dataset (`LONG_ZERO_SPEND_RUN`, `EXTREME_OUTLIERS`, `HIGH_CHANNEL_CORRELATION`).
- The optimizer blindly assumed all fitted posterior curves were equally trustworthy, creating severe decision-quality risk for channels with limited historical spend variance.

---

## 3. Architecture & Code Solution

### 1. Robust Multi-Strategy Saturation Curves Rendering
`PlottingService._render_saturation_curves` now employs a resilient 3-tier strategy:
1. **Strategy 1**: Official `model.plot.saturation_curves(curve=curve)` with posterior curve sampled via `model.sample_saturation_curve(original_scale=False)`.
2. **Strategy 2**: `model.saturation.plot_curve_hdi(curve=curve, axes=axes_arr)` with correct positional and keyword arguments.
3. **Strategy 3**: Parameter posterior histograms with clear channel labels as fallback.
4. **Contextual Next Action**: Replaced hardcoded posterior-predictive errors with plot-specific next action guidance.

### 2. Full Per-Channel Response Curve Resolution
`PyMCMarketingAdapter.response_curves` now slices the 4D posterior DataArray by channel:
- Produces `channels: {channel_name: {spend_grid, median_response, lower_94, upper_94, max_response_median, half_saturation_spend}}`.
- Maintains top-level `summary` for backward compatibility while providing full per-channel curve coordinates for callers.

### 3. Upstream Identifiability Warning Carry-Forward
`DecisionService` introduces `_collect_channel_identifiability_warnings`:
- Cross-references channels receiving budget allocations against upstream dataset validation findings.
- Generates high-priority `IDENTIFIABILITY_RISK` warnings if a channel with `LONG_ZERO_SPEND_RUN`, `EXTREME_OUTLIERS`, or `HIGH_CHANNEL_CORRELATION` receives significant budget.
- Annotates every channel with a `channel_confidence` score (`high`, `low_sparse_history`, `medium_outliers`).
- Embeds caveats directly into the response payload and top-level MCP envelope warnings.

### 4. Explicit Tool Schema & Next-Action Cleanup
- Updated `register_dataset` using typing `Annotated[str | None, Field(description="...")]` to guarantee that MCP clients discover `content`, `filename`, `content_base64`, `url`, and `path`.
- Removed phantom `repair_dataset` suggestions from `inspect_dataset` and `validate_dataset`, replacing them with `register_dataset`.

---

## 4. Verification Evidence

1. **Unit Test Suite** (`tests/unit/test_revision2_fixes.py`):
   - `test_register_dataset_schema_has_content_and_descriptions`: PASSED
   - `test_inspect_and_validate_do_not_suggest_phantom_repair_dataset`: PASSED
   - `test_saturation_curves_renders_without_type_error`: PASSED
   - `test_response_curves_returns_per_channel_trajectories`: PASSED
   - `test_model_not_diagnosed_error_has_evidence_and_next_action`: PASSED
   - `test_optimize_budget_surfaces_channel_identifiability_warnings`: PASSED
2. **Statistical MCMC Suite** (`tests/statistical/test_plot_summary_consistency.py`):
   - Verified that `saturation_curves` renders a valid PNG against a real 52-week MCMC fitted model without errors.
3. **Platform Check Runner** (`./check.sh`):
   - All 83+ tests green across Rust, TypeScript, Python contract, storage, and security layers.
