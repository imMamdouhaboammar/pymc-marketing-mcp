# Production Persistence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace single-instance SQLite/local-filesystem assumptions with explicit production metadata and artifact interfaces that survive instance replacement, support workers, and can be backed up and restored.

**Architecture:** Preserve SQLite and local files as first-class local/dev adapters while introducing stable repository interfaces for metadata, jobs, credentials, and artifacts. Production configuration selects an external SQL metadata implementation and object-storage implementation. Services depend on interfaces rather than concrete SQLite/local classes.

**Tech Stack:** Python 3.12, SQL repository abstraction, PostgreSQL-compatible production database, object storage compatible with S3/GCS semantics, pytest contract tests, existing SQLite/local adapters

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- Local stdio must continue to work with SQLite and local artifact storage
- Production HTTP must fail startup if configured for ephemeral metadata or artifact storage
- No service may branch on provider-specific behavior after construction
- Metadata, jobs, credentials, and artifact references must survive API and worker replacement
- Backup/restore must be tested, not documented only
- Tenant/owner authorization data must remain queryable and preserved across migration
- Binary model artifacts must not be stored inside generic JSON payload columns

---

## Task 1: Define persistence interfaces before adding providers

**Files:**
- Create: `src/marketing_mcp/storage/interfaces.py`
- Modify: `src/marketing_mcp/storage/metadata.py`
- Modify: `src/marketing_mcp/storage/artifacts.py`
- Test: `tests/contract/test_storage_interfaces.py`

**Interfaces:**
- Produces: `MetadataStore`, `ArtifactStore`
- Consumes: existing service calls to metadata and artifacts

- [ ] **Step 1: Inventory every method used by services**

Map calls from `Application`, `DatasetService`, `ModelingService`, `DecisionService`, `DiagnosticsService`, `CLVService`, and job/credential repositories. The interfaces must contain only methods used by production code.

- [ ] **Step 2: Write contract tests against existing adapters**

Instantiate `SQLiteMetadataStore` and `LocalArtifactStore` through their interface types and verify dataset/model/scenario/CLV persistence plus artifact put/get/delete semantics.

- [ ] **Step 3: Define protocol/ABC interfaces**

Required artifact surface:

```python
class ArtifactStore(Protocol):
    def put_bytes(self, key: str, data: bytes) -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
```

The metadata interface must expose typed operations already used by services rather than raw SQL connections.

- [ ] **Step 4: Make existing adapters satisfy the interfaces without behavior change**

- [ ] **Step 5: Run contract tests**

Run: `uv run pytest tests/contract/test_storage_interfaces.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/storage/interfaces.py src/marketing_mcp/storage/metadata.py src/marketing_mcp/storage/artifacts.py tests/contract/test_storage_interfaces.py
git commit -m "refactor: define production persistence interfaces"
```

## Task 2: Remove direct SQLite connection dependencies from application services

**Files:**
- Modify: `src/marketing_mcp/app.py`
- Modify: `src/marketing_mcp/jobs/repository.py`
- Modify: `src/marketing_mcp/credentials/sqlite_repository.py`
- Modify: `src/marketing_mcp/http/health.py`
- Test: `tests/unit/test_application_storage_injection.py`

**Interfaces:**
- Consumes: storage interfaces
- Produces: injectable application composition root

- [ ] **Step 1: Write a failing composition test**

Construct `Application` with fake metadata/artifact/job/credential repositories and assert no service reaches `metadata.conn` directly.

- [ ] **Step 2: Change `Application` into the composition root**

Allow explicit provider injection while retaining `Application()` defaults for local mode.

Suggested constructor surface:

```python
def __init__(
    self,
    settings: Settings | None = None,
    metadata: MetadataStore | None = None,
    artifacts: ArtifactStore | None = None,
    job_repo: JobRepository | None = None,
    credential_repo: CredentialRepository | None = None,
): ...
```

