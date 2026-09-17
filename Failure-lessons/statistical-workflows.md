# Failure Lessons: Statistical Workflow Contracts & Capability Prerequisites

This document captures durable failure lessons, root causes, and architectural invariants for statistical workflow sequencing, model comparison prerequisites, and capability manifest contracts in `pymc-marketing-mcp`.

---

## MODEL-SEL-001: Model Selection Failure Due to Missing Upstream Log-Likelihood

### What happened
A caller fitted two candidate MMM models (e.g. Model A with geometric adstock and Model B with Weibull adstock) using `submit_fit_mmm_job`. After both jobs completed, the caller invoked `compare_models(model_ids=["model_a", "model_b"], method="loo")` to perform Bayesian Leave-One-Out cross-validation model selection. The tool crashed immediately with:
```text
KeyError: 'log_likelihood'
```
Neither model could be compared, forcing the user to discard both artifacts and rerun two 20-minute MCMC fitting jobs from scratch.

### Why it mattered
* **Severe Computational Waste**: Rerunning multi-chain Bayesian MCMC models wastes significant time, electricity, and cloud budget ($10–$50 per run on cloud instances).
* **Broken Pipeline Handoff**: Model selection (LOO / WAIC) is an essential official workflow in marketing science to choose between competing media response theories. Having `compare_models` fail on models produced by the platform's own `fit_mmm` tool violated workflow composability.

### Observable symptom
* `compare_models` failing with unhandled `KeyError` or ArviZ `MissingData` exception.
* Model artifacts missing the `log_likelihood` group in their NetCDF InferenceData groups.

### Initial assumption
Developers assumed that fitting jobs should disable log-likelihood computation by default to optimize sampling speed and reduce NetCDF file size, expecting users to know they needed to re-evaluate log-likelihood later.

### Root cause
* **Status**: Confirmed.
* **Undeclared Downstream Prerequisites**: Downstream workflow tools (`compare_models`) had a hard requirement for point-wise log-likelihood tensors in the ArviZ `InferenceData` object, but the upstream tool (`submit_fit_mmm_job`) defaulted to `compute_log_likelihood=False` without declaring the consequence.
* **Missing Capability Manifest**: Model artifacts lacked a machine-readable capability manifest declaring what downstream analyses the artifact could support.

### Why the system allowed it
The system treated model artifacts as opaque binary blobs rather than typed statistical artifacts with explicit capability contracts.

### Fix
1. **Explicit Capability Manifest in Metadata**: Added a typed `capabilities` list to `ModelMetadata`:
   ```json
   {
     "model_id": "mmm_123",
     "capabilities": [
       "posterior_samples",
       "prior_predictive",
       "log_likelihood",
       "response_curves"
     ]
   }
   ```
2. **Upstream Default Alignment**: Updated `submit_fit_mmm_job` to include `compute_log_likelihood=True` by default for all production model fits.
3. **Fail-Fast Prerequisite Guard**: In `compare_models`, check artifact capabilities before invoking ArviZ:
   - If `log_likelihood` is missing, return a structured `PrerequisiteError("MISSING_CAPABILITY")` explaining exactly how to compute or re-fit with log-likelihood.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_model_capabilities_and_loo_prerequisites`
* Asserts that `compare_models` validates capability manifests and that newly fitted models include `log_likelihood` in their registered capabilities.

### Prevention rule
> **Rule**: If a downstream official workflow requires an artifact capability, the upstream official workflow must either produce it by default or declare that requirement explicitly before fitting. Complex computational artifacts must carry capability manifests declaring what downstream operations they support.

### Reusable lesson
Whenever workflows form a multi-step DAG, artifacts passed between steps must declare explicit capability metadata. Never allow a downstream tool to crash on an opaque missing array inside a third-party object.

### Related failures
* [Failure Lesson 24: Prior Sensitivity Contract Fidelity](./24-prior-sensitivity-contract-fidelity.md)
* [Failure Lesson 28: Statistical Authority Duplication & Fallback AttributeError](./28-statistical-authority-duplication-and-fallback-attribute-error.md)
* `artifact-lifecycle.md`: Artifact Lifecycle & Readiness

---

## Protected Systems & Code References

* `src/marketing_mcp/schemas/models.py`: [`ModelMetadata`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/schemas/models.py) with `capabilities` list
* `src/marketing_mcp/mcp/tools/mmm.py`: Prerequisite checking in `compare_models`
* `src/marketing_mcp/errors.py`: [`PrerequisiteError`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/errors.py)
* `tests/unit/test_hard_test_remediation.py`: Capability and LOO prerequisite tests
