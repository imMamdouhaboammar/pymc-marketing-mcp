# Scientific Contract Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every statistical and decision capability in v0.4.x match its public contract and prove the behavior with executable real-library tests before production infrastructure work proceeds.

**Architecture:** Keep PyMC-Marketing behind adapter boundaries, but strengthen those boundaries with typed model configuration builders and explicit result contracts. Separate statistical computation from presentation. Use small real statistical fixtures for release-critical behavior and reserve mocks for non-statistical failure plumbing only.

**Tech Stack:** PyMC-Marketing 1.0.0, PyMC 6, ArviZ 1.3, xarray, NumPy, pandas, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Do not weaken existing diagnostics thresholds to make tests pass.
- Do not compute posterior claims in the MCP or agent layer.
- Every optimization must report uncertainty and constraint status.
- Every test claiming statistical support must use the real PyMC-Marketing implementation.
- Preserve model lineage and dataset fingerprints across refits/calibration.

---

### Task 1: Replace transform-only configuration with a real MMM model configuration builder

**Files:**
- Create: `src/marketing_mcp/adapters/mmm_config.py`
- Modify: `src/marketing_mcp/adapters/pymc_marketing.py`
- Modify: `src/marketing_mcp/schemas/models.py`
- Test: `tests/unit/test_mmm_config_builder.py`
- Test: `tests/statistical/test_channel_specific_config.py`

**Interfaces:**
- Produces: `build_mmm_init_kwargs(config: FitMMMInput | dict) -> dict[str, Any]`
- Produces: `build_model_config(config: FitMMMInput | dict) -> dict[str, Any]`
- Consumes: global adstock/saturation configuration and per-channel overrides.

- [x] Write failing tests proving that two channels can receive different prior parameters in the resulting model configuration.
- [x] Extend `ChannelPriorConfig` so it represents actual PyMC-Marketing prior/model configuration values rather than only transform class selection.
- [x] Keep transform selection global unless the upstream API supports per-channel transform families directly and that behavior is verified by a real test.
- [x] Map per-channel prior arrays/dimensions using the official channel coordinate rather than constructing separate unsupported transform objects per channel.
- [x] Add validation for shape, channel-name coverage, positive-only parameters, and unknown prior names.
- [x] Refactor `PyMCMarketingAdapter.fit()`, cross-validation, and prior-sensitivity model construction to use the same builder.
- [x] Run:

```bash
uv run pytest tests/unit/test_mmm_config_builder.py -v
uv run pytest tests/statistical/test_channel_specific_config.py -v
```

- [x] Commit.

### Task 2: Expand transform configuration only where parameters are real and supported

**Files:**
- Modify: `src/marketing_mcp/schemas/models.py`
- Modify: `src/marketing_mcp/adapters/mmm_config.py`
- Test: `tests/unit/test_adstock_saturation_zoo.py`
- Test: `tests/statistical/test_transform_family_sampling.py`

**Required behavior:**
- transform type names must map to importable PyMC-Marketing 1.0 classes
- transform-specific constructor arguments must be validated
- unsupported combinations fail before sampling

- [x] Replace a one-size `l_max` schema with discriminated or model-validated fields where transforms require different parameters.
- [x] Test each supported transform factory using real classes.
- [x] Add a small sampling smoke matrix for at least one representative from geometric/delayed/weibull/no-adstock and logistic/hill/michaelis/no-saturation families.
- [x] Record unsupported transforms in capability inventory as unsupported rather than silently falling back.
- [x] Commit.

### Task 3: Correct model comparison semantics

**Files:**
- Create: `src/marketing_mcp/domain/model_selection.py`
- Modify: `src/marketing_mcp/services/modeling_service.py`
- Modify: `src/marketing_mcp/schemas/models.py`
- Test: `tests/unit/test_model_selection.py`
- Test: `tests/statistical/test_model_selection_real_idata.py`

**Interfaces:**
- Produces: `compare_information_criteria(idatas, criterion, weighting) -> ModelComparisonResult`

