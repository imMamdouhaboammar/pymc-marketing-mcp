# Statistical Safety

## Non-negotiable rules

1. PyMC-Marketing computes model-dependent quantities. The LLM explains evidence and must not fabricate posterior values
2. A fitted model is not automatically a decision model. `diagnose_mmm` must establish the persisted decision state first
3. Decision-grade tools are blocked on a rejected model. The current set includes incremental ROAS, budget simulation, budget optimization and flighting optimization
4. Descriptive outputs may still be inspected for diagnosis on rejected models, but the rejected state must remain visible
5. Divergences greater than 0 are a hard rejection signal in the current product policy
6. Maximum R-hat greater than 1.05 is a hard rejection signal. R-hat greater than 1.01 and at most 1.05 produces caution rather than automatic rejection
7. Minimum ESS below 50 is a hard rejection signal. ESS below 400 but at least 50 produces caution
8. Posterior-predictive coverage below 0.50 is a hard rejection signal. Coverage below 0.80 but at least 0.50 produces caution
9. Posterior-predictive NRMSE above 1.0 and absolute lag-1 residual autocorrelation at or above 0.70 are caution signals in the current policy
10. Posterior quantities are summarized with distribution-aware fields. The interface must not invent decimal precision, confidence scores or causal certainty
11. Total and marginal iROAS are delegated to PyMC-Marketing incrementality APIs and require a decision-approved model
12. A requested spend scenario is evaluated as that scenario. The optimizer is not used as a substitute for counterfactual evaluation
13. An optimized allocation is not returned as a naked recommendation. The model response, uncertainty, constraints, warnings and provenance remain part of the result
14. Multidimensional budget cells require exact dimension selectors. Ambiguous aggregate bounds fail closed
15. Calibration creates lineage rather than silently mutating the original model
16. Model and dataset fingerprints protect comparisons and reload/reuse decisions from accidental identity drift
17. Extrapolation warnings must remain visible even if a user asks the agent to hide them

## Decision policy versus universal statistics

The thresholds above are product safety policy for this service

They do not claim that every Bayesian workflow in every domain must use the same cutoffs. A production change to these thresholds is a decision-policy change and requires statistical tests, documentation updates and review

## What diagnostic approval does not prove

Sampler and posterior-predictive health do not prove

- causal identification
- correct control-variable selection
- sufficient channel variation
- correct business interpretation
- unbiased lift-test evidence
- transportability to materially different markets or spend levels
- absence of model misspecification

Those remain modeling assumptions and limitations that must be communicated

## Agent behavior

Agents must use tools for model-dependent claims and retain warnings/provenance in the final response

They must not

- invent iROAS without a fitted approved model
- substitute average return for marginal iROAS when answering a next-dollar question
- call an optimization tool after a rejected diagnostic gate
- present correlation as causal proof
- suppress infeasibility or extrapolation warnings
- mark an eval or release gate passed without executable evidence

See `docs/DECISION-INTEGRITY.md` for the complete decision contract
