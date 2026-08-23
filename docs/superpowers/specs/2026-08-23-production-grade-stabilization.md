# PyMC Marketing MCP Production-Grade Stabilization Spec

**Status:** Proposed execution baseline
**Date:** 2026-08-23
**Target:** Move the repository from an advanced beta into a production-grade Bayesian marketing decision service without adding unrelated feature surface.

## 1. Problem Statement

The repository has a credible MMM core, typed MCP contracts, persisted model artifacts, diagnostics gating, budget simulation, calibration, CLV, plotting, model comparison, and HTTP/stdio transports. The current risk is not lack of features. The risk is that some public contracts and agent skills are ahead of verified behavior, while remote execution, persistence, security, CI, and long-running job handling are not yet strong enough for production use.

This program therefore prioritizes correctness, recoverability, security, reproducibility, and release evidence over new statistical features.

## 2. Product Invariants

The following invariants apply to every workstream and are release blockers when violated.

1. No MCP tool may claim behavior that is not covered by executable behavioral or statistical tests.
2. An LLM must never calculate posterior statistics or invent model outputs when the statistical library can produce them.
3. Decision tools must remain blocked until the model passes the diagnostics decision gate.
4. Any recommended allocation must conserve budget within an explicit tolerance and respect all declared constraints.
5. Any model-derived recommendation must include model identity, dataset identity, configuration identity, package versions, and uncertainty evidence.
6. Remote HTTP mode must fail closed when production authentication is not configured.
7. Credentials must never be accepted in query parameters, logged, printed, or persisted in model metadata.
8. Cloud restarts must not orphan model artifacts from their metadata.
9. Expensive statistical operations must be represented as cancellable, inspectable jobs rather than opaque request-bound calls.
10. Every release claim must be generated from CI evidence rather than manually asserted.
11. Agent skills must never describe a stronger capability than the current implementation.
12. Local mode may stay lightweight. Production mode must use production persistence, authorization, audit, and job controls.

## 3. Scope

### In scope

- v0.4 correctness audit and contract repair
- channel-specific MMM configuration
- true multi-period flighting behavior or honest downgrade of the current tool
- model comparison semantics
- CLV contract separation and verification
- plotting statistical aggregation correctness
- MCP server decomposition
- production authentication and authorization
- job execution and cancellation
- Postgres metadata and object storage abstractions
- idempotency and recovery
- observability
- CI, release, supply-chain, and documentation drift gates
- executable agent skill evals
- release evidence and production readiness scoring

### Out of scope until stabilization gates pass

- new model families unrelated to existing contracts
- arbitrary Python execution
- unconstrained user-supplied PyMC code
- direct ad platform write-back or autonomous budget changes
- multi-tenant billing
- UI redesign work not required for operational correctness

## 4. Maturity Model

### M0 - Prototype

Tool calls work on a developer machine, but correctness, persistence, and recovery are informal.

### M1 - Verified Local

Local stdio and HTTP behavior is covered by unit, contract, integration, and statistical tests. Public tool descriptions match tested behavior.

### M2 - Recoverable Service

Expensive operations are jobs. Metadata and artifacts survive restart. Idempotency, cancellation, and retry rules exist.

### M3 - Secure Remote

OAuth 2.1 resource-server mode, scoped authorization, request limits, secret handling, and audit records are enforced.

### M4 - Operable Production

Metrics, traces, structured logs, SLOs, runbooks, backup/restore, release gates, and canary compatibility checks exist.

### M5 - Decision-Grade

Statistical decisions have explicit evidence policies, champion/challenger lifecycle, model refresh criteria, executable agent evals, and reproducible decision history.

**Target for v0.5.0:** M3 minimum, with M4 CI and observability foundations.
**Target for v1.0.0:** M5 release gate.

## 5. Workstreams

### WS-A: Production Truth and Release Discipline

Goal: establish one truthful source of version, capability, compatibility, and release evidence.

Deliverables:
- version source of truth
- v0.4 release verification report
- generated tool inventory
- generated compatibility report
- documentation drift checks
- release evidence artifact

### WS-B: Scientific Contract Hardening

Goal: remove contract-to-behavior mismatches.

Deliverables:
- verified channel-specific model configuration
- correct model comparison criteria and weighting semantics
- CLV model-specific APIs and tests
- statistically correct plotting aggregation
- true dynamic flighting or renamed heuristic schedule builder
- decision-tool invariants

### WS-C: MCP Protocol and Server Boundaries

Goal: keep protocol code small, composable, and testable.

Deliverables:
- split tool registration by domain
- resource registration modules
- common response envelope helpers
- centralized authorization context
- generated discovery snapshot tests

### WS-D: Security and Authorization

Goal: make remote HTTP mode safe by default.

Deliverables:
- OAuth 2.1 resource-server support
- API-key mode limited to local/private deployments
- scoped tool authorization
- no query-string credentials
- secret-safe logs and errors
- request limits and rate-control hooks
- production startup validation

### WS-E: Jobs and Compute Control

Goal: make sampling and diagnostics operationally manageable.

Deliverables:
- Job model and repository
- submit/status/cancel/result APIs
- idempotency keys
- resource limits and timeouts
- failure classification
- retry policy
- worker abstraction

### WS-F: Persistence and Recovery

Goal: prevent metadata and artifact loss.

