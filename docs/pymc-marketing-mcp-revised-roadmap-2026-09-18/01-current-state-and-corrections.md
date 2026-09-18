# Current State and Corrections

## Audit baseline

The review was performed against commit `1182e64a659ed341abad2a7c17ce88f0d9489a56` on `main`.

The repository has materially evolved since the earlier roadmap. The biggest change is not one isolated feature, but a shift toward a canonical scientific core plus a Unified Platform migration path.

## What already exists and must not be rebuilt

### 1. Marketing Data Intelligence and Identifiability

This is no longer a missing capability.

The repository now has `MarketingDataIntelligenceEngine` under `src/marketing_mcp/intelligence/engine.py`. It orchestrates:

- structural profiling
- semantic role inference
- target ambiguity handling
- currency inference
- campaign-objective analysis
- channel lifecycle analysis
- market structure analysis
- tracking-quality analysis
- spend variance checks
- channel collinearity checks
- identifiability risk synthesis
- MMM suitability
- panel-MMM suitability
- CLV suitability
- transformation planning
- downstream `ModelingContract` generation

The engine emits an authoritative `SemanticDatasetContract` with issues, suitability verdicts, transformations, clarification requests, known risks, and a modeling contract.

Therefore, the old task "build a Data Quality / Identifiability Engine" is deleted.

The remaining work is to deepen specific diagnostics and connect their decision impact more tightly to downstream policy.

### 2. Prior infrastructure

The repository already supports:

- per-channel `channel_priors`
- a default prior map in `adapters/mmm_config.py`
- prior validation
- `evaluate_prior_sensitivity`
- real sampling tests for prior sensitivity
- a `prior_selection` insight category

Therefore, the old task "add a prior system" is deleted.

The remaining gap is an evidence-aware prior recommendation layer that proposes priors with explicit evidence, confidence, assumptions, alternatives, and validation requirements before those priors are accepted into a model spec.

### 3. Financial decision logic

The repository already supports financial optimization semantics in flighting:

- `maximize_net_profit`
- `margin_pct`
- `compute_net_profit`
- gross revenue / margin outputs
- target ROAS constraints
- CLV discounting via `discount_rate`

Therefore, the old task "build a Financial Decision Layer from scratch" is incorrect.

The remaining gap is to unify financial semantics across ordinary budget optimization, simulation, flighting, CLV, and future portfolio decisions. Contribution margin, gross margin, variable cost, acquisition economics, CLV, discounted value, profit and NPV should be represented through one typed financial contract rather than being embedded in isolated tools.

### 4. Carryover-aware decision logic

The repository already has dynamic multi-period flighting with adstock carryover. It also explicitly samples response distributions with `include_carryover=True` in budget/scenario paths.

Therefore, the old task "add carryover accounting" is too broad and partially redundant.

The genuine missing concept is a source-period response ledger: an auditable decomposition mapping spend in period t to response in future periods, with optional financial discounting. This is different from merely using carryover during optimization.

### 5. Multi-dimensional / market support

The repository already supports panel MMM dimensions, cell-level budget constraints, market-structure analysis, and recommends hierarchical panel modeling when appropriate.

Therefore, the old task "add multi-market modeling" is too broad.

The remaining gap is cross-entity portfolio semantics: explicit portfolio, brand, product, market or business-unit entities plus direct effect, shared/masterbrand effect, halo/spillover and cannibalization. Existing `dims` are a useful substrate but are not yet a portfolio-effect model.

### 6. Experiment calibration

The repository already has `calibrate_mmm`, lift-test measurements, model lineage, parent-model tracking, and statistical tests for calibration.

Therefore, the old task "add experiment calibration" is deleted.

The remaining gap is a persistent Experiment Evidence Registry that stores experiment identity, methodology, dates, geography, treatment/control, effect estimate, uncertainty, source, quality metadata, provenance, and links those records into calibration lineage and measurement planning.

### 7. Decision safety

The repository already has a mature decision gate. Existing decision paths enforce approved / approved-with-caution / rejected semantics and fail closed for blocked models.

Every new decision capability must reuse the same policy seam. No new optimizer, financial objective, long-term model, or portfolio recommendation may bypass diagnostic state.

### 8. Platform migration direction

The repository now contains a capability migration ledger that maps current MCP capabilities to future target owners such as:

- `packages/python/marketing_core/modeling`
- `packages/python/marketing_core/decisions`
- `packages/python/marketing_core/datasets`
- `packages/python/marketing_core/diagnostics`
- `services/analytics-worker/*`
- `apps/gateway/resources`

The current repository does not yet contain those target directories. Consequently the roadmap must not blindly create a second architecture inside this repository.

Implementation rule:

- if work happens before Unified Platform cutover, extend the current canonical scientific/domain seams and record the future target owner in the migration ledger
- if work happens after the target package exists, implement in the target owner and keep MCP as a compatibility adapter

### 9. Capability-count documentation drift

The checked `src/marketing_mcp/capabilities.py` currently contains more entries than the README summary claims. The roadmap should treat the registry and generated inventory as source of truth and include a docs-drift verification step after every capability change.
