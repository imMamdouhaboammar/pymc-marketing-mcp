---
name: pymc-mmm-workflow
version: 2.1.0
description: Use when a user wants to fit or continue the principal MMM lifecycle from validated data through diagnosis and downstream evidence.
---

# PyMC MMM Workflow

Operate only through the public MCP API. Do not generate arbitrary PyMC/PyMC-Marketing Python or recreate model calculations in the LLM.

## Lifecycle

1. Complete `pymc-dataset-readiness`: register, inspect, and `validate_dataset` with intended roles.
2. Choose the simplest supported model specification justified by the problem. `fit_mmm` accepts the server’s typed adstock/saturation/sampler configuration; do not invent universal channel-specific priors or “typical” carryover constants.
3. For an interactive fit, call `fit_mmm`. For work expected to outlive a client request, use `submit_fit_mmm_job` and hand off to `pymc-job-resilience`; current jobs are server-managed but the repository does not claim an external durable worker architecture.
4. Use `get_model_status` to confirm the persisted model and provenance.
5. Run `diagnose_mmm`. Diagnosis is mandatory before decision-grade operations.
6. Continue by question: validation/comparison → `pymc-model-validation`; contributions/iROAS/curves → `pymc-incrementality-evidence`; spend decisions → `pymc-budget-optimization`; experiment calibration → `pymc-lift-calibration`; plots/artifacts → `pymc-artifact-delivery`.

## Stop conditions

Stop rather than invent an answer when the dataset is invalid, a model/job did not complete, the model artifact cannot be loaded, diagnostics are rejected for a requested decision operation, or a requested quantity is not returned by a public tool. Descriptive evidence that the server permits on a rejected model must remain labeled non-decision-grade.

MMM evidence is observational unless supported by an appropriate experimental or identification design. A healthy sampler is not causal proof. Follow the shared [scientific answer contract](marketing://skills/references/scientific-answer-contract).