**Schema change:**

Use explicit fields:

```python
criterion: Literal["loo", "waic", "both"] = "loo"
weighting: Literal["stacking", "bb-pseudo-bma", "pseudo-bma"] = "stacking"
```

Keep temporary backward-compatible translation for legacy `method` values with a deprecation warning.

- [ ] Write failing test that `criterion="waic"` reaches `az.compare(..., ic="waic")`.
- [ ] Write failing test that `criterion="loo"` reaches `ic="loo"`.
- [ ] Write failing test that `criterion="both"` returns two separately labeled comparisons.
- [ ] Do not infer criterion from weighting method.
- [ ] Calculate Pareto-k diagnostics only for LOO and expose warning severity.
- [ ] Refuse automatic `best_model_id` when reliability diagnostics make ranking unsafe; return `recommended_model_id=None` plus reason.
- [ ] Add real ArviZ idata test with deterministic generated log likelihood arrays.
- [ ] Commit.

### Task 4: Make CLV contracts model-specific

**Files:**
- Modify: `src/marketing_mcp/adapters/clv_adapter.py`
- Modify: `src/marketing_mcp/services/clv_service.py`
- Modify: `src/marketing_mcp/schemas/models.py`
- Modify: `src/marketing_mcp/mcp/server.py` or the split CLV tool registration module after MCP refactor
- Create: `tests/statistical/test_clv_real_models.py`
- Modify: `tests/unit/test_clv_workflow.py`

**Interfaces:**
- `fit_purchase_model`
- `predict_expected_purchases`
- `predict_probability_alive`
- `fit_value_model`
- `predict_expected_spend`
- `estimate_customer_lifetime_value`

A compatibility wrapper may keep `fit_clv_model` temporarily, but it must return a deprecation warning and route to the model-specific implementation.

- [ ] Normalize arbitrary user column names into the canonical data frame expected by the selected PyMC-Marketing CLV model.
- [ ] Keep BG/NBD frequency and survival outputs separate from Gamma-Gamma monetary outputs.
- [ ] Require a compatible purchase model plus value model for combined CLV.
- [ ] Add real fit/save/load/predict statistical tests for BG/NBD and Gamma-Gamma with small deterministic RFM fixtures.
- [ ] Add a capability-specific test for shifted-beta-geometric only if the pinned PyMC-Marketing class is stable and supports the required API.
- [ ] Verify returned `total_customers` represents the complete population even when `top_n` truncates evidence rows.
- [ ] Commit.

### Task 5: Decide and repair dynamic flighting contract

**Files:**
- Modify: `src/marketing_mcp/domain/decisions/flighting.py`
- Modify: `src/marketing_mcp/services/decision_service.py`
- Modify: `src/marketing_mcp/schemas/models.py`
- Test: `tests/unit/test_flighting_domain.py`
- Create: `tests/statistical/test_flighting_optimization.py`

**Decision rule:**

Implement one of the following before release:

**Preferred:** true channel-by-week optimization.

**Fallback:** rename current behavior to `build_flighting_schedule` and remove all optimization/carryover claims until true optimization exists.

Do not leave the current name and semantics unchanged.

#### Preferred interface

Decision variables:

```text
x[channel, week] >= 0
```

Constraints:
- total budget equality within tolerance
- per-channel weekly min/max
- optional fixed spend cells
- optional blackout weeks
- optional pattern preference as penalty, not as a fake optimizer result
- optional target posterior median iROAS floor

Objectives:
- maximize posterior expected response
- maximize expected net profit
- maximize conservative/risk-adjusted objective using a specified posterior quantile

- [ ] Write a budget-conservation failing test for the current implementation.
- [ ] Write infeasible-constraints test.
- [ ] Write test proving objective choice changes the result on a synthetic response surface.
- [ ] Add a weekly allocation representation that preserves time dimension through response evaluation.
- [ ] Evaluate carryover using the official model response path with week-by-week spend retained.
- [ ] Make `target_iroas_min` a solver constraint, not a post-hoc warning.
- [ ] Return solver status, constraint residuals, baseline comparison, posterior uncertainty, and extrapolation warnings.
- [ ] If the official PyMC-Marketing API cannot safely evaluate sequential weekly response, execute the fallback rename instead of approximating behavior silently.
- [ ] Commit.