Deliverables:
- repository interfaces
- SQLite local implementation
- Postgres production implementation
- filesystem local artifact store
- GCS production artifact store
- schema migrations
- backup/restore test
- orphan reconciliation

### WS-G: Observability and Operations

Goal: make failures diagnosable before users report them.

Deliverables:
- structured logs
- metrics
- traces
- health/readiness endpoints
- SLO definitions
- alert thresholds
- operator runbook

### WS-H: CI, Supply Chain, and Release

Goal: prevent unverified code from shipping.

Deliverables:
- PR checks
- nightly statistical checks
- upstream dependency canary
- wheel and Docker install verification
- vulnerability and secret scanning
- SBOM
- signed release metadata where supported

### WS-I: Agent Skills and Evals

Goal: make agent behavior evidence-driven and version-aware.

Deliverables:
- executable eval harness
- positive and negative scenarios
- tool-trace assertions
- skill capability matrix
- versioned skill metadata
- refusal and decision-gate tests

## 6. Dependency Order

Execution order is mandatory unless a plan explicitly proves independence.

1. WS-A Production Truth
2. WS-B Scientific Contract Hardening
3. WS-C MCP Server Boundaries
4. WS-D Security and Authorization
5. WS-E Jobs and Compute Control
6. WS-F Persistence and Recovery
7. WS-G Observability and Operations
8. WS-H CI and Release Hardening
9. WS-I Agent Skills and Evals
10. v0.5 release candidate validation

WS-G and WS-H may start after WS-C once stable interfaces exist, but their final gates depend on WS-D through WS-F.

## 7. Release Gates

### Gate G0 - Baseline Truth

Must pass before feature work continues.

- package version, health endpoint version, docs, and image tag agree
- all public tools appear in generated inventory
- every public tool has a documented contract
- v0.4 tests are executed and recorded from current HEAD
- no documentation claims a completed behavior without a linked test

### Gate G1 - Scientific Correctness

- channel-specific configuration changes actual model construction
- model comparison honors `loo`, `waic`, `stacking`, and `all` semantics
- CLV APIs are model-specific and real-fit tested
- dynamic flighting behavior is truthful and budget-conserving
- plot calculations use statistically correct dimensions
- all decision tools retain diagnostics gating

### Gate G2 - Service Recovery

- model/job state survives process restart
- artifact and metadata references remain consistent
- duplicate submissions can be detected
- cancellation and failure state are persisted
- backup and restore are tested

### Gate G3 - Remote Security

- production HTTP refuses startup without configured auth
- token-in-query is rejected
- scopes are enforced per tool group
- secrets are redacted in logs and errors
- unauthorized cross-principal access is rejected

### Gate G4 - Operability

- logs, metrics, and traces include request and job correlation IDs
- readiness reflects dependency health
- sampling failures are observable
- alertable error-rate and queue-depth metrics exist
- operator runbook covers the top failure modes

### Gate G5 - Release Evidence

- PR pipeline green
- nightly statistical suite green
- package and image built from the same commit
- clean install smoke test passes
- dependency canary is green or explicitly waived with documented evidence
- release evidence file is generated from CI

## 8. Testing Strategy

### Unit

Pure domain behavior, schema validation, constraint construction, identifier validation, and error mapping.

### Contract

Tool input/output shape, resource URIs, error envelopes, auth requirements, job states, storage interfaces.

### Integration

Real SQLite/Postgres adapters, object storage adapter contract, MCP stdio and HTTP roundtrips, restart recovery, migration, OAuth token verification.

### Statistical

Real PyMC-Marketing fitting and decision behavior. Small deterministic datasets are acceptable, but no mocking of the statistical boundary for release-critical claims.

### Agent Evals

Real tool traces with assertions on tool choice, decision gate behavior, warning surfacing, and forbidden claims.

## 9. Failure Policy

Failures must be classified into stable error families:

- `INPUT_INVALID`
- `DATA_INVALID`
- `MODEL_FIT_FAILED`
- `MODEL_DIAGNOSTICS_REJECTED`
- `DECISION_BLOCKED`
- `OPTIMIZATION_INFEASIBLE`
- `DEPENDENCY_UNAVAILABLE`
- `AUTH_REQUIRED`
- `AUTH_FORBIDDEN`
- `RESOURCE_LIMIT_EXCEEDED`
- `JOB_CANCELLED`
- `STORAGE_UNAVAILABLE`
- `ARTIFACT_CORRUPT`
- `INTERNAL_ERROR`

Every error must include a machine-readable code, a safe message, evidence safe for the caller, and a next action when one exists.

## 10. Data and Privacy Policy

- Never log raw customer rows, full media datasets, tokens, or secrets.
- Hash dataset contents for identity and reproducibility.
- Store dataset and artifact access by principal/tenant when production multi-user mode is enabled.
- Keep audit events separate from statistical artifacts.
- Make retention configurable for datasets, jobs, plots, and audit records.

## 11. Definition of Production Grade

The repository may be described as production-grade only when all of the following are true:

- current public contracts match tested behavior
- statistical decisions are reproducible from persisted evidence
- remote access is authenticated and authorized
- long-running operations are recoverable jobs
- state survives restart
- CI blocks regressions
- operational signals exist for failure detection
- release evidence is generated automatically
- agent behavior is covered by executable evals

Until then, release notes should use the phrase `advanced beta` or `release candidate` as appropriate.