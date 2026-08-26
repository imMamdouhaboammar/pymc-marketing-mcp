# Production Stabilization and Hardening Plan Index

This directory coordinates the move from the current v0.4.x advanced-beta/release-candidate implementation to a release-approved production service, followed by a decision-grade v1.0 target

Plans describe target work. They are not evidence that the work is complete

## Current state after the 2026-08-26 core hardening commit

The repository now includes more production-oriented primitives than the original 2026-08-23 baseline

- SQLite migrations
- persisted job records and async job tools
- local stale-job recovery
- security profiles
- scope policy and ownership helpers
- query-credential rejection
- request-safety/redaction helpers
- structured logging/metrics foundations
- liveness/readiness foundations
- additional release/agent tests

The hardening amendment remains necessary because several full-system properties are still unproven or incomplete

- authenticated HTTP identity is not yet proven to become the principal used by real MCP tool execution
- MCP resources do not yet use request-scoped scope/ownership authorization
- ownership helpers need complete lifecycle wiring and E2E tenant evidence
- dashboard API keys remain a separate raw-secret browser/Firestore prototype
- current statistical jobs execute inside the API process rather than isolated durable workers
- production metadata/object-storage adapters and backup/restore evidence are not complete
- traces, SLOs/alerts/runbooks and required CI/release workflows are not complete
- agent eval fixtures still require conversion to runtime trace evidence
- upstream compatibility is not yet a release/feature-admission gate
- current-head machine-generated release evidence does not yet exist for the hardening branch

## Authoritative execution order

### 1. Runtime truth baseline: H0

Use `2026-08-26-runtime-truth-ci-gates.md`

First establish current-head evidence and make readiness/doc status derive from executed reality rather than assertions

### 2. Remote identity and resource isolation: H1 + H2 / G3

Use `2026-08-26-auth-context-resource-isolation.md` together with the unfinished requirements of `2026-08-23-security-mcp-hardening.md`

Required outcome

```text
HTTP auth
  -> Principal
  -> ExecutionContext
  -> MCP tool/resource
  -> scope
  -> object/tenant authorization
```

### 3. Credential control plane: H3

Use `2026-08-26-dashboard-control-plane-security.md`

The dashboard must consume the same credential authority as the MCP server and must not persist raw reusable secrets

### 4. Durable jobs, storage and recovery: G2 + H4

Use both

- `2026-08-23-jobs-storage-recovery.md`
- `2026-08-26-jobs-mcp-task-boundary.md`

Current SQLite/in-process jobs are the starting point, not the final production worker model

The internal JobService stays transport-neutral. Current custom job tools remain compatibility tools. Future MCP Tasks support, when supported by the selected SDK/runtime, is an adapter over the same job domain

### 5. Resilience, observability and release automation: G4 + G5

Use

- `2026-08-23-performance-resilience-capacity.md`
- `2026-08-23-observability-ci-release.md`
- remaining tasks in `2026-08-26-runtime-truth-ci-gates.md`

Required outcome includes API/worker capacity separation, traces, dependency readiness, alerts/runbooks, PR/statistical/security/release workflows and machine-generated release evidence

### 6. Agent quality: AQG + H5

Use

- `2026-08-23-agent-skills-evals.md`
- `2026-08-26-agent-skill-eval-hardening.md`

Required outcome is capability-driven routing plus executable tool-trace/negative eval evidence. Committed `passed: true` values are not evidence

### 7. Upstream compatibility and feature admission: H6

Use `2026-08-26-upstream-compatibility-capability-gates.md`

Feature work remains frozen until the locked production lane and latest-allowed canary can prove upstream compatibility for the affected statistical surface

### 8. Release candidate review

Return to `2026-08-23-production-grade-master-program.md`

Build the v0.5 release evidence pack only after the required G/H/AQG gates are actually green from current-head evidence

### 9. Decision-grade v1.0

Use `2026-08-23-decision-governance-audit.md`

M5 adds append-only audit/decision records, lifecycle/governance, freshness and historical reproducibility requirements after the production runtime is stable

## Original 2026-08-23 plans

These remain authoritative for work not explicitly amended by 2026-08-26

- `2026-08-23-production-grade-master-program.md`
- `2026-08-23-production-truth-release-discipline.md`
- `2026-08-23-scientific-contract-hardening.md`
- `2026-08-23-security-mcp-hardening.md`
- `2026-08-23-jobs-storage-recovery.md`
- `2026-08-23-performance-resilience-capacity.md`
- `2026-08-23-observability-ci-release.md`
- `2026-08-23-agent-skills-evals.md`
- `2026-08-23-decision-governance-audit.md`

## 2026-08-26 amendment plans

- `2026-08-26-hardening-master-program.md`
- `2026-08-26-runtime-truth-ci-gates.md`
- `2026-08-26-auth-context-resource-isolation.md`
- `2026-08-26-dashboard-control-plane-security.md`
- `2026-08-26-jobs-mcp-task-boundary.md`
- `2026-08-26-agent-skill-eval-hardening.md`
- `2026-08-26-upstream-compatibility-capability-gates.md`

## Dependency rule

A plan may start early only when it does not rely on an unfinished interface

It may not be marked complete merely because code for one sub-property exists

Examples

- scope-policy code can exist before H1, but H1 remains open until the real authenticated HTTP principal reaches tool execution
- ownership helpers can exist before H2, but H2 remains open until tool and resource E2E tenant tests pass
- SQLite jobs can exist before G2/H4, but durable compute remains open until worker/process failure recovery is proven
- logging/metrics can exist before G4, but operability remains open until traces, dependency readiness and runbooks are evidenced
- release-test files can exist before G5, but G5 remains open until required workflows and artifacts execute for the release commit

## Review rule

Every material implementation task follows

```text
Inspect current state
Select focused skills/workflows
Write failing test
Implement minimum correct change
Run focused tests
Independent review
Run wider verification
Update capability/docs/evidence
Commit
```

Additional review focus

- statistical changes: scientific semantics and real-library tests
- security changes: auth bypass, cross-principal/resource access and secret exposure
- persistence/jobs: crash/restart, cancellation, partial write and artifact integrity
- agent changes: tool traces, forbidden calls and warning preservation
- governance: provenance immutability and historical reproducibility

## Release rule

No v0.5.0 release until G0 through G5, H0 through H6 and AQG are green from current-head machine evidence

No v1.0.0 release until the M5 Decision-Grade gate is also green
