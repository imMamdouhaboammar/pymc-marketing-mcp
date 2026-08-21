# Statistical Safety

## Non-negotiable rules

1. PyMC-Marketing computes model quantities. The LLM explains them.
2. A fitted model is not automatically a decision model. Diagnostics must run first.
3. Divergences or R-hat above 1.01 reject the model for budget decisions by default. Low ESS is surfaced explicitly.
4. Posterior predictive checks are part of the gate. Catastrophically poor predictive coverage rejects the model; weaker predictive evidence produces caution rather than a fabricated accuracy score.
5. Posterior quantities are summarized with distribution-aware fields. The interface must not invent decimal precision or unsupported confidence scores.
6. Total iROAS and marginal iROAS are delegated to PyMC-Marketing's incrementality API.
7. A requested scenario is sampled as that scenario. The optimizer is not used as a substitute for counterfactual evaluation.
8. An optimized allocation is not returned alone. The server also samples baseline and recommended response distributions and compares them.
9. Multidimensional budget cells require exact dimension selectors. Ambiguous aggregate bounds fail closed.
10. Recommendations retain model ID, dataset identity, package versions, configuration, and persisted diagnostic state.

## What this gate does not prove

Sampler and posterior-predictive health do not prove causal identification, correct controls, experiment calibration, or transportability to spend levels outside the observed range. Those remain modeling assumptions and must be communicated as such.

The current predictive thresholds are a product decision policy. They are not presented as universal scientific cutoffs.
