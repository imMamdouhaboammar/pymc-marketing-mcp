# Worker and Durable Compute Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make asynchronous statistical jobs truly durable by executing them in a standalone worker process with registered production handlers, persistent state, idempotency, cancellation, and restart recovery.

**Architecture:** Keep `JobService` transport-neutral and make the API responsible only for validating, authorizing, and persisting job submissions. A worker-handler registry maps durable job types to synchronous worker functions that reconstruct typed inputs and call domain services. API-process background execution remains allowed only for local/development mode, not production HTTP.

**Tech Stack:** Python 3.12, SQLiteJobRepository initially, ProcessJobWorker, JobService, PyMC-Marketing, pytest, MCP compatibility job tools

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- Production HTTP must not depend on `AsyncioJobExecutor` for CPU-heavy MMM fitting
- Job submission must be persisted before execution starts
- The standalone worker must register all supported production job handlers at startup
- A process restart must not lose queued/succeeded/failed/cancelled state
- Idempotency keys are tenant-scoped and must reject semantic conflicts
- MCP Tasks extension must not be claimed until supported by the selected SDK/runtime
- Remote users must not inspect or cancel another tenant's jobs

---

## Task 1: Define the production worker handler registry

**Files:**
- Create: `src/marketing_mcp/jobs/handlers.py`
- Modify: `src/marketing_mcp/jobs/types.py`
- Test: `tests/unit/test_job_handlers.py`

**Interfaces:**
- Consumes: `Application`, `JobRecord`
- Produces: `build_job_handlers(app: Application) -> dict[str, Callable[[JobRecord], dict[str, Any]]]`

- [ ] **Step 1: Write a failing registry test**

Assert that the registry contains the canonical MMM fit job type and that unknown job types are absent.

- [ ] **Step 2: Define one canonical job-type string**

Use `StatisticalJobType.MMM_FIT.value` everywhere. Remove drift between `"fit_mmm"` and `"mmm.fit"` by choosing the enum value as the source of truth.

- [ ] **Step 3: Implement the MMM fit handler**

The handler must:

```python
def run_mmm_fit_job(app: Application, job: JobRecord) -> dict[str, Any]:
    config = FitMMMInput.model_validate(job.payload)
    result = app.models.fit(config)
    return result.model_dump()
```

- [ ] **Step 4: Build the registry**

Return a dictionary keyed by `StatisticalJobType.MMM_FIT.value` and bind the application instance explicitly.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/unit/test_job_handlers.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/jobs/handlers.py src/marketing_mcp/jobs/types.py tests/unit/test_job_handlers.py
git commit -m "feat: register production statistical job handlers"
```

## Task 2: Wire real handlers into the standalone worker CLI

**Files:**
- Modify: `src/marketing_mcp/jobs/worker_cli.py`
- Test: `tests/integration/test_worker_cli.py`

**Interfaces:**
- Consumes: `build_job_handlers(app)`
- Produces: functional `marketing-mcp-worker`

- [ ] **Step 1: Write the failing CLI worker test**

Seed one queued MMM job with a lightweight fake handler injection point, run `worker_cli.main(["--once"])`, and assert the job no longer ends with `NO_HANDLER`.

- [ ] **Step 2: Add an injectable worker factory**

Keep the public CLI simple, but allow tests to pass an application/handler registry through an internal helper rather than monkeypatching global state.

- [ ] **Step 3: Register handlers at startup**

The runtime path must be equivalent to:

```python
app = Application()
worker = ProcessJobWorker(app.job_repo, handlers=build_job_handlers(app))
```

- [ ] **Step 4: Run CLI integration test**

Run: `uv run pytest tests/integration/test_worker_cli.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/jobs/worker_cli.py tests/integration/test_worker_cli.py
git commit -m "fix: make standalone worker execute real job types"
```

## Task 3: Separate submission from execution in production HTTP

**Files:**
- Modify: `src/marketing_mcp/jobs/service.py`
- Modify: `src/marketing_mcp/mcp/tools/jobs.py`
- Modify: `src/marketing_mcp/config.py`
- Test: `tests/unit/test_job_service_modes.py`
- Test: `tests/integration/test_http_job_submission_worker_execution.py`

**Interfaces:**
- Consumes: `JobRepository`, execution mode setting
- Produces: persisted-only production submissions and optional local inline execution

- [ ] **Step 1: Add an explicit execution-mode setting**

Define a setting with exact values:

```text
local-inline
external-worker
```

Default stdio/local development may use `local-inline`; production HTTP profile must require `external-worker`.

- [ ] **Step 2: Write a failing service-mode test**

When execution mode is `external-worker`, `submit_job` must create `QUEUED` state without invoking an in-process executor.

- [ ] **Step 3: Refactor JobService submission**

Split persistence from dispatch so the service can persist a job with no local runner in external-worker mode.

Suggested interface:

```python
def submit_job(
    self,
    job_type: str,
    payload: dict[str, Any],
    principal: Principal | None = None,
    idempotency_key: str | None = None,
    runner_fn: Callable[..., Coroutine[Any, Any, dict[str, Any]]] | None = None,
) -> JobRecord:
```

Reject a missing runner only in `local-inline` mode.

- [ ] **Step 4: Update `submit_fit_mmm_job`**

In production/external-worker mode, submit only the durable payload. In local-inline mode, retain the current convenience runner.

- [ ] **Step 5: Add E2E API-plus-worker test**

The test must:

1. submit a job through a real MCP HTTP session
2. terminate the API server after the job is persisted
3. create a fresh `Application` on the same metadata DB
4. run one standalone worker iteration
5. start a fresh API server
6. call `get_job_status`
7. assert the job succeeded and its result persisted

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/jobs/service.py src/marketing_mcp/mcp/tools/jobs.py src/marketing_mcp/config.py tests/unit/test_job_service_modes.py tests/integration/test_http_job_submission_worker_execution.py
git commit -m "feat: separate production job submission from worker execution"
```

