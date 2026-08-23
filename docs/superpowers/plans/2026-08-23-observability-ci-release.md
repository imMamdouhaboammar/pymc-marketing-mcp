# Observability, CI, and Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make production failures visible, prevent unverified changes from merging, continuously test compatibility with the upstream statistical stack, and generate trustworthy release evidence from CI.

**Architecture:** Instrument request, job, model, and storage boundaries with structured context. Add health/readiness semantics for dependencies. Build layered CI so fast checks run on every PR, statistical checks run on protected/nightly paths, and release workflows verify wheel/container identity from a single commit.

**Tech Stack:** structlog, OpenTelemetry API/SDK/exporters, Prometheus-compatible metrics or OpenTelemetry metrics, pytest, Ruff, GitHub Actions, uv, Docker, Cloud Build, dependency/security scanners.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Never emit raw data rows, customer identifiers beyond approved pseudonymous IDs, tokens, or secrets to logs/traces.
- Metrics labels must remain low-cardinality. Model IDs, dataset IDs, and job IDs belong in logs/traces, not metric labels.
- Statistical test failures must never be auto-waived by rerunning until green.
- Release artifacts must be built from the same commit that passed release gates.
- CI evidence must include exact dependency versions.

---

### Task 1: Add structured logging foundation

**Files:**
- Create: `src/marketing_mcp/observability/logging.py`
- Modify: `src/marketing_mcp/cli.py`
- Modify: service/job boundaries
- Test: `tests/unit/test_structured_logging.py`

**Required context keys:**
- request_id
- principal_subject_hash or safe subject identifier
- tenant_id when enabled
- tool_name
- job_id
- job_type
- model_id
- dataset_id
- duration_ms
- status
- error_code

- [ ] Configure JSON logs for production and readable console logs for local development.
- [ ] Route all payloads through the redaction helper from the security plan.
- [ ] Add context-bound logging helpers so nested service calls inherit request/job IDs.
- [ ] Test that tokens and API keys are absent from captured logs.
- [ ] Test that unexpected exceptions include type and correlation ID but not unsafe payloads.
- [ ] Commit.

### Task 2: Add metrics

**Files:**
- Create: `src/marketing_mcp/observability/metrics.py`
- Test: `tests/unit/test_metrics_contract.py`

**Counters:**
- MCP requests by tool/outcome
- auth failures by reason family
- job submissions/completions/failures/cancellations
- decision gate rejects
- artifact integrity failures
- extrapolation warnings

**Histograms:**
- tool latency
- job queue wait
- job execution duration
- model fit duration
- artifact load/store duration

**Gauges:**
- queued jobs
- running jobs
- stale jobs

- [ ] Keep labels limited to stable categories such as tool name, job type, outcome, error family.
- [ ] Do not label metrics by model_id, dataset_id, subject, or raw exception text.
- [ ] Add deterministic unit tests against the metrics adapter.
- [ ] Commit.

### Task 3: Add traces

**Files:**
- Create: `src/marketing_mcp/observability/tracing.py`
- Modify: MCP execution wrapper
- Modify: job executor
- Modify: repository/artifact adapters
- Test: `tests/integration/test_trace_propagation.py`

**Span hierarchy:**

```text
mcp.tool
  service.operation
    job.submit or job.execute
      pymc.operation
      repository.operation
      artifact.operation
```

- [ ] Generate or accept a request correlation ID.
- [ ] Propagate trace context into queued jobs via stored trace metadata.
- [ ] Add safe attributes only.
- [ ] Test that a tool submission and its later job execution can be correlated.
- [ ] Commit.

### Task 4: Define health, liveness, and readiness

**Files:**
- Create: `src/marketing_mcp/http/health.py`
- Modify: `src/marketing_mcp/cli.py`
- Test: `tests/integration/test_health_readiness.py`

**Endpoints:**
- `/health/live`: process is alive
- `/health/ready`: required dependencies available for the configured profile
- `/health`: compatibility summary if retained

**Readiness dependencies in production:**
- metadata database
- job repository/executor
- artifact store
- auth verifier configuration

- [ ] Ensure liveness does not fail because Postgres is briefly unavailable.
- [ ] Ensure readiness does fail when required durable dependencies are unavailable.
- [ ] Keep public response non-sensitive.
- [ ] Include application version and commit identity.
- [ ] Commit.

### Task 5: Define SLOs and alerts

**Files:**
- Create: `docs/operations/SLOS.md`
- Create: `docs/runbooks/high-error-rate.md`
- Create: `docs/runbooks/job-queue-stalled.md`
- Create: `docs/runbooks/storage-integrity.md`
- Create: `docs/runbooks/statistical-failure-spike.md`

**Initial SLO definitions should distinguish:**
- control-plane/read tools
- job submission
- statistical job completion

Do not promise a fixed statistical completion latency across arbitrary datasets.

- [ ] Define availability and latency objectives only where bounded.
- [ ] Define queue-age and stale-job alerts.
- [ ] Define auth-failure anomaly alert.
- [ ] Define artifact-integrity alert.
- [ ] Define repeated model-fit failure alert by error family.
- [ ] Commit.

### Task 6: Create fast PR CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`
- Create or modify: `pyproject.toml` test markers/config

