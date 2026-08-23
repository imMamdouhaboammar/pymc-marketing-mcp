# Performance, Resilience, and Capacity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure the service remains predictable under concurrent MCP clients, large datasets, expensive MCMC workloads, worker crashes, dependency degradation, and resource pressure without corrupting state or degrading into uncontrolled queue growth.

**Architecture:** Separate control-plane HTTP handling from CPU/memory-heavy statistical execution. Apply quotas and admission control before jobs enter the worker pool. Define resource classes for different job types, enforce queue/backpressure policies, and test failure/recovery behavior with repeatable load and fault scenarios.

**Tech Stack:** Python, job executor from the jobs plan, Cloud Run or equivalent worker runtime, PostgreSQL, object storage, OpenTelemetry metrics, pytest, load-test tooling suitable for HTTP/MCP traffic.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Never run arbitrary numbers of MCMC jobs concurrently because HTTP concurrency is high.
- Queue capacity and worker capacity must be explicit.
- Admission policy must return a stable error or queued state rather than allowing memory exhaustion.
- Performance tuning must not change statistical semantics or weaken sampler configuration silently.
- Load tests must use synthetic/non-sensitive data.

---

### Task 1: Define resource classes for job types

**Files:**
- Create: `src/marketing_mcp/jobs/resources.py`
- Test: `tests/unit/test_job_resource_classes.py`

**Resource classes:**

```text
light
  model metadata reads, small plots

medium
  diagnostics, bounded posterior summaries, model comparison on small sets

heavy
  MMM fit, CLV fit, calibration

very_heavy
  cross-validation, prior sensitivity, multi-model statistical comparisons
```

**Fields:**
- max_runtime_seconds
- cpu_units
- memory_mb_hint
- max_concurrency_per_worker
- max_attempts
- cancellable

- [ ] Map every job type to a resource class.
- [ ] Reject unknown job types rather than defaulting to unlimited resources.
- [ ] Keep hints/configuration observable in job metadata.
- [ ] Commit.

### Task 2: Add admission control

**Files:**
- Create: `src/marketing_mcp/jobs/admission.py`
- Modify: job submission service
- Test: `tests/contract/test_job_admission.py`

**Policies:**
- maximum queued jobs globally or per deployment
- maximum active jobs per principal/tenant
- maximum heavy jobs per principal/tenant
- dataset size/model complexity pre-checks
- optional administrative override scope

- [ ] Return `RESOURCE_LIMIT_EXCEEDED` or a clear queue rejection reason when limits are exceeded.
- [ ] Do not accept a job and later silently discard it.
- [ ] Make admission counters transaction-safe with production job repository.
- [ ] Commit.

### Task 3: Add dataset and model complexity estimation

**Files:**
- Create: `src/marketing_mcp/domain/complexity.py`
- Modify: dataset inspection/model submission
- Test: `tests/unit/test_complexity_estimator.py`

**Inputs:**
- rows/time periods
- channels
- controls
- panel dimensions/cardinality
- draws/tune/chains
- CV folds
- prior sensitivity candidates

**Output:**
- complexity class
- estimated relative cost score
- warning findings
- hard-limit violations

- [ ] Use the estimator for admission policy only, not for promising wall-clock duration.
- [ ] Reject configurations beyond explicit deployment limits before starting PyMC compilation.
- [ ] Expose warnings to clients so they can reduce draws/folds/dimensions intentionally.
- [ ] Commit.

### Task 4: Separate API and statistical worker concurrency

**Files:**
- Modify: deployment manifests/scripts
- Create: `docs/operations/COMPUTE-TOPOLOGY.md`
- Test: configuration contract tests

**Topology:**

```text
MCP/API service
  high enough concurrency for control-plane calls
  no direct heavy sampling

Statistical worker pool
  low controlled concurrency
  explicit CPU/memory reservation
  job repository driven
```

- [ ] Remove any deployment configuration that allows HTTP concurrency such as 80 to imply 80 simultaneous samplers.
- [ ] Define worker concurrency by resource class.
- [ ] Define max instances and queue behavior.
- [ ] Document local single-process fallback separately.
- [ ] Commit.

### Task 5: Add job timeout and cooperative cancellation policy

**Files:**
- Modify: `src/marketing_mcp/jobs/executor.py`
- Modify: process worker implementation
- Test: `tests/integration/test_job_timeout_cancel.py`

- [ ] Enforce resource-class runtime caps.
- [ ] Persist cancellation request before signalling worker.
- [ ] Give cooperative shutdown a bounded grace period.
- [ ] Escalate to worker process termination when safe and required.
- [ ] Mark result `cancelled`, not generic failed, when cancellation succeeds.
- [ ] Verify partial artifacts are not promoted as complete.
- [ ] Commit.

