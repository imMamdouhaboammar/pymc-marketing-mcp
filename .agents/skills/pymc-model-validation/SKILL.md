---
name: pymc-model-validation
version: 1.0.0
description: Use when a user asks about cross-validation, prior sensitivity, comparing MMM specifications, information criteria, or selecting among fitted models.
---

# PyMC Model Validation

Use the server tools rather than manually ranking models from copied metrics.

## Different questions, different tools

- `cross_validate_mmm`: out-of-sample time-slice predictive performance.
- `evaluate_prior_sensitivity`: whether commercial conclusions materially change under the server’s supported prior/transform perturbations.
- `compare_models`: stored diagnostics, predictive evidence, configuration, and lineage comparison.
- `select_best_model`: the server’s model-selection operation using the criteria/weights its current contract exposes. This capability is experimental; report its diagnostics and do not treat its selected ID as automatic decision approval.

Good convergence is not predictive accuracy. Predictive accuracy is not prior robustness. Prior robustness is not causal identification. None of them alone proves commercial usefulness.

Before a comparison, preserve dataset/model lineage and let the server enforce compatibility. If an MCP comparison operation exists, do not hand-rank models in the LLM. A model selected by comparison must still have its own acceptable `diagnose_mmm` state before gated decision use.

`archive_model` is an administrative lifecycle operation, not a normal analytical recommendation; use it only when explicitly requested and authorized. Report uncertainty and Pareto/selection warnings returned by the server. Do not import generic ArviZ behavior that the MCP tool does not expose.
