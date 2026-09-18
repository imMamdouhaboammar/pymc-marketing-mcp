# Coding Agent Brief: Implement the Revised Core Capability Roadmap

Repository: `https://github.com/imMamdouhaboammar/pymc-marketing-mcp`

## Mission

Implement the revised core-capability roadmap without rebuilding capabilities that already exist and without creating architecture that conflicts with the repository's active Unified Platform migration.

## Mandatory first step: re-audit before coding

The baseline for this plan is commit `1182e64a659ed341abad2a7c17ce88f0d9489a56`, but the repository is moving quickly.

Before changing code:

1. inspect current HEAD, open PRs, recent commits and relevant GitHub bot review comments
2. classify every planned item as `already implemented`, `partial`, `missing`, `superseded`, or `wrong owner`
3. search source, tests, capability registry, migration ledger, failure lessons and docs
4. do not implement any task that is already satisfied
5. if architecture has moved, update this plan before coding

## Existing systems you must preserve

Do not rebuild or bypass:

- `MarketingDataIntelligenceEngine`
- `SemanticDatasetContract`
- `ModelingContract`
- current channel-prior infrastructure
- `evaluate_prior_sensitivity`
- lift-test calibration and model lineage
- decision gate and approved/caution/rejected semantics
- budget optimizer robustness / multi-start behavior
- panel MMM dimensions and cell-level constraints
- carryover-aware flighting
- CLV discounting
- artifact manifests and artifact lifecycle
- capability registry and evidence-backed maturity
- migration ledger

## Ownership rule

The migration ledger currently points modeling/decision capabilities toward future owners such as `packages/python/marketing_core/*`, but those target directories were not present in the audited repository state.

Therefore:

- if the target owner exists in the active worktree and cutover is active, implement there and keep MCP as an adapter
- otherwise, extend the current canonical scientific/domain seam and update migration metadata so later cutover is straightforward
- never create a duplicate service just to imitate a future directory layout

## Execution order

### Phase A: Financial semantics and posterior utility

First extract the existing financial concepts into one typed domain contract while preserving current net-profit flighting behavior.

Then add a minimal posterior utility abstraction on top of existing posterior response samples and optimizer paths. Expected-response mode must reproduce existing behavior. Add risk-aware objectives only after scientific tests establish their semantics.

### Phase B: Evidence-aware priors and experiments

Build prior recommendations on top of `channel_priors` and `evaluate_prior_sensitivity`. Recommendations must include evidence, confidence, assumptions, alternatives, provenance, prior-predictive requirements and sensitivity requirements. No hidden defaults.

Add a persistent Experiment Evidence Registry and allow calibration to reference experiment IDs. Preserve inline lift-test compatibility during migration.

### Phase C: Temporal accountability

Add a source-period Response Cohort Ledger. Reuse the fitted model's real adstock/carryover semantics and reconcile the ledger back to aggregate response. Do not create a second simplified carryover model.

### Phase D: Long-term effects

Write a scientific RFC first. Introduce a pluggable long-term engine interface. Bayesian VAR may be the first experimental implementation only if the scientific review confirms it. Long-term outputs require their own diagnostics and must avoid double counting when linked to MMM.

### Phase E: Portfolio effects

Build on panel MMM/dimensional foundations. Add typed portfolio entities and effect relationships. Direct effects first, then halo/cannibalization/shared-brand effects only with explicit evidence or learned hierarchical structure.

## Scientific requirements

- use official PyMC-Marketing / PyMC APIs where possible
- do not copy proprietary Simba implementation or constants
- keep statistical truth in Python/scientific libraries
- use real non-mocked statistical tests for new model-dependent behavior
- write synthetic recovery tests for new statistical model families
- define and test invariants before exposing public tools
- fail closed on missing diagnostics or ambiguous units

## Decision integrity requirements

Every new decision result must expose:

- model/run identity
- dataset identity
- decision gate state
- requested/resolved/effective configuration
- objective definition
- financial assumptions where applicable
- uncertainty evidence
- extrapolation/support warnings
- provenance and package versions

## TDD and compatibility

Use test-first implementation. Preserve existing MCP contracts unless a versioned migration is explicitly required. Add compatibility adapters for legacy fields such as `margin_pct` when extracting canonical financial contracts.

## Capability lifecycle

For each new public capability:

1. implement domain/scientific logic
2. add service/adapter exposure only at the correct owner seam
3. enforce auth/tenant isolation
4. add decision gate if required
5. add executable tests
6. register capability as experimental
7. update migration ledger
8. regenerate capability docs
9. run docs drift checks
10. promote to stable only when evidence requirements are satisfied

## Verification

At minimum run the repository's current equivalents of:

- fast/unit/integration suite
- statistical suite for touched model-dependent behavior
- Ruff
- Pyright
- capability inventory drift check
- documentation drift check
- migration-ledger contract tests

Do not mark production or scientific readiness green from planning docs alone.

## Stop conditions

Stop and update the plan rather than forcing implementation when:

- a requested feature already exists under a different name
- the active branch has completed Unified Platform cutover for that domain
- an upstream PyMC-Marketing API makes the planned custom implementation unnecessary
- a proposed financial or statistical objective has ambiguous units or unsupported scientific semantics
- the only way forward would duplicate statistical authority or bypass the decision gate
