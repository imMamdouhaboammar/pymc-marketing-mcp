# Jobs, Persistence, and Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move expensive statistical work out of request-bound execution and make model, job, scenario, and artifact state survive process restart and cloud instance replacement.

**Architecture:** Add storage and job interfaces before adding production implementations. Local mode keeps SQLite plus filesystem. Production mode uses PostgreSQL for metadata/jobs and object storage for datasets/model artifacts/plots. Statistical execution is submitted through a job executor abstraction so local inline/worker execution and future external queue workers can share the same domain contracts.

**Tech Stack:** Python 3.12+, PostgreSQL, SQLAlchemy or psycopg with explicit migrations, SQLite local adapter, GCS object storage adapter, PyMC-Marketing, asyncio/process workers as appropriate, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Existing local SQLite data must remain readable or have a deterministic migration path.
- Model artifacts are immutable after successful write.
- Job state transitions must be persisted before returning them to clients.
- Retrying a fit must not silently create duplicate business decisions when an idempotency key matches.
- A worker crash must leave the job in a recoverable state rather than `running` forever.
- Production cloud metadata must not live only on ephemeral container disk.

---

### Task 1: Define repository interfaces

**Files:**
- Create: `src/marketing_mcp/repositories/base.py`
- Create: `src/marketing_mcp/repositories/models.py`
- Refactor: `src/marketing_mcp/storage/metadata.py`
- Refactor: `src/marketing_mcp/storage/artifacts.py`
- Test: `tests/contract/test_repository_contracts.py`

**Interfaces:**

```python
class MetadataRepository(Protocol):
    def put_dataset(self, record: dict) -> None: ...
    def get_dataset(self, dataset_id: str) -> dict: ...
    def put_model(self, record: dict) -> None: ...
    def get_model(self, model_id: str) -> dict: ...
    def put_clv_model(self, record: dict) -> None: ...
    def get_clv_model(self, model_id: str) -> dict: ...
    def put_scenario(self, record: dict) -> None: ...
    def get_scenario(self, scenario_id: str) -> dict: ...
```

```python
class ArtifactStore(Protocol):
    def put_model_artifact(self, model_id: str, source: Path) -> ArtifactRef: ...
    def materialize_model_artifact(self, ref: ArtifactRef) -> Path: ...
    def put_dataset(self, dataset_id: str, source: Path) -> ArtifactRef: ...
    def put_plot(self, model_id: str, plot_type: str, data: bytes, media_type: str) -> ArtifactRef: ...
```

- [ ] Write adapter contract tests before refactoring callers.
- [ ] Wrap the existing SQLite implementation behind `MetadataRepository` without behavior change.
- [ ] Wrap filesystem artifacts behind `ArtifactStore`.
- [ ] Introduce `ArtifactRef` with URI, sha256, size, content type, created_at.
- [ ] Make `Application` depend on interfaces instead of concrete storage classes.
- [ ] Commit.

### Task 2: Add schema-versioned local SQLite migrations

**Files:**
- Create: `src/marketing_mcp/storage/migrations.py`
- Modify: `src/marketing_mcp/storage/metadata.py`
- Create: `tests/integration/test_sqlite_migrations.py`

- [ ] Add `schema_migrations(version, applied_at)` table.
- [ ] Replace implicit `CREATE TABLE IF NOT EXISTS` as the only migration strategy with ordered migrations.
- [ ] Create migration for owner/tenant fields or store them in versioned structured records according to the chosen repository schema.
- [ ] Test migration from a fixture representing the current v0.4 database.
- [ ] Test idempotent reopen after migration.
- [ ] Test rollback policy by proving startup fails safely when DB schema is newer than the binary understands.
- [ ] Commit.

### Task 3: Define durable job models and state machine

**Files:**
- Create: `src/marketing_mcp/jobs/models.py`
- Create: `src/marketing_mcp/jobs/state.py`
- Create: `src/marketing_mcp/jobs/repository.py`
- Test: `tests/unit/test_job_state_machine.py`

