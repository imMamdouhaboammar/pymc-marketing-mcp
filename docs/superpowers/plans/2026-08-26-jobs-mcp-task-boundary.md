# Durable Jobs and MCP Task Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make long-running statistical compute durable and transport-neutral today while preserving a clean adapter path to the MCP `io.modelcontextprotocol/tasks` extension when the Python SDK implements that extension.

**Architecture:** Keep the existing `2026-08-23-jobs-storage-recovery.md` as the core persistence/executor plan. This amendment defines a stable internal job contract, process-isolated statistical execution, MCP compatibility tools for the current SDK, and a future `TasksExtensionAdapter` that can be added without changing services, repositories or workers.

**Tech Stack:** Python multiprocessing/process workers, SQLite/PostgreSQL job repositories, MCP Python SDK v2, Pydantic typed job contracts, pytest integration/recovery tests.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Protocol constraint

MCP specification `2026-07-28` moved long-running Tasks into the formal `io.modelcontextprotocol/tasks` extension. The official Python SDK v2 roadmap currently lists that extension as not yet implemented. Therefore:

- do not couple domain services to provisional/legacy Task APIs
- do not wait for the extension before making compute durable
- expose compatibility job tools now
- add a protocol adapter later when supported by the pinned SDK

## Global Constraints

- Job identity/state is server-owned durable state, not MCP session state.
- Every job has owner/tenant identity and authorization checks.
- Submission must persist before execution begins.
- CPU-heavy PyMC work must run outside the ASGI event loop.
- Cancellation must not depend on unsafe thread killing.
- Idempotency is scoped by principal/tenant + job type + semantic input.
- Job results reference immutable artifacts/provenance rather than embedding huge posterior payloads.

---

### Task 1: Lock the internal job contract before MCP-facing changes

**Files:**
- Create/modify: `src/marketing_mcp/jobs/models.py`
- Create/modify: `src/marketing_mcp/jobs/service.py`
- Create/modify: `src/marketing_mcp/jobs/repository.py`
- Test: `tests/contract/test_job_service_contract.py`

**Interfaces:**

```python
class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYABLE_FAILED = "retryable_failed"

@dataclass(frozen=True)
class JobSpec:
    job_type: str
    tenant_id: str
    owner_subject: str
    semantic_input: dict[str, Any]
    idempotency_key: str | None
    trace_context: dict[str, str]

@dataclass(frozen=True)
class JobResultRef:
    media_type: str
    uri: str
    sha256: str

class JobService:
    def submit(self, spec: JobSpec) -> JobRecord: ...
    def get(self, job_id: str, *, principal: Principal) -> JobRecord: ...
    def cancel(self, job_id: str, *, principal: Principal) -> JobRecord: ...
    def result(self, job_id: str, *, principal: Principal) -> JobResultRef | dict: ...
```

- [ ] Write state/ownership/idempotency contract tests
- [ ] Ensure no MCP-specific request/response type appears under `jobs/`
- [ ] Commit

---

### Task 2: Define statistical job types and semantic hashes

**Files:**
- Create: `src/marketing_mcp/jobs/types.py`
- Modify: `src/marketing_mcp/jobs/idempotency.py`
- Test: `tests/unit/test_statistical_job_identity.py`

**Required job types:**

```text
mmm.fit
mmm.cross_validate
mmm.prior_sensitivity
mmm.calibrate
clv.fit_purchase
clv.fit_value
model.compare_expensive
```

- [ ] Canonicalize Pydantic inputs before hashing
- [ ] Include dataset fingerprint and parent model identity where relevant
- [ ] Exclude request IDs/timestamps/trace metadata from semantic hash
- [ ] Test same semantic input deduplicates and changed model config conflicts under same key
- [ ] Commit

---

### Task 3: Process-isolate sampling and support cancellation

**Files:**
- Create/modify: `src/marketing_mcp/jobs/local_executor.py`
- Create: `src/marketing_mcp/jobs/process_worker.py`
- Test: `tests/integration/test_sampling_process_isolation.py`

- [ ] Start statistical work in a worker process, not an ASGI coroutine/thread that cannot be safely cancelled
- [ ] Persist `running` + worker identity/heartbeat before heavy compute
- [ ] Implement cooperative cancellation checkpoints where possible
- [ ] Allow controlled worker process termination only through executor-owned process handles
- [ ] Ensure partial NetCDF/artifact writes use temporary names and never become canonical result refs
- [ ] Test cancellation while sampling, process crash, and stale heartbeat recovery
- [ ] Commit

---

### Task 4: Add compatibility MCP job tools for current SDK

**Files:**
- Create: `src/marketing_mcp/mcp/tools/jobs.py`
- Modify: `src/marketing_mcp/mcp/server.py`
- Modify: `src/marketing_mcp/capabilities.py`
- Test: `tests/integration/test_mcp_job_tools.py`

