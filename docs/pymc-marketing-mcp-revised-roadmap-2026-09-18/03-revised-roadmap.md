# Revised Roadmap

## Wave 0 - Architecture alignment before feature work

Purpose: stop the roadmap from creating parallel systems during Unified Platform migration.

Deliverables:

- add a new-feature ownership rule to architecture docs
- for each new capability, record current implementation seam, future target owner, cutover gate and adapter compatibility requirement
- verify capability-registry / generated-doc drift before and after changes
- preserve the Python/PyMC scientific-authority invariant

Exit criteria:

- no feature is implemented in MCP transport code if it belongs in scientific/domain logic
- no new service duplicates `MarketingDataIntelligenceEngine`, `DecisionService`, modeling lineage, artifact manifests, or existing storage protocols

## Wave 1 - Decision utility and unified financial semantics

### A. Posterior Utility Objective Layer

Do not replace `BudgetOptimizerWrapper` or the existing multi-start robustness logic.

Introduce a typed decision objective abstraction that can transform posterior outcome samples into a scalar optimization utility. Candidate objectives:

- expected response
- expected profit
- risk-adjusted expected value
- probability of exceeding a target
- lower-quantile / downside objective
- expected regret
- CVaR-style downside utility where scientifically justified

The first implementation should be intentionally small and evidence-backed. Do not expose every objective until real tests exist.

Key design rule: objective evaluation must consume posterior samples returned by the current model path rather than reimplement model response math.

### B. Financial Semantics Contract

Create one typed financial contract consumed by decision tools, rather than embedding `margin_pct` in one path and `discount_rate` in another.

Suggested concepts:

- KPI unit
- revenue-per-outcome if applicable
- gross margin rate
- contribution margin rate
- variable cost
- acquisition cost
- customer lifetime value reference
- discount rate and period convention
- planning horizon
- profit / NPV semantics

Backward compatibility: `margin_pct` remains supported through an adapter/migration path until public schemas can evolve safely.

Exit criteria:

- existing net-profit flighting behavior remains equivalent under legacy inputs
- ordinary budget optimization can use the same financial objective semantics
- output exposes objective definition and financial assumptions in provenance

## Wave 2 - Evidence-aware modeling inputs

### A. Prior Recommendation Engine

Build on existing `channel_priors` and `evaluate_prior_sensitivity`.

A recommendation is not a hidden Smart Default. It must return:

- recommended prior family and parameters
- parameter/channel target
- evidence source
- reason
- confidence
- assumptions
- alternative priors
- required prior-predictive checks
- sensitivity checks that must pass before use

Do not import Simba heuristic constants as defaults.

### B. Experiment Evidence Registry

Persist experiment evidence as first-class records.

Minimum fields:

- experiment_id
- channel / treatment target
- methodology
- geography / segment
- start/end dates
- treatment/control definition
- spend or exposure delta
- measured effect
- standard error / uncertainty distribution
- source
- evidence quality metadata
- provenance
- tenant/project ownership

Calibration should be able to reference experiment IDs instead of requiring every evidence record to be resubmitted inline.

`recommend_next_measurement` should be able to reason over registered evidence coverage without pretending observational evidence is experimental evidence.

### C. Resolved Configuration Transparency

Persist three layers where applicable:

- requested configuration
- resolved configuration
- effective configuration actually used by PyMC-Marketing / optimizer

This should include model transforms, priors, dimensions, objective definitions and financial assumptions.

## Wave 3 - Temporal accountability

### Response Cohort Ledger

This is not a second flighting optimizer.

Create an auditable decomposition:

`source spend period -> future response periods -> optional financial value`

Use the model's actual transform/carryover semantics. Do not implement a separate geometric-adstock approximation when the fitted model uses another supported adstock family.

Outputs should support:

- channel/source-period cohort
- future response allocation
- cumulative carryover contribution
- optional discounted financial value
- reconciliation back to aggregate model response within tolerance

The ledger should be artifact-friendly because large temporal decompositions may not belong in MCP JSON responses.

## Wave 4 - Long-term effects

Introduce a pluggable `LongTermEffectsEngine` abstraction rather than hardcoding "Simba VAR" into the product model.

Candidate interface:

- `fit()`
- `diagnose()`
- `impulse_response()`
- `forecast_error_variance_decomposition()` where applicable
- `long_run_multiplier()`
- `link_to_mmm()`
- `estimate_total_effect()`

Bayesian VAR can be the first implementation if the scientific review confirms it is appropriate, but the architecture should allow state-space, distributed-lag or other long-term model families later.

Long-term outputs must have their own diagnostic gate and must not inherit MMM decision approval automatically.

## Wave 5 - Portfolio and cross-entity effects

Build on existing panel/dimensional MMM rather than creating a disconnected portfolio service.

Introduce typed entities:

- portfolio
- brand
- product
- market
- business unit

Introduce typed effects:

- direct
- halo / spillover
- cannibalization
- shared/masterbrand

Cross-entity effects should be learned or evidence-backed where possible. No fixed halo coefficient should become a universal default.

Optimization should be able to use portfolio-level objectives only when the underlying cross-entity model has passed its own diagnostics and identification checks.