**States:**

```text
queued -> running -> succeeded
queued -> cancelled
running -> cancelling -> cancelled
running -> failed
running -> retryable_failed -> queued
```

Terminal states:
- succeeded
- failed
- cancelled

**Job record fields:**
- job_id
- job_type
- principal/tenant ownership
- idempotency_key
- input_hash
- resource_id if created
- state
- progress metadata
- created_at
- started_at
- heartbeat_at
- finished_at
- attempt
- max_attempts
- failure code/message
- result reference

- [ ] Write state transition tests including illegal transitions.
- [ ] Make cancellation idempotent.
- [ ] Define stale-running detection from heartbeat age.
- [ ] Commit.

### Task 4: Implement a local job repository and executor

**Files:**
- Create: `src/marketing_mcp/jobs/sqlite_repository.py`
- Create: `src/marketing_mcp/jobs/executor.py`
- Create: `src/marketing_mcp/jobs/local_executor.py`
- Test: `tests/integration/test_local_jobs.py`

**Interfaces:**

```python
class JobExecutor(Protocol):
    def submit(self, spec: JobSpec) -> JobRecord: ...
    def cancel(self, job_id: str) -> JobRecord: ...
```

- [ ] Persist job before execution begins.
- [ ] Execute CPU-heavy PyMC work outside the ASGI event loop.
- [ ] Define process isolation strategy for sampling jobs where cancellation requires process termination.
- [ ] Persist heartbeat/progress at safe checkpoints.
- [ ] Capture known DomainError families without replacing them with generic internal errors.
- [ ] On worker/process crash, recovery scan marks stale jobs retryable or failed according to policy.
- [ ] Commit.

### Task 5: Add idempotency and duplicate suppression

**Files:**
- Create: `src/marketing_mcp/jobs/idempotency.py`
- Modify: fit/calibration/CV/CLV submission services
- Test: `tests/contract/test_job_idempotency.py`

**Contract:**
- same principal + job type + idempotency key + semantically identical input returns the existing active/succeeded job
- same idempotency key with different semantic input returns `IDEMPOTENCY_CONFLICT`
- no idempotency key preserves explicit ability to create a new independent run

- [ ] Canonicalize input JSON and hash it.
- [ ] Exclude transient request metadata from semantic hash.
- [ ] Include dataset fingerprint and model parent identity where relevant.
- [ ] Add concurrency test for two near-simultaneous duplicate submissions.
- [ ] Commit.

### Task 6: Convert expensive operations into jobs

**Files:**
- Modify: `src/marketing_mcp/services/modeling_service.py`
- Modify: `src/marketing_mcp/services/diagnostics_service.py`
- Modify: `src/marketing_mcp/services/clv_service.py`
- Add: job handler modules under `src/marketing_mcp/jobs/handlers/`
- Modify: MCP tool modules after server split
- Test: `tests/integration/test_statistical_job_lifecycle.py`

**Convert at minimum:**
- fit MMM
- cross-validation
- prior sensitivity
- calibration
- fit CLV
- expensive multi-model comparison when real models are loaded

**MCP contract:**
- submission returns `job_id`, state, and known resource placeholder if applicable
- `get_job_status(job_id)` returns durable state
- `cancel_job(job_id)` requests cancellation
- `get_job_result(job_id)` returns the final tool envelope/result reference

- [ ] Keep short read-only analytical tools synchronous after loading an approved model if their latency remains bounded.
- [ ] Add tool-level tests that expensive submissions return before sampling completes.
- [ ] Commit.

### Task 7: Implement PostgreSQL metadata and job repository

**Files:**
- Create: `src/marketing_mcp/storage/postgres.py`
- Create: `src/marketing_mcp/jobs/postgres_repository.py`
- Create: `migrations/` or repository-standard migration directory
- Test: `tests/integration/test_postgres_repositories.py`

**Tables:**
- datasets
- models
- clv_models
- scenarios
- jobs
- artifacts
- audit_events or reference to audit plan
- schema_migrations if migration framework does not provide its own