**Tools:**

```text
get_job_status(job_id)
cancel_job(job_id)
get_job_result(job_id)
```

Expensive domain tools may return a submission envelope containing `job_id` instead of blocking

- [ ] Register job tools under explicit read/admin or model scopes as appropriate
- [ ] Apply object ownership policy to every job operation
- [ ] Add discovery snapshot/capability inventory entries
- [ ] Ensure result payload contains stable lifecycle fields rather than executor internals
- [ ] Commit

---

### Task 5: Convert expensive tools without breaking cheap read tools

**Files:**
- Modify: `src/marketing_mcp/services/modeling_service.py`
- Modify: `src/marketing_mcp/services/diagnostics_service.py`
- Modify: `src/marketing_mcp/services/clv_service.py`
- Modify: MCP tool modules
- Test: `tests/integration/test_statistical_job_lifecycle.py`

- [ ] Convert the required expensive operations to submission flows
- [ ] Keep bounded read-only summaries synchronous when load time remains bounded
- [ ] Test `fit_mmm` submission returns before sampling completes
- [ ] Test diagnostics/decision tools refuse a model whose fit job is incomplete
- [ ] Test completed job creates exactly one durable model/resource
- [ ] Commit

---

### Task 6: Add API/worker deployment separation contract

**Files:**
- Create: `src/marketing_mcp/jobs/worker_cli.py`
- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Modify: `cloudbuild.yaml`
- Modify: `docs/DEPLOYMENT-GCP.md`
- Test: `tests/integration/test_api_worker_separation.py`

**Scripts:**

```toml
marketing-mcp = "marketing_mcp.cli:main"
marketing-mcp-worker = "marketing_mcp.jobs.worker_cli:main"
```

- [ ] Prove API process can submit to durable repository without executing sampling inline in production profile
- [ ] Prove worker can claim queued jobs transactionally
- [ ] Prove two workers do not execute the same job simultaneously
- [ ] Document separate CPU/memory/concurrency settings
- [ ] Commit

---

### Task 7: Define a future MCP Tasks adapter contract without implementing unsupported SDK APIs

**Files:**
- Create: `src/marketing_mcp/mcp/task_adapter.py`
- Create: `tests/unit/test_task_adapter_contract.py`
- Modify: `docs/API-COMPATIBILITY.md`

**Interface:**

```python
class ProtocolTaskAdapter(Protocol):
    def advertise_if_supported(self, server: Any) -> None: ...
    def to_protocol_handle(self, job: JobRecord) -> Any: ...
    def apply_protocol_update(self, job_id: str, update: Any, principal: Principal) -> JobRecord: ...
```

Initial implementation:

```python
class UnsupportedTasksExtensionAdapter:
    supported = False
```

- [ ] Test that current server does not falsely advertise Tasks support
- [ ] Document Python SDK support state and tracked upgrade condition
- [ ] Ensure compatibility job tools remain the supported path until the adapter becomes real
- [ ] Commit

---

### Task 8: Add extension migration tests once SDK support lands

**Files:**
- Future modify: `src/marketing_mcp/mcp/task_adapter.py`
- Future create: `tests/integration/test_mcp_tasks_extension.py`

This task is gated and MUST NOT be implemented against private/provisional SDK APIs

Acceptance when unblocked:

```text
tools/call can return a protocol task handle where supported
tasks/get maps to JobService.get
tasks/update maps only to allowed mutable task metadata
tasks/cancel maps to JobService.cancel
ownership/scope policy remains unchanged
legacy compatibility job tools can be deprecated on an explicit schedule
```

- [ ] Open/track upstream SDK implementation before coding
- [ ] Add version/capability detection
- [ ] Implement adapter only after pinned SDK provides public extension APIs
- [ ] Run protocol conformance + backward compatibility tests
- [ ] Commit

---

### Task 9: Establish H4 Recoverable Compute gate

**Files:**
- Create: `tests/release/test_h4_recoverable_compute.py`
- Modify: `docs/PRODUCTION-READINESS.md`

**Assertions:**

- every release-critical expensive operation submits a durable job
- job persisted before execution
- restart/recovery/cancel/idempotency tests pass
- process-isolated sampling does not block API event loop
- cross-principal job access denied
- current MCP server does not falsely advertise unsupported Tasks extension
- job domain layer contains no MCP protocol types
- API and worker roles can run separately

- [ ] Run G2 + H4 release suites
- [ ] Mark H4 green only from CI evidence
- [ ] Commit

## Acceptance Criteria

This plan is complete when statistical compute is durable/recoverable today and the MCP protocol boundary can adopt the official Tasks extension later through a small adapter rather than a job-system rewrite