- [ ] **Step 3: Move DB health checks behind the metadata interface**

Add `healthcheck() -> tuple[bool, str | None]` or an equivalent typed result to the store contract; do not access `.conn` from HTTP readiness.

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/app.py src/marketing_mcp/jobs/repository.py src/marketing_mcp/credentials/sqlite_repository.py src/marketing_mcp/http/health.py tests/unit/test_application_storage_injection.py
git commit -m "refactor: inject persistence providers into application"
```

## Task 3: Add external SQL metadata provider

**Files:**
- Create: `src/marketing_mcp/storage/sql_metadata.py`
- Create: `src/marketing_mcp/storage/schema.py`
- Modify: `src/marketing_mcp/config.py`
- Test: `tests/contract/test_metadata_provider_contract.py`
- Test: `tests/integration/test_external_metadata_lifecycle.py`

**Interfaces:**
- Consumes: `MetadataStore`
- Produces: production SQL-backed metadata adapter

- [ ] **Step 1: Define normalized production tables**

At minimum keep indexed columns for:

```text
id
tenant_id
owner
status
created_at
updated_at
```

for datasets/models/scenarios/CLV records where applicable, plus JSON payload for provider-neutral extensible metadata.

- [ ] **Step 2: Preserve existing IDs and ownership during migration**

Write a migration test that copies representative SQLite records into the external provider and compares IDs, tenant IDs, owners, status, lineage references, and semantic hashes.

- [ ] **Step 3: Implement the provider through the interface only**

Do not expose a provider connection object to services.

- [ ] **Step 4: Add configuration selection**

Define explicit backend values:

```text
sqlite
sql
```

Production profile rejects `sqlite` unless an explicit beta-only override is set.

- [ ] **Step 5: Run the common contract suite against both providers**

Expected: the same behavior contract passes for SQLite and external SQL.

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/storage/sql_metadata.py src/marketing_mcp/storage/schema.py src/marketing_mcp/config.py tests/contract/test_metadata_provider_contract.py tests/integration/test_external_metadata_lifecycle.py
git commit -m "feat: add external production metadata provider"
```

## Task 4: Add object-storage artifact provider

**Files:**
- Create: `src/marketing_mcp/storage/object_artifacts.py`
- Modify: `src/marketing_mcp/config.py`
- Test: `tests/contract/test_artifact_provider_contract.py`
- Test: `tests/integration/test_artifact_integrity.py`

**Interfaces:**
- Consumes: `ArtifactStore`
- Produces: external object-storage adapter

- [ ] **Step 1: Define deterministic artifact keys**

Use stable keys derived from tenant/resource identity, for example:

```text
tenants/{tenant_id}/models/{model_id}/model.nc
tenants/{tenant_id}/models/{model_id}/plots/{plot_type}.png
```

Do not include user-controlled path traversal segments.

- [ ] **Step 2: Write integrity tests**

Store bytes, persist SHA-256 digest in metadata, reload bytes through a fresh adapter instance, and assert the digest matches.

- [ ] **Step 3: Implement provider-neutral operations**

The adapter must support put/get/exists/delete and return a stable object URI/key, not a signed temporary URL as the persistent reference.

- [ ] **Step 4: Add backend selection**

Define:

```text
local
object
```

