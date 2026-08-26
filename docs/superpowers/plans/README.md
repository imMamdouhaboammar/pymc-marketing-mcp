# Production Stabilization and Hardening Plan Index

This directory contains the execution program for moving PyMC Marketing MCP from the current v0.4.x advanced-beta state to a production-grade release candidate, then to a decision-grade v1.0 release.

## 2026-08-26 Hardening Amendment

A current-code review after the first G0/G1 and MCP security work found several runtime integration gaps that must be resolved before continuing the original execution order:

- HTTP authentication is not yet proven to propagate the real caller principal into tool execution
- MCP resources do not yet share tool scope/ownership enforcement
- current persisted records do not carry enough owner/tenant identity to prove cross-principal isolation
- the dashboard API-key prototype persists raw secrets independently of server authentication
- readiness status can lag code because status text is not fully generated from CI evidence
- long-running jobs need a transport-neutral boundary that can later adapt to the MCP Tasks extension without a rewrite
- agent eval fixtures still contain pre-marked pass evidence
- upstream compatibility must gate future statistical capability expansion

The amendment is coordinated by:

1. `2026-08-26-hardening-master-program.md`
   - H0-H6 gates, priority changes, cross-program invariants and freeze/thaw rule

2. `2026-08-26-runtime-truth-ci-gates.md` Tasks 1-4
   - current-head baseline, machine-derived readiness, typing, bounded PR CI
   - start here before more hardening implementation

3. `2026-08-26-auth-context-resource-isolation.md`
   - HTTP principal propagation, scope + ownership authorization, resource protection, ownership migration
   - exit: G3/H1/H2 evidence

4. `2026-08-26-dashboard-control-plane-security.md`
   - backend-issued API keys, verifier-only storage, revocation, credential audit, removal of Firestore/localStorage secret authority
   - exit: H3

5. Existing `2026-08-23-jobs-storage-recovery.md` plus `2026-08-26-jobs-mcp-task-boundary.md`
   - durable jobs/storage remain governed by the original plan
   - amendment keeps the job domain transport-neutral and defines current compatibility tools/future Tasks extension adapter
   - exit: G2/H4

6. Finish `2026-08-26-runtime-truth-ci-gates.md`, then execute existing resilience/observability plans
   - CI, canary, release evidence, readiness, API/worker operability
   - exit: H0/G4/G5

7. Existing `2026-08-23-agent-skills-evals.md` plus `2026-08-26-agent-skill-eval-hardening.md`
   - executable traces, negative decision/security evals, measurable agent quality
   - exit: AQG/H5

8. `2026-08-26-upstream-compatibility-capability-gates.md`
   - dependency policy, canary, capability admission, freeze/thaw enforcement
   - exit: H6

Only after H0-H6 and the original release gates are green may new public statistical capability work resume.

## Original Production Stabilization Execution Order

The original plans remain authoritative for work not explicitly amended above.

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
   - execute the v0.5 release-candidate evidence pack and production readiness review

10. `2026-08-23-decision-governance-audit.md`
   - append-only audit, decision records, model lifecycle, champion/challenger, freshness, sensitivity, retention
   - target: M5 Decision-Grade gate for v1.0

## Dependency Rule

A plan may begin early only when its interfaces do not depend on an unfinished prior plan. It may not be marked complete until all upstream interfaces it consumes are green.

Examples:

- CI scaffolding can begin before Postgres is complete, but G5 cannot be green until the Postgres/recovery suites are part of CI
- Skill text cleanup can begin early, but stable capability claims cannot be finalized until G1 is green
- Observability wrappers can begin after MCP/job interfaces stabilize, but production SLO evidence depends on resilience/capacity tests
- Decision-governance schema design can start before v0.5, but M5 implementation should consume the stable production persistence, security, and audit interfaces rather than invent parallel ones
- Dashboard credential work must not invent a second identity store; it consumes the principal/tenant and credential repository contracts from the hardening plans
- Future MCP Tasks support must adapt the internal JobService; it must not replace or fork the job state model

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

For security changes, independent review must include authorization bypass, cross-principal access and secret exposure cases.

For persistence changes, independent review must include crash/restart and partial-write cases.

For decision-governance changes, independent review must verify provenance immutability and historical reproducibility.

For agent changes, independent review must inspect tool traces and negative safety cases rather than prose alone.

## Release Rule

No `0.5.0` release until G0 through G5, H0 through H6, and the Agent Quality Gate are green from current-head CI evidence.

No `1.0.0` release until the project also demonstrates repeated restart recovery, backup/restore, fault-injection recovery, compatibility canary stability, decision-grade agent evals, append-only audit evidence, immutable decision records, and the M5 Decision-Grade gate.