## Task 4: Make idempotency semantic, not key-only

**Files:**
- Modify: `src/marketing_mcp/jobs/models.py`
- Modify: `src/marketing_mcp/jobs/repository.py`
- Modify: `src/marketing_mcp/jobs/service.py`
- Test: `tests/unit/test_job_idempotency_semantics.py`

**Interfaces:**
- Consumes: tenant ID, job type, normalized payload, idempotency key
- Produces: `semantic_hash` stored with every idempotent job

- [ ] **Step 1: Write conflict tests**

Same tenant + same key + same semantic payload must return the existing job. Same tenant + same key + different semantic payload must return `IDEMPOTENCY_CONFLICT`. Different tenants may reuse the same key.

- [ ] **Step 2: Define canonical semantic hashing**

Serialize a normalized object containing `job_type` and payload with sorted keys and stable separators, then hash with SHA-256.

- [ ] **Step 3: Persist `semantic_hash`**

Add a migration if the column does not already exist. Backfill existing rows with `NULL` and enforce the new check on newly submitted idempotent jobs.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_job_idempotency_semantics.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/jobs/models.py src/marketing_mcp/jobs/repository.py src/marketing_mcp/jobs/service.py src/marketing_mcp/storage/migrations.py tests/unit/test_job_idempotency_semantics.py
git commit -m "feat: enforce semantic job idempotency"
```

## Task 5: Harden cancellation and stale-running recovery

**Files:**
- Modify: `src/marketing_mcp/jobs/process_worker.py`
- Modify: `src/marketing_mcp/jobs/repository.py`
- Test: `tests/integration/test_worker_recovery.py`

**Interfaces:**
- Consumes: queued/running/cancelled durable job state
- Produces: safe worker claim and recovery behavior

- [ ] **Step 1: Write worker claim-race test**

Two worker instances attempting to claim one queued job must result in exactly one execution claim.

- [ ] **Step 2: Add an atomic claim operation to the repository**

The claim must transition `QUEUED -> RUNNING` conditionally. A worker that loses the claim must not execute the handler.

- [ ] **Step 3: Respect cancellation before handler execution**

If a queued job is already cancelled, the worker must skip it. If cancellation arrives after a job is claimed, record cooperative-cancellation state and do not overwrite `CANCELLED` with `SUCCEEDED`.

- [ ] **Step 4: Define stale-running recovery policy**

On worker startup, stale `RUNNING` jobs must either return to `QUEUED` for retry or become `FAILED` according to a configurable retry policy. Record recovery count and last recovery reason.

- [ ] **Step 5: Run recovery tests**

Run: `uv run pytest tests/integration/test_worker_recovery.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/jobs/process_worker.py src/marketing_mcp/jobs/repository.py tests/integration/test_worker_recovery.py
git commit -m "fix: make worker claims and recovery durable"
```

## Task 6: Make readiness reflect real worker capability

**Files:**
- Modify: `src/marketing_mcp/http/health.py`
- Modify: `src/marketing_mcp/jobs/repository.py`
- Test: `tests/unit/test_readiness_worker_dependency.py`

**Interfaces:**
- Consumes: configured execution mode and worker heartbeat state
- Produces: truthful `job_executor` readiness status

- [ ] **Step 1: Write the failing readiness test**

In `external-worker` mode with no recent worker heartbeat, `/health/ready` must report `job_executor.status = "error"` and HTTP 503.

- [ ] **Step 2: Add worker heartbeat persistence**

Persist worker ID and last-seen timestamp in metadata using a dedicated table/migration. The worker updates its heartbeat before polling and after each job.

- [ ] **Step 3: Update readiness logic**

`local-inline` may report the local executor healthy if the application can submit local jobs. `external-worker` must require at least one heartbeat within the configured freshness window.

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/http/health.py src/marketing_mcp/jobs/repository.py src/marketing_mcp/jobs/process_worker.py src/marketing_mcp/storage/migrations.py tests/unit/test_readiness_worker_dependency.py
git commit -m "fix: make readiness verify worker availability"
```

## Task 7: Reclassify the async job capability until the production path passes

**Files:**
- Modify: `src/marketing_mcp/capabilities.py`
- Generate: `docs/CAPABILITIES.md`
- Test: `tests/integration/test_capability_inventory.py`

**Interfaces:**
- Consumes: H4 evidence
- Produces: capability status that matches runtime maturity

- [ ] **Step 1: Keep `submit_fit_mmm_job` experimental until the API-exit/worker-restart E2E test passes**

Do not label the tool stable solely because local `AsyncioJobExecutor` tests pass.

- [ ] **Step 2: Promote only after the external-worker test is evidence-linked**

Regenerate inventory:

```bash
uv run python scripts/generate_capability_inventory.py
```

- [ ] **Step 3: Verify drift**

Run:

```bash
uv run python scripts/generate_capability_inventory.py --check
uv run pytest tests/integration/test_capability_inventory.py -q
```

Expected: PASS

## Acceptance criteria

This plan is complete when:

- the standalone CLI starts with real registered handlers
- API production mode persists jobs without executing CPU-heavy fits in the API process
- a submitted job survives API shutdown and completes in a separate worker process
- job results survive application restart
- worker claim is atomic under competing workers
- cancellation cannot be overwritten by a late success update
- idempotency detects same-key/different-payload conflicts
- readiness fails when external-worker mode has no healthy worker
- async job capability status is backed by the external-worker E2E evidence