Production profile rejects `local` unless beta-only single-instance mode is explicit.

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/storage/object_artifacts.py src/marketing_mcp/config.py tests/contract/test_artifact_provider_contract.py tests/integration/test_artifact_integrity.py
git commit -m "feat: add production object artifact storage"
```

## Task 5: Make jobs and credentials use production SQL repositories

**Files:**
- Create: `src/marketing_mcp/jobs/sql_repository.py`
- Create: `src/marketing_mcp/credentials/sql_repository.py`
- Modify: `src/marketing_mcp/app.py`
- Test: `tests/contract/test_job_repository_contract.py`
- Test: `tests/contract/test_credential_repository_contract.py`

**Interfaces:**
- Consumes: production SQL database configuration
- Produces: shared durable job and credential repositories

- [ ] **Step 1: Run the same repository contracts against SQLite first**

Contracts must cover create/get/update/list, tenant filtering, atomic worker claim, idempotency lookup, credential issue/verify/revoke, and audit events.

- [ ] **Step 2: Implement SQL repositories without changing service semantics**

- [ ] **Step 3: Verify API and worker share the same job repository**

Run an integration test using separate `Application` instances against one production-test database.

- [ ] **Step 4: Verify credential revocation crosses processes**

Issue through one application instance, authenticate through a second, revoke through the first, then verify the second rejects the key on the next request.

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/jobs/sql_repository.py src/marketing_mcp/credentials/sql_repository.py src/marketing_mcp/app.py tests/contract/test_job_repository_contract.py tests/contract/test_credential_repository_contract.py
git commit -m "feat: share production jobs and credentials through SQL"
```

## Task 6: Add migration, backup, restore, and reconciliation tools

**Files:**
- Create: `src/marketing_mcp/storage/backup.py`
- Create: `src/marketing_mcp/storage/reconcile.py`
- Create: `scripts/migrate_storage.py`
- Create: `scripts/verify_restore.py`
- Test: `tests/integration/test_backup_restore.py`
- Test: `tests/integration/test_artifact_reconciliation.py`

**Interfaces:**
- Consumes: metadata and artifact interfaces
- Produces: deterministic migration/backup/restore/reconciliation operations

- [ ] **Step 1: Write a full backup/restore test**

Seed dataset, model metadata, scenario, job, credential metadata, and model artifact. Export, create a fresh empty environment, restore, then verify all IDs/references/digests.

- [ ] **Step 2: Implement metadata export with schema version**

Every backup manifest must record application version, schema version, created timestamp, record counts, and artifact digests.

- [ ] **Step 3: Implement artifact reconciliation**

Detect:

```text
metadata reference with missing object
object with no metadata reference
digest mismatch
```

Do not auto-delete or auto-repair during detection mode.

- [ ] **Step 4: Add explicit repair mode**

Repair operations must be opt-in and produce an audit report.

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/storage/backup.py src/marketing_mcp/storage/reconcile.py scripts/migrate_storage.py scripts/verify_restore.py tests/integration/test_backup_restore.py tests/integration/test_artifact_reconciliation.py
git commit -m "feat: add storage backup restore and reconciliation"
```

## Task 7: Make readiness provider-aware

**Files:**
- Modify: `src/marketing_mcp/http/health.py`
- Test: `tests/unit/test_readiness_storage_backends.py`

**Interfaces:**
- Consumes: metadata/artifact `healthcheck()`
- Produces: dependency-aware `/health/ready`

- [ ] **Step 1: Add failure tests**

External DB unavailable must yield 503. Object storage write/read failure must yield 503. Local beta mode must report the configured backend names in non-sensitive form.

- [ ] **Step 2: Verify read and write ability where required**

Readiness must not only check client construction. Use a low-cost provider health operation with bounded timeout.

- [ ] **Step 3: Commit**

```bash
git add src/marketing_mcp/http/health.py tests/unit/test_readiness_storage_backends.py
git commit -m "fix: make readiness verify configured persistence backends"
```

## Acceptance criteria

This plan is complete when:

- local SQLite/local-file mode still passes all existing tests
- production profile can run with external SQL and object storage without service-layer provider branches
- API and worker processes see the same jobs and credentials
- instance replacement does not lose model metadata or artifacts
- cross-process credential revocation is immediate
- backup/restore into a fresh environment is executable and verified
- artifact orphan/missing/digest mismatches are detected
- readiness becomes 503 when required external persistence is unavailable
- production startup rejects ephemeral persistence unless an explicit beta-only override is configured
