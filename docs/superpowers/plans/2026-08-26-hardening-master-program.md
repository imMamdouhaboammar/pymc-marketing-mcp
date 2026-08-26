# 2026-08-26 Hardening Master Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the production/runtime gaps discovered after G0/G1 hardening without duplicating the existing stabilization program, then resume capability work only after the service proves identity propagation, object isolation, recoverable compute, trustworthy CI evidence, and executable agent safety.

**Architecture:** Keep the existing statistical/domain architecture. Add a request-scoped identity boundary that propagates authenticated principals into every MCP tool/resource, enforce scope plus object ownership, introduce production repository/job abstractions behind `Application`, make CI the source of gate truth, and treat the dashboard and agent skills as consumers of the same verified contracts rather than parallel systems.

**Tech Stack:** Python 3.12-3.13, PyMC-Marketing 1.0.x within an explicitly tested range, PyMC 6, MCP Python SDK v2, Pydantic 2.12, SQLite local mode, PostgreSQL production metadata/jobs, GCS-compatible object storage, structlog/OpenTelemetry, GitHub Actions, React/Firebase dashboard only where it consumes backend-issued credentials.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Why this supplement exists

The 2026-08-23 stabilization plans remain authoritative for production readiness. This supplement records gaps found after later MCP/security commits and changes execution priority where needed.

It does **not** replace:

- `2026-08-23-security-mcp-hardening.md`
- `2026-08-23-jobs-storage-recovery.md`
- `2026-08-23-observability-ci-release.md`
- `2026-08-23-agent-skills-evals.md`

It adds concrete blockers that were not fully represented when those plans were written:

1. HTTP authentication is not yet proven to propagate the caller principal into tool execution.
2. MCP resources do not share the tool scope/ownership policy.
3. Resource ownership/tenant identity is not represented by the current metadata schema.
4. The dashboard creates and stores raw API secrets independently of the Python server's credential source.
5. `docs/PRODUCTION-READINESS.md` can lag current code because gate state is still human-maintained.
6. Long-running job design should remain transport-neutral and be ready for the MCP `io.modelcontextprotocol/tasks` extension when the Python SDK implements it.
7. Agent evals must be executable evidence, not committed `passed: true` assertions.
8. Upstream PyMC-Marketing/MCP compatibility must gate capability expansion.

## Global Constraints

- Preserve the mandatory diagnostics gate for decision-grade MMM operations.
- Never let remote HTTP fall back to the trusted stdio principal.
- Authorization must be enforced at execution time and on resources, not only at middleware ingress.
- A valid scope never grants access to another principal's object unless an explicit tenant/admin policy allows it.
- Never store raw API keys in Firestore, localStorage, logs, traces, or metadata tables after one-time issuance.
- Local stdio remains lightweight and may use SQLite/filesystem/local execution.
- Production state must survive API process replacement.
- Expensive statistical operations must not block the ASGI event loop.
- Release/gate status may only be green from executable evidence produced from the assessed commit.
- No new public statistical capability work until H0-H6 below are green.

## Hardening Gates

| Gate | Name | Definition |
|---|---|---|
| H0 | Runtime Truth | current-head evidence and CI-generated readiness status agree with code |
| H1 | Identity Propagation | HTTP auth principal reaches tool and resource execution with no trusted fallback |
| H2 | Object Isolation | all persisted datasets/models/scenarios/CLV/jobs/artifacts have owner/tenant semantics and cross-principal tests |
| H3 | Credential Control Plane | dashboard-issued credentials are backend-generated, verifier-only at rest, revocable, and used by the MCP server |
| H4 | Recoverable Compute | statistical jobs are durable, idempotent, cancellable, restart-safe, and transport-neutral |
| H5 | Agent Safety | skill routing/evals execute real traces and block unsafe tool sequences/claims |
| H6 | Upstream Compatibility | locked stack plus latest-allowed canary are tested before widening dependencies or adding capability |

## Authoritative Execution Order

### Wave A: Runtime truth before more implementation

Execute `2026-08-26-runtime-truth-ci-gates.md` Tasks 1-4.

Exit criteria:

- current HEAD baseline regenerated
- G3/H1 tests exist and fail for any unbridged HTTP principal path
- readiness documentation is generated or verified from machine-readable evidence
- PR CI exists for the hardening branch

### Wave B: Identity, authorization, resource isolation

Execute `2026-08-26-auth-context-resource-isolation.md` completely.

Exit criteria:

