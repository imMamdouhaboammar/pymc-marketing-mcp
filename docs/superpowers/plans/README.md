# Production Stabilization Plan Index

This directory contains the execution program for moving PyMC Marketing MCP from the current v0.4.x advanced-beta state to a production-grade release candidate.

## Authoritative Execution Order

1. `2026-08-23-production-grade-master-program.md`
   - program coordination, freeze, release gates, final release candidate review

2. `2026-08-23-production-truth-release-discipline.md`
   - canonical version, capability inventory, documentation drift, release evidence
   - exit gate: G0

3. `2026-08-23-scientific-contract-hardening.md`
   - channel-specific configuration, model comparison, CLV, flighting, plotting, decision gate
   - exit gate: G1

4. `2026-08-23-security-mcp-hardening.md`
   - MCP server decomposition, principals, OAuth, scopes, ownership, request safety, deployment security
   - exit gate: G3 security controls

5. `2026-08-23-jobs-storage-recovery.md`
   - durable jobs, idempotency, Postgres, object storage, restart recovery, backup/restore
   - exit gate: G2

6. `2026-08-23-performance-resilience-capacity.md`
   - resource classes, admission control, worker/API separation, backpressure, load, fault injection
   - required before final operability/release gates

7. `2026-08-23-observability-ci-release.md`
   - logs, metrics, traces, health/readiness, SLOs, PR CI, statistical CI, canary, release evidence
   - exit gates: G4 and G5

8. `2026-08-23-agent-skills-evals.md`
   - capability router, truthful skills, executable evals, negative decision-safety tests, tool trace assertions
   - exit gate: Agent Quality Gate

9. Return to `2026-08-23-production-grade-master-program.md`
   - execute the release-candidate evidence pack and final production readiness review

## Dependency Rule

A plan may begin early only when its interfaces do not depend on an unfinished prior plan. It may not be marked complete until all upstream interfaces it consumes are green.

Examples:

- CI scaffolding can begin before Postgres is complete, but G5 cannot be green until the Postgres/recovery suites are part of CI.
- Skill text cleanup can begin early, but stable capability claims cannot be finalized until G1 is green.
- Observability wrappers can begin after MCP/job interfaces stabilize, but production SLO evidence depends on resilience/capacity tests.

## Review Rule

Every material implementation task follows:

```text
Inspect current state
Select focused skills/workflows
Write failing test
Implement minimum change
Run focused tests
Independent review
Run wider verification
Update evidence/docs
Commit
```

For statistical behavior changes, independent review must include scientific semantics, not only code quality.

For security changes, independent review must include authorization bypass and secret exposure cases.

For persistence changes, independent review must include crash/restart and partial-write cases.

## Release Rule

No `0.5.0` release until G0 through G5 plus the Agent Quality Gate are green from current-head CI evidence.

No `1.0.0` release until the project also demonstrates repeated restart recovery, backup/restore, fault-injection recovery, compatibility canary stability, and decision-grade agent evals.