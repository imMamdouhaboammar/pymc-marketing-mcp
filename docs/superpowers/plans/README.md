# Production Stabilization and Hardening Plan Index

This directory coordinates the move from the current v0.4.x advanced-beta/release-candidate implementation to a release-approved public beta and then production GA

Plans describe target work. They are not evidence that the work is complete

## Current audited baseline

Latest launch-closure audit baseline: `1c7fed0af32f9162d840f292a40a557b412978f9`

Material progress already implemented:

- request-scoped HTTP identity propagation into MCP execution
- tool and MCP resource scope/tenant authorization
- verifier-only API-key credential authority with one-time secret issuance
- 39 capability registry with generated documentation
- local machine evidence showing 446 non-statistical tests passing on a near-current hardening commit
- durable job records, idempotency primitives, stale-job recovery, and a process-worker abstraction
- CI, security, statistical, upstream-canary, and release workflow definitions
- readiness, structured logging, metrics, and trace foundations

The current implementation is still not release-approved because launch proof and several production boundaries remain incomplete

Current launch blockers discovered in the latest audit:

- current-head GitHub Actions jobs fail before any steps execute
- standalone `marketing-mcp-worker` starts without registering production statistical handlers
- `submit_fit_mmm_job` still defaults to API-process execution rather than a durable external-worker path
- production persistence is still SQLite plus local artifact files
- production bearer identity is not yet wired through the existing external issuer/JWKS verifier
- dashboard identity assumptions need alignment with the production control-plane verifier
- capability contract drift exists around `get_incremental_roas` decision gating
- readiness reports the job executor healthy without proving an external worker exists
- release workflow does not yet prove same-SHA package and container identity plus provenance
- `main` is not protected by required status checks

## 2026-08-26 launch-closure amendment

This amendment is now the shortest path to launch. It supersedes stale assumptions in earlier plans where the implementation has already advanced, while preserving earlier plans for unfinished deep-production work

### Master

- `2026-08-26-launch-closure-master.md`

Defines launch tiers, dependency order, feature freeze, public-beta criteria, GA criteria, and the final GO/NO-GO model

### P0 public-beta closure

1. `2026-08-26-ci-release-pipeline-recovery.md`
   - recover zero-step GitHub Actions failures
   - pin release-critical actions
   - make core CI deterministic
   - correct statistical matrix fan-out
   - harden security/SBOM scanning
   - bind release evidence to package and container identity
   - require stable checks on `main`

2. `2026-08-26-capability-contract-truth-hardening.md`
   - fix iROAS decision-gate drift
   - bind registry to real MCP discovery
   - make stable/experimental status evidence-driven
   - centralize decision capability policy
   - derive readiness from exact-commit evidence
   - bind agent routing to capability truth

3. `2026-08-26-worker-durable-compute-closure.md`
   - register real worker handlers
   - make worker CLI functional
   - separate production submission from execution
   - enforce semantic idempotency
   - add atomic claims/cancellation/recovery
   - make readiness verify worker heartbeat
   - keep async capability maturity honest until proven

4. `2026-08-26-final-launch-gates.md`
   - define launch evidence manifest
   - encode beta and GA machine gates
   - smoke the exact candidate container
   - define rollback/outage runbooks
   - enforce release governance
   - generate deterministic GO/NO-GO

### P1 production-GA closure

5. `2026-08-26-production-persistence-hardening.md`
   - persistence interfaces
   - external SQL metadata
   - object artifact storage
   - shared job/credential repositories
   - migration, backup, restore, reconciliation
   - provider-aware readiness

6. `2026-08-26-production-auth-dashboard-identity.md`
   - wire external issuer/JWKS verifier into active auth runtime
   - normalize issuer claims into `Principal`
   - remove contradictory query-token guidance
   - align dashboard control-plane identity
   - add production issuer MCP E2E tests
   - prevent object/tenant enumeration
   - enforce startup security posture

## Launch tiers

