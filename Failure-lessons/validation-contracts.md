# Failure Lessons: Validation Contracts & Admission Parity

This document captures durable failure lessons, root causes, and architectural invariants for input validation, synchronous preflight vs asynchronous worker parity, and data admission gates in `pymc-marketing-mcp`.

---

## MMM-VAL-001: Preflight vs Asynchronous Job Admission Validation Parity Divergence

### What happened
When a caller submitted an invalid dataset (containing negative marketing spend, non-numeric values, or missing date columns):
* Calling `validate_dataset` correctly rejected the payload with a structured `400 Bad Request` and detailed column-level error diagnostics.
* Calling `submit_fit_mmm_job` with the **exact same invalid dataset** returned `success: True`, created a `job_id`, and admitted the job into the background execution queue.
* Five minutes later, the background worker crashed with an unhandled Python `ValueError` or PyTensor shape mismatch during MCMC initialization.

### Why it mattered
* **Wasted Infrastructure Resources**: The worker queue allocated high-memory/GPU compute instances to execute a job doomed to fail from the start.
* **Degraded Agent Usability**: Autonomous agents believed the job was successfully started and entered polling loops, only to be hit with a fatal, unrecoverable worker crash minutes later.
* **Contract Asymmetry**: Having two endpoints disagree on the validity of identical input destroys the predictability of the API.

### Observable symptom
* Synchronous validation returned `status: "invalid"`, but asynchronous submission returned `status: "queued"`.
* Delayed worker failure logs: `PyTensor Shape Error: expected (N, K) got (N, K-1)`.

### Initial assumption
Developers assumed that since the background worker runs PyMC code that eventually performs its own checks, performing deep dataset validation in the API ingress layer was redundant overhead.

### Root cause
* **Status**: Confirmed.
* **Architectural Duplication & Separation**: Validation logic was implemented in `DatasetValidator` for the `validate_dataset` tool, but `submit_fit_mmm_job` bypassed `DatasetValidator` entirely, directly serializing the dataset into database staging and deferring all checks to the background worker.
* The background worker relied on raw library exceptions rather than structured domain validation.

### Why the system allowed it
The system lacked an enforced admission gateway requiring all job submissions to execute the canonical preflight validation pipeline before queue admission.

### Fix
1. **Canonical Validation Gate**: Unified validation into a single canonical `DatasetValidator.validate_mmm_dataset()` implementation.
2. **Synchronous Ingress Admission Check**: `submit_fit_mmm_job` now invokes `DatasetValidator.validate_mmm_dataset()` synchronously before writing the job record to the database:
   - If validation fails, `submit_fit_mmm_job` raises `DatasetValidationError` immediately.
   - Zero jobs are queued for invalid datasets.
3. **Parity Regression Assertions**: Added tests asserting identical validation verdicts across both `validate_dataset` and `submit_fit_mmm_job`.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_validation_parity_between_preflight_and_job_submission`
* Asserts that invalid datasets produce identical rejection errors in both synchronous preflight and asynchronous submission tools.

### Prevention rule
> **Rule**: One domain invariant must have one canonical validation implementation. Every asynchronous submission endpoint must run synchronous preflight validation before queue admission.

### Reusable lesson
Never defer input validation to background worker threads. When an API provides both an explicit validation tool and an execution tool, the execution tool must strictly enforce the validation tool as its first gate.

### Related failures
* [Failure Lesson 06: Bayesian RFM Mathematical Domain Invariants](./06-bayesian-rfm-domain-invariants.md)
* [Failure Lesson 07: Remote Client Sandbox Data Ingestion & Diagnostic Usability](./07-remote-client-sandbox-data-ingestion.md)
* [Failure Lesson 17: Dataset Ingestion SSRF and Memory Exhaustion](./17-dataset-ingestion-ssrf-and-memory-exhaustion.md)
* [Failure Lesson 25: Remote Dataset Content-Type Verification](./25-remote-dataset-content-type-verification.md)
* [Failure Lesson 31: MCP Protocol Inversion & Unprotected Ingress Admission](./31-mcp-protocol-inversion-and-admission-boundary.md)

---

## Protected Systems & Code References

* `src/marketing_mcp/domain/datasets/validation.py`: [`DatasetValidator`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/domain/datasets/validation.py)
* `src/marketing_mcp/services/dataset_service.py`: Dataset ingestion and validation service
* `src/marketing_mcp/mcp/tools/mmm.py`: Synchronous preflight admission gate in `submit_fit_mmm_job`
* `tests/unit/test_hard_test_remediation.py`: Validation parity regression test suite