- [ ] Use typed columns for identity/state/ownership/timestamps and JSONB for versioned domain payloads where appropriate.
- [ ] Add indexes for owner/tenant, dataset/model lineage, job state, idempotency key, created_at.
- [ ] Add unique constraint for active idempotency identity.
- [ ] Use transactions for state changes that create/update both job and resource metadata.
- [ ] Test rollback on injected failure.
- [ ] Commit.

### Task 8: Implement production object storage

**Files:**
- Create: `src/marketing_mcp/storage/gcs_artifacts.py`
- Test: `tests/contract/test_artifact_store_contract.py`
- Test: `tests/integration/test_gcs_artifact_store.py` using emulator/fake endpoint if supported

**Object layout:**

```text
datasets/{tenant-or-local}/{dataset_id}/{sha256}.{ext}
models/{tenant-or-local}/{model_id}/{sha256}.nc
plots/{tenant-or-local}/{model_id}/{plot_type}/{sha256}.{ext}
```

- [ ] Write to a temporary object key first.
- [ ] Verify size and sha256.
- [ ] Promote/finalize immutable object reference.
- [ ] Record `ArtifactRef` only after successful verification.
- [ ] Never overwrite a model artifact under the same immutable reference.
- [ ] Add materialization cache with bounded disk usage for libraries that require local paths.
- [ ] Commit.

### Task 9: Add artifact integrity and orphan reconciliation

**Files:**
- Create: `src/marketing_mcp/storage/reconcile.py`
- Test: `tests/integration/test_storage_reconciliation.py`

**Cases:**
- metadata exists, object missing
- object exists, metadata missing
- checksum mismatch
- temporary upload abandoned
- job succeeded but result reference missing

- [ ] Implement read-only scan first.
- [ ] Emit stable findings with recommended actions.
- [ ] Add explicit repair commands/functions that require administrative scope.
- [ ] Never auto-delete unknown objects during normal startup.
- [ ] Commit.

### Task 10: Add restart recovery tests

**Files:**
- Create: `tests/integration/test_restart_recovery.py`

- [ ] Start service with persistent test DB/storage.
- [ ] Register dataset and complete a small model job.
- [ ] Stop the application and construct a fresh `Application` instance.
- [ ] Verify dataset, model status, lineage, artifact load, diagnostics metadata, and job result remain available.
- [ ] Create a running job with stale heartbeat and verify recovery policy.
- [ ] Verify no resource becomes anonymous/unowned after restart.
- [ ] Commit.

### Task 11: Add backup and restore verification

**Files:**
- Create: `scripts/backup_metadata.py`
- Create: `scripts/verify_backup_restore.py`
- Create: `docs/runbooks/backup-restore.md`
- Test: `tests/integration/test_backup_restore.py`

- [ ] Define Postgres logical backup procedure and object storage versioning/retention policy.
- [ ] Restore into a clean test environment.
- [ ] Verify artifact checksums and model metadata references.
- [ ] Document RPO/RTO assumptions without claiming guarantees not enforced by deployment configuration.
- [ ] Commit.

### Task 12: Establish Gate G2

**Files:**
- Create: `tests/release/test_g2_recovery.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- expensive operations use durable jobs
- job cancellation is persisted
- restart recovery passes
- local SQLite mode passes adapter contracts
- production Postgres adapter passes the same contracts
- production object store passes artifact integrity tests
- backup/restore verification passes

- [ ] Run G2 suite in CI with disposable Postgres and storage test environment.
- [ ] Mark G2 green only from CI evidence.

## Acceptance Criteria

This plan is complete when:

- no production model metadata depends on ephemeral disk
- every expensive statistical operation has durable job state
- duplicate submissions can be safely deduplicated
- jobs can be cancelled and recovered after crash
- Postgres and local SQLite implement the same repository contracts
- model/dataset/plot objects have immutable checksum references
- restart and backup/restore tests pass
- Gate G2 is green