### Task 6: Repair statistical plotting aggregation

**Files:**
- Modify: `src/marketing_mcp/services/plotting_service.py`
- Create: `src/marketing_mcp/domain/posterior_summaries.py`
- Test: `tests/unit/test_posterior_summaries.py`
- Test: `tests/statistical/test_plot_summary_consistency.py`

**Interfaces:**
- `summarize_channel_contributions(idata) -> xarray.Dataset`
- `summarize_predictions(idata) -> xarray.Dataset`

- [ ] Move numerical aggregation out of matplotlib code.
- [ ] Aggregate contribution over time/dimensions per posterior draw before computing median/HDI across chain/draw.
- [ ] Preserve panel dimensions explicitly and require the caller to choose aggregate or per-dimension output.
- [ ] For actual-vs-predicted, identify the time dimension by coordinate/name rather than `shape[-1]`.
- [ ] Plot only summaries returned by tested domain functions.
- [ ] Add consistency test comparing plot summary inputs to analytical contribution tool summaries.
- [ ] Commit.

### Task 7: Strengthen decision gate coverage

**Files:**
- Modify: `src/marketing_mcp/services/decision_service.py`
- Modify: `src/marketing_mcp/domain/diagnostics/gate.py`
- Create: `tests/contract/test_decision_gate_contract.py`

- [ ] Enumerate all tools that require an approved model.
- [ ] Ensure contributions, iROAS, response curves, plots, simulation, optimization, flighting, and model-dependent recommendations have an explicit policy rather than accidental differences.
- [ ] Decide which descriptive tools may run on a diagnosed-but-rejected model and document why.
- [ ] Add parameterized contract tests for approved, approved-with-caution, rejected, and not-diagnosed states.
- [ ] Ensure `approved_with_caution` always returns warnings from the diagnostic state.
- [ ] Commit.

### Task 8: Add statistical invariants test pack

**Files:**
- Create: `tests/statistical/test_decision_invariants.py`
- Create: `tests/fixtures/statistical/` datasets as small generated CSV/Parquet fixtures or deterministic fixture factories

**Invariants:**
- zero or near-zero spend change produces near-zero incremental response change within posterior noise tolerance
- a saturated channel shows lower marginal than historical average return on the selected fixture
- optimization respects exact/floor/cap constraints
- model reload preserves posterior summary outputs within numerical tolerance
- calibration creates a new lineage node without mutating the parent model
- comparison rejects different dataset fingerprints even if dataset IDs are manually forged equal

- [ ] Implement fixtures with fixed random seeds.
- [ ] Add explicit statistical tolerances with rationale comments.
- [ ] Mark tests `statistical`.
- [ ] Run the full statistical suite twice to detect flakiness.
- [ ] Commit.

### Task 9: Establish Gate G1

**Files:**
- Create: `tests/release/test_g1_scientific_correctness.py`
- Modify: `docs/PRODUCTION-READINESS.md`
- Modify: `docs/CAPABILITIES.md` through its generator

- [ ] Assert no stable capability is missing statistical evidence when the capability makes a statistical claim.
- [ ] Assert deprecated compatibility tools are marked deprecated in inventory and docs.
- [ ] Run full fast and statistical suites.
- [ ] Mark G1 green only when current-head evidence passes.

## Acceptance Criteria

This plan is complete when:

- channel-specific prior configuration changes real model configuration
- every supported transform has real factory coverage and representative sampling coverage
- LOO/WAIC/weighting semantics are correct and independently tested
- CLV purchase and monetary value models have separate real contracts
- flighting is a real time-preserving optimization or honestly renamed
- plotting summaries are dimension-safe and shared with analytical summaries
- every decision tool has an explicit diagnostics-gate policy
- Gate G1 is green