**Jobs:**
1. lock/install validation
2. Ruff check
3. format check
4. type check if a type checker is adopted in the repository
5. unit tests
6. contract tests
7. MCP integration tests
8. package build
9. clean wheel install smoke test
10. Docker build smoke test

- [ ] Use `uv sync --frozen --extra dev`.
- [ ] Cache dependency downloads without caching generated model artifacts.
- [ ] Upload junit/test reports on failure.
- [ ] Fail on docs drift and capability inventory drift.
- [ ] Verify the wheel's `marketing-mcp --help` and import path in a clean venv.
- [ ] Commit.

### Task 7: Create statistical CI workflow

**Files:**
- Create: `.github/workflows/statistical.yml`

**Triggers:**
- nightly schedule
- manual workflow dispatch
- protected release branch/tag candidate
- optional path-filtered PR run when core statistical files change

**Tests:**
- real MMM single dimension
- real multidimensional MMM
- channel-specific configuration
- transform smoke matrix
- budget decision invariants
- flighting behavior
- CLV real models
- model comparison
- save/load invariants

- [ ] Pin thread/process counts to avoid CI oversubscription.
- [ ] Capture dependency versions and machine details.
- [ ] Run each release-critical stochastic test with deterministic seed and explicit tolerance.
- [ ] Reject flaky-test retry as a substitute for fixing nondeterminism.
- [ ] Upload evidence summaries.
- [ ] Commit.

### Task 8: Add upstream compatibility canary

**Files:**
- Create: `.github/workflows/upstream-canary.yml`
- Create: `scripts/compatibility_canary.py`
- Modify: `docs/API-COMPATIBILITY.md`

**Matrix:**
- locked production dependency set
- latest allowed PyMC-Marketing/PyMC/MCP versions under declared constraints
- optional pre-release lane that is non-blocking but visible

- [ ] Run adapter import and constructor checks.
- [ ] Run a minimal real fit/save/load flow.
- [ ] Run MCP discovery/roundtrip.
- [ ] Detect upstream API removals or changed result shape early.
- [ ] Do not automatically widen dependency constraints when a canary passes.
- [ ] Commit.

### Task 9: Add security and supply-chain checks

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `.github/workflows/security.yml` if separation is cleaner

**Checks:**
- dependency vulnerability audit
- secret scanning
- static security checks appropriate to Python
- Docker image vulnerability scan
- SBOM generation for wheel/container
- license inventory if required by distribution policy

- [ ] Ensure scans fail on configured severity policy rather than only printing reports.
- [ ] Store SBOM as CI artifact for release builds.
- [ ] Confirm no production secret is required to run PR checks.
- [ ] Commit.

### Task 10: Create release workflow

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `scripts/collect_release_evidence.py`
- Modify: `scripts/verify_release_identity.py`

**Release sequence:**
1. verify G0-G5 gate tests
2. run full statistical suite
3. build wheel/sdist
4. clean-install package smoke test
5. build Docker image
6. verify package/image version and commit identity
7. generate SBOM
8. generate release evidence JSON/Markdown
9. publish artifacts only after all checks pass

- [ ] Ensure a rerun cannot publish a different artifact under the same immutable version.
- [ ] Hash wheel, sdist, and container digest in release evidence.
- [ ] Tie image labels to git SHA.
- [ ] Commit.

### Task 11: Align Cloud Build with release identity

**Files:**
- Modify: `cloudbuild.yaml`
- Modify: `scripts/deploy_cloud_run.sh`
- Modify: `docs/DEPLOYMENT-GCP.md`

- [ ] Deploy immutable image digest or commit tag rather than mutable `latest` for production.
- [ ] Keep `latest` only as optional developer convenience if retained.
- [ ] Use the same concurrency setting across documented and automated deployment paths.
- [ ] Separate MCP web/API instance configuration from CPU-heavy worker configuration if jobs use independent workers.
- [ ] Document CPU, memory, timeout, and max-instance rationale.
- [ ] Commit.

### Task 12: Establish Gate G4

**Files:**
- Create: `tests/release/test_g4_operability.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- structured logs contain correlation identifiers
- redaction tests pass
- readiness reflects dependency failure
- metrics record tool/job outcomes
- trace propagation works across job boundary
- runbooks exist for defined critical alerts

- [ ] Mark G4 green from CI evidence only.

### Task 13: Establish Gate G5

**Files:**
- Create: `tests/release/test_g5_release_evidence.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- fast PR workflow definition contains required jobs
- statistical workflow exists
- upstream canary exists
- wheel install smoke is part of CI
- Docker build is part of CI
- release evidence schema contains commit and artifact hashes
- package/image version identity check passes

- [ ] Execute a dry-run release from a test tag or manual workflow without publishing.
- [ ] Verify generated evidence is reproducible for the same artifacts.
- [ ] Mark G5 green only after the dry run succeeds.

## Acceptance Criteria

This plan is complete when:

- production requests/jobs/storage actions are observable without exposing secrets
- readiness reflects actual dependency availability
- alertable operational signals and runbooks exist
- every PR is blocked by fast correctness checks
- statistical regressions are caught by a dedicated workflow
- upstream dependency changes are tested continuously
- package and container artifacts are tied to one commit
- release evidence is machine-generated
- Gates G4 and G5 are green