- remote HTTP can never use `stdio_context_provider()`
- tool scope tests run through a real HTTP MCP client
- MCP resources enforce scope + ownership
- persisted resource records include owner/tenant identity
- cross-principal access fails deterministically

### Wave C: Credential/control-plane repair

Execute `2026-08-26-dashboard-control-plane-security.md`.

Exit criteria:

- no raw API key is persisted in Firestore/localStorage
- backend owns key creation, verifier storage, revocation and audit
- dashboard consumes backend key-management API only
- server authentication reads the same credential repository

### Wave D: Durable compute boundary

Execute the existing `2026-08-23-jobs-storage-recovery.md` plus the compatibility amendment in `2026-08-26-jobs-mcp-task-boundary.md`.

Exit criteria:

- expensive operations return durable job handles
- job service is independent from MCP-specific task names
- API and worker processes can be separated
- restart/cancel/idempotency tests pass
- an MCP Tasks extension adapter can be added later without rewriting domain/job code

### Wave E: Operability and release truth

Return to `2026-08-26-runtime-truth-ci-gates.md`, then the existing `2026-08-23-observability-ci-release.md` and `2026-08-23-performance-resilience-capacity.md`.

Exit criteria:

- PR, nightly, security and release workflows run
- readiness checks dependencies instead of process-only health
- artifact/package/image identity ties to one commit
- H0 plus G4/G5 are evidence-backed

### Wave F: Agent execution safety

Execute `2026-08-26-agent-skill-eval-hardening.md`, consuming the existing agent plan rather than duplicating it.

Exit criteria:

- no committed pass values in eval fixtures
- router chooses minimal relevant skill set
- tool trace assertions prove decision-gate, auth and ownership behavior
- unsafe requests fail even if the final prose would otherwise sound plausible

### Wave G: Upstream compatibility and capability thaw

Execute `2026-08-26-upstream-compatibility-capability-gates.md`.

Exit criteria:

- production lock is reproducible
- latest-allowed dependency canary passes
- MCP SDK capability matrix is explicit
- capability proposals include upstream API evidence, statistical invariants and downgrade/rollback path

Only then may the feature freeze be lifted.

## Cross-Program Invariants

### Identity invariant

```text
HTTP credential
  -> authenticated Principal
  -> ExecutionContext
  -> scope policy
  -> object policy
  -> service/repository call
```

There must be no HTTP path where the caller becomes the local trusted principal.

### Object invariant

Every durable object must answer:

```text
Who owns it?
Which tenant contains it?
Which principal created it?
What immutable artifact/data fingerprint backs it?
Which authorization rule grants this caller access?
```

### Credential invariant

Raw API keys are displayed only at issuance. At rest, store a non-reversible verifier plus prefix/metadata. Revocation must take effect in the same credential store used by request authentication.

### Scientific invariant

A tool/skill/dashboard cannot promote an experimental or failed-diagnostics output into a decision-grade recommendation.

### Evidence invariant

Documentation, capability status, readiness gates and release notes derive from executable evidence from the exact assessed commit.

## Required Review Sequence Per Task

```text
Read current code and plan dependency
Write characterization/failing test
Run focused failing test
Implement smallest change
Run focused tests
Run relevant integration/statistical/security tests
Independent review
Update generated evidence/docs
Commit
```

Security changes require an explicit bypass review.

Statistical changes require a scientific-semantics review.

Persistence changes require crash/partial-write/restart review.

Agent changes require negative tool-trace evals.

## Program Stop Conditions

Stop and open a focused investigation if:

1. The MCP SDK cannot expose per-request principal context without bypassing supported APIs.
2. An ownership migration cannot preserve existing v0.4 data deterministically.
3. A remote request can invoke a protected tool/resource under the trusted stdio identity.
4. Credential revocation cannot be made atomic with authentication lookup.
5. Sampling cancellation requires unsafe thread termination rather than process isolation/cooperative cancellation.
6. The MCP Tasks extension requires a wire contract incompatible with the internal job abstraction.
7. An upstream PyMC-Marketing change alters decision semantics without a compatible statistical invariant.
8. Gate status can only be made green by editing documentation rather than producing evidence.

## Final Definition of Done

This hardening supplement is complete when:

- H0-H6 are green from current-head evidence
- G0-G5 and Agent Quality Gate remain green
- HTTP identity propagation is proven end-to-end
- cross-principal resource isolation is proven end-to-end
- dashboard credentials are backend-controlled and revocable
- long-running statistical work is recoverable and transport-neutral
- agent evals execute real tool traces
- dependency upgrades are canary-tested before release
- no public capability is described as stable without executable behavioral evidence
