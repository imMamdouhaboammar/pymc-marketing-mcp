# Statistical Testing Methodology

Bayesian marketing models are stochastic, so release-critical tests focus on behavioral/statistical invariants rather than exact posterior samples

This document describes methodology. Current pass/fail counts belong in machine-generated release evidence, not here

## Test layers

### Unit tests

Use deterministic code paths for schemas, allocation contracts, diagnostics classification, posterior summary helpers, error handling and repository/state-machine behavior

### Contract tests

Assert public safety properties such as

- decision-grade tools reject a model whose persisted diagnostic state is rejected
- descriptive outputs remain clearly labeled when used on a rejected model
- model/dataset identity requirements are enforced
- public tool/resource discovery matches the capability registry

### Integration tests

Exercise MCP protocol paths, persistence lifecycle, save/load and service wiring

Remote security/recovery claims require end-to-end integration tests rather than isolated helper tests

### Statistical tests

Run real PyMC-Marketing/PyMC computation for claims whose semantics depend on the upstream library

Release-critical statistical behavior must not be proven only with mocks

## Statistical invariants

Examples currently covered by the suite include

1. finite posterior quantities and valid interval ordering
2. probability outputs bounded in `[0,1]`
3. near-zero spend changes producing near-zero response changes within numerical tolerance
4. saturated-channel marginal response remaining below appropriate average/low-spend response behavior
5. exact budget conservation within numerical tolerance
6. lower/upper allocation constraints respected
7. dynamic flighting preserving time/carryover semantics
8. save/load preserving posterior summaries
9. calibration creating child lineage without mutating the parent
10. model comparison refusing incompatible dataset fingerprints
11. channel-specific transform configuration changing real model construction
12. posterior summaries aggregating over the intended named dimensions

## Diagnostic classification assertions

Tests must match the current diagnostic engine policy

Hard rejection

- divergences `> 0`
- max R-hat `> 1.05`
- min ESS `< 50`
- posterior-predictive coverage `< 0.50`

Caution when hard rejection is absent

- max R-hat `> 1.01` and `<= 1.05`
- min ESS `< 400` and `>= 50`
- coverage `< 0.80` and `>= 0.50`
- NRMSE `> 1.0`
- absolute lag-1 residual autocorrelation `>= 0.70`

Changing these cutoffs requires focused diagnostic tests plus review of `docs/DECISION-INTEGRITY.md` and `docs/STATISTICAL-SAFETY.md`

## Execution profiles

Do not document fixed wall-clock runtimes. Sampling time depends on hardware, model shape, dimensions, priors and upstream library versions

Use repository markers instead

```bash
# deterministic and bounded suite
uv run pytest -m "not statistical" -v

# real statistical suite
uv run pytest -m statistical -v

# full suite
uv run pytest -v
```

For release candidates, statistical tests run in the dedicated statistical CI lane defined by the hardening plan. The release evidence must record machine/environment/dependency identity and command results

## Randomness and tolerances

- use deterministic seeds where the upstream API allows them
- assert intervals, ordering, conservation and bounded error rather than exact posterior draw arrays
- use explicit tolerances justified by the invariant under test
- do not fix a flaky statistical test by rerunning until it passes
- investigate whether nondeterminism comes from the model, test fixture, parallel execution or upstream runtime

## Synthetic fixtures

Synthetic data is valid for controlled regression tests when the data-generating process is explicit and the tested claim is appropriate for synthetic evidence

The suite contains single-dimensional MMM, multidimensional panel and lift/calibration fixtures

Synthetic evidence does not replace production data validation or establish causal identification for a real business dataset

## Real-library requirement

The following kinds of claims require real PyMC-Marketing execution before they can be marked stable

- model construction semantics
- incrementality/iROAS semantics
- budget response and optimization behavior
- dynamic flighting behavior
- CLV model-family behavior
- model comparison behavior
- save/load posterior invariants

## Release evidence rule

A Markdown statement such as "27 statistical tests passed" is historical information unless it is linked to machine-generated evidence for the exact commit being assessed

Current release truth is generated under `docs/release-evidence/`
