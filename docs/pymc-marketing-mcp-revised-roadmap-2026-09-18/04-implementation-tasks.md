# Implementation Tasks

## T0 - Repository re-baseline and ownership map

- Pin implementation work to a fresh commit before coding.
- Re-run repository gap search because this project changes rapidly.
- Update the capability migration ledger for every new public capability.
- Record current owner, future owner, cutover gate and adapter-compatibility requirement.
- Do not create `packages/python/marketing_core/*` locally unless the Unified Platform target package exists in the active branch/worktree.

## T1 - Financial contract extraction

- Locate all current financial semantics: `margin_pct`, net-profit logic, CLV discounting, target-ROAS handling.
- Define a typed `FinancialAssumptions` or equivalent domain contract.
- Add compatibility migration from existing public fields.
- Refactor flighting to consume the canonical financial contract with behavior-preserving tests.
- Extend ordinary simulation/budget optimization to consume the same contract.
- Add provenance fields for financial assumptions and objective definition.

Tests:

- existing flighting statistical tests remain green
- legacy `margin_pct` results are equivalent within tolerance
- inconsistent financial units fail closed
- NPV/discount-period conventions are explicit and tested

## T2 - Posterior utility objective abstraction

- Introduce an objective protocol that receives posterior outcome samples plus financial assumptions and returns utility.
- Start with existing expected response as the compatibility objective.
- Add one risk-aware objective only after a scientific RFC and invariant tests.
- Keep optimizer constraints, budget conservation, multi-start recovery and extrapolation warnings unchanged.
- Add objective metadata to result provenance.

Tests:

- expected-response mode reproduces current allocation within tolerance
- risk-neutral parameterization collapses to expected-value behavior where mathematically applicable
- risk-aware objectives react monotonically to worse downside distributions in controlled fixtures
- blocked diagnostic state cannot invoke new objectives

## T3 - Intelligence integration, not replacement

- Extend `MarketingDataIntelligenceEngine` only for diagnostics that are demonstrably absent.
- Candidate additions after fixture review: structural-break/change-point evidence, target leakage checks, control near-zero variance, stronger spend/activity mismatch evidence, intervention contamination.
- Every new issue must define evidence, why it matters, recommended action, blocking policy and affected analysis.
- Feed issue effects into existing `SuitabilityAssessment` / `IdentifiabilityRisk` rather than creating a second readiness object.

Tests:

- adversarial fixtures
- false-positive fixtures
- clean-data regression
- stable ModelingContract generation

## T4 - Evidence-aware prior recommendations

- Reuse `ChannelPriorConfig` and current prior builders.
- Define `PriorRecommendation` contract.
- Add evidence providers separately from recommendation policy.
- Require prior-predictive validation before a recommendation can be marked usable.
- Integrate with existing prior-sensitivity workflow.
- Persist accepted recommendation provenance in effective model config.

Tests:

- recommendations never silently mutate a fit request
- user override always remains explicit
- unsupported evidence yields low confidence or no recommendation
- prior sensitivity can compare recommended vs alternative priors

## T5 - Experiment Evidence Registry

- Add repository/storage protocol for experiment evidence.
- Add tenant/project authorization and immutable provenance.
- Add create/get/list/archive operations.
- Extend calibration input to accept experiment IDs as well as inline measurements during compatibility period.
- Persist model lineage links to experiment IDs.
- Let `recommend_next_measurement` inspect evidence coverage.

Tests:

- tenant isolation
- immutable evidence history
- inline-vs-registry calibration parity
- rejected/invalid experiment metadata fails before sampling

## T6 - Requested / resolved / effective config

- Extend model/decision provenance schemas.
- Capture defaults and transformations actually applied by the adapter.
- Detect unsupported or ignored requested fields.
- Fail or warn according to contract instead of silently dropping configuration.

Tests:

- round-trip snapshot
- explicit default resolution
- unknown field behavior
- adapter parity across legacy/current code paths

## T7 - Response Cohort Ledger

- Build from fitted model transform semantics, not a separate simplified adstock formula.
- Define source-period x destination-period decomposition contract.
- Reconcile ledger totals to aggregate posterior contribution within tolerance.
- Add optional financial projection using the canonical financial contract.
- Store large ledgers as artifacts with manifest/provenance.

Tests:

- conservation / reconciliation invariant
- multiple supported adstock families
- zero-spend periods
- multidimensional model behavior
- artifact-size path

## T8 - Long-term effects RFC and prototype

- First write a scientific RFC with references, identification assumptions, diagnostics and failure modes.
- Define `LongTermEffectsEngine` protocol.
- Prototype Bayesian VAR only behind experimental capability status.
- Add IRF and long-run multiplier outputs.
- Define explicit MMM linkage semantics without double-counting short-term effect.
- Create a separate diagnostic/decision policy for long-term outputs.

Tests:

- synthetic parameter recovery
- stability / stationarity diagnostics where model family requires them
- impulse-response sign/magnitude recovery under controlled data
- linkage reconciliation and no-double-counting invariant

## T9 - Portfolio effect model

- Start from current panel MMM dimensional infrastructure.
- Define portfolio entity graph and effect taxonomy.
- Support direct effect first.
- Add halo/cannibalization only with explicit priors/evidence and identification tests.
- Add portfolio-level objective only after model diagnostics pass.

Tests:

- hierarchy/coordinate preservation
- direct-only model reduces to existing panel behavior
- cross-entity effects cannot appear without declared structure
- portfolio optimization conserves total budget and respects entity/channel bounds

## T10 - Public surface, docs and migration proof

For every exposed capability:

- register in `capabilities.py`
- add contract test
- add statistical evidence test where scientific
- update migration ledger
- regenerate `docs/CAPABILITIES.md`
- run docs drift check
- update skill/tool mapping only when capability is executable
- keep new capability `experimental` until executable evidence is attached