### Task 6: Add backpressure and queue-age behavior

**Files:**
- Modify: job admission/repository
- Test: `tests/integration/test_queue_backpressure.py`

- [ ] Define maximum queue age by job/resource class.
- [ ] Emit queue age metrics.
- [ ] Allow users to cancel queued jobs.
- [ ] Reject new low-priority heavy work when queue saturation threshold is reached.
- [ ] Do not reorder jobs in a way that breaks tenant fairness without an explicit scheduling policy.
- [ ] Commit.

### Task 7: Add memory and disk safety controls

**Files:**
- Modify: dataset/materialization/artifact cache code
- Create: `src/marketing_mcp/runtime/limits.py`
- Test: `tests/integration/test_runtime_limits.py`

**Controls:**
- max registered dataset bytes
- max materialized artifact bytes
- bounded artifact cache
- cleanup of failed temporary files
- minimum free disk threshold before materialization

- [ ] Keep existing dataset size limit but make it profile-configurable and tested.
- [ ] Estimate uncompressed parquet/CSV memory expansion before loading when possible.
- [ ] Refuse unsafe materialization before filling local disk.
- [ ] Clean temporary files after failed/cancelled jobs.
- [ ] Commit.

### Task 8: Add load tests for MCP control plane

**Files:**
- Create: `tests/load/README.md`
- Create: `tests/load/mcp_control_plane.py`
- Create: `scripts/run_load_tests.py`

**Scenarios:**
- concurrent health/readiness
- concurrent dataset/model status reads
- authenticated tool discovery
- job submissions under quota
- status polling with many queued jobs

- [ ] Measure p50/p95/p99 control-plane latency.
- [ ] Verify no unauthorized request reaches service execution.
- [ ] Verify rate/admission limits remain stable under concurrency.
- [ ] Keep load suite outside default pytest PR lane; run in scheduled/pre-release environment.
- [ ] Commit.

### Task 9: Add statistical worker capacity benchmark

**Files:**
- Create: `benchmarks/statistical_capacity.py`
- Create: `docs/operations/CAPACITY.md`

**Benchmark matrix:**
- small MMM fixture
- medium synthetic MMM fixture
- multidimensional fixture
- CLV fixture
- CV fixture

Capture:
- wall time
- peak RSS if measurable
- CPU utilization
- artifact size
- compile/sampling split where observable

- [ ] Run one job and controlled concurrent jobs per target worker size.
- [ ] Determine safe default worker concurrency from evidence, not HTTP defaults.
- [ ] Document tested machine/container profile and commit SHA.
- [ ] Do not publish capacity numbers as universal guarantees.
- [ ] Commit.

### Task 10: Add fault-injection recovery tests

**Files:**
- Create: `tests/resilience/test_fault_injection.py`

**Faults:**
- worker process killed mid-fit
- Postgres unavailable during status read
- object storage unavailable during final artifact write
- checksum mismatch on artifact read
- API restart while jobs remain queued
- stale heartbeat

- [ ] Verify state is not falsely marked succeeded.
- [ ] Verify recoverable failures enter the correct state.
- [ ] Verify immutable artifact rules prevent corrupted promotion.
- [ ] Verify user receives stable error family and correlation ID.
- [ ] Commit.

### Task 11: Define retry policy

**Files:**
- Create: `src/marketing_mcp/jobs/retry.py`
- Test: `tests/unit/test_retry_policy.py`

**Retryable examples:**
- temporary database/network/storage unavailability before statistical result finalization

**Non-retryable examples:**
- invalid data
- invalid model configuration
- diagnostics rejection
- deterministic PyMC model construction error
- authorization failure
- idempotency conflict

- [ ] Make retry classification explicit by error code.
- [ ] Use bounded exponential backoff for infrastructure failures.
- [ ] Never rerun a completed statistical job just because result delivery failed; recover the stored result instead.
- [ ] Commit.

### Task 12: Add resilience release checks

**Files:**
- Create: `tests/release/test_resilience_capacity_contract.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- heavy jobs cannot bypass admission control
- worker concurrency is separate from API concurrency
- timeout/cancel leaves no completed-looking partial artifact
- restart/stale-job recovery works
- queue saturation has deterministic behavior
- fault-injection critical cases pass

- [ ] Add scheduled/pre-release execution to CI/operations workflow.
- [ ] Include capacity benchmark reference in release evidence.

## Acceptance Criteria

This plan is complete when:

- HTTP concurrency cannot accidentally create uncontrolled sampler concurrency
- job admission and quotas are explicit and tested
- oversized/over-complex work is rejected before consuming large resources
- cancellation, timeout, and crash behavior preserves correct job/artifact state
- queue saturation produces backpressure instead of resource collapse
- load and capacity benchmarks exist for the target deployment profile
- core fault-injection scenarios recover safely