### Local stdio beta

May launch after package/local verification and stable-capability evidence are green

### Authenticated remote public beta

May launch only after the P0 launch-closure plans are green from one exact candidate commit

A beta may explicitly retain single-instance SQLite/local artifacts only when release documentation states the limitation and horizontal scaling is not presented as supported

Async job capability may remain in beta only when it is either external-worker proven or clearly marked experimental/not advertised as durable

### Production GA

Requires the P1 production plans plus G0-G5, H0-H6, and AQG exact-commit evidence

Production GA may not waive external persistence, API/worker separation, production identity verification, backup/restore, operability evidence, or artifact provenance

## Previous 2026-08-26 hardening plans

These remain useful for deeper requirements and implementation history

- `2026-08-26-hardening-master-program.md`
- `2026-08-26-runtime-truth-ci-gates.md`
- `2026-08-26-auth-context-resource-isolation.md`
- `2026-08-26-dashboard-control-plane-security.md`
- `2026-08-26-jobs-mcp-task-boundary.md`
- `2026-08-26-agent-skill-eval-hardening.md`
- `2026-08-26-upstream-compatibility-capability-gates.md`

Several of their original gaps have now been implemented, especially request-scoped identity, MCP resource authorization, verifier-backed credentials, workflow definitions, and H1/H2/H3 test coverage. Their remaining requirements should be interpreted against the latest code rather than replayed blindly

## Original 2026-08-23 plans

These remain authoritative for work not explicitly superseded by later plans

- `2026-08-23-production-grade-master-program.md`
- `2026-08-23-production-truth-release-discipline.md`
- `2026-08-23-scientific-contract-hardening.md`
- `2026-08-23-security-mcp-hardening.md`
- `2026-08-23-jobs-storage-recovery.md`
- `2026-08-23-performance-resilience-capacity.md`
- `2026-08-23-observability-ci-release.md`
- `2026-08-23-agent-skills-evals.md`
- `2026-08-23-decision-governance-audit.md`

## Execution order

```text
1. CI/release pipeline recovery
2. Capability/contract truth
3. Durable worker closure
4. Remote beta E2E and exact-candidate launch gate
5. Public beta release
6. Production persistence
7. Production issuer/dashboard identity
8. Operability + backup/restore + provenance closure
9. Production GA gate
10. Decision-grade v1.0 governance
```

P0 plans may overlap only when they do not depend on unfinished interfaces. Do not mark a plan complete because code for one sub-property exists

Examples:

- a worker class existing is not durable-compute evidence until the production CLI registers handlers and a job survives API shutdown
- a workflow file existing is not release evidence until GitHub actually executes it on the candidate SHA
- a JWKS verifier existing is not production identity evidence until the active HTTP auth path uses it
- an ownership helper existing is not isolation evidence until real MCP tool/resource sessions reject foreign tenants
- a capability being documented as stable is not sufficient until its evidence tests are live and match runtime semantics

## Review rule

Every material implementation task follows:

```text
Inspect current state
Select focused skills/workflows
Write failing test
Run the failing test
Implement minimum correct change
Run focused tests
Independent review
Run wider verification
Update capability/docs/evidence
Commit
```

Additional review focus:

- statistical changes: scientific semantics and real-library tests
- security changes: auth bypass, cross-principal/resource access, enumeration, secret exposure
- persistence/jobs: crash/restart, atomic claim, cancellation, partial write, backup/restore, artifact integrity
- agent changes: tool traces, forbidden calls, warning preservation, registry drift
- release changes: exact SHA, artifact identity, dependency versions, SBOM/provenance, rollback

## Release rule

No public remote beta until all mandatory P0 launch gates are green from exact-candidate machine evidence

No production GA until G0 through G5, H0 through H6, AQG, external persistence, durable worker isolation, production identity, backup/restore, operability, and artifact provenance are green from the exact GA commit

No v1.0.0 until the M5 Decision-Grade gate is also green
