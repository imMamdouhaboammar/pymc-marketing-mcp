# Production Readiness Gates

This document is the human-readable release-status view for the current codebase

A gate is green only when machine-collected evidence for the exact commit being assessed proves every required property. The existence of a release test, a passing result from an older commit, or a hand-written status line is not sufficient evidence

See `docs/release-evidence/README.md` for the evidence contract and `docs/superpowers/plans/README.md` for the execution order

## Current status

Current maturity: **advanced beta / release-candidate implementation, not release-approved**

The 2026-08-26 core hardening commit implemented meaningful portions of G2 through G5, but the repository does not currently contain a machine-generated release-evidence record for the branch head, and several gate definitions are broader than the tests that currently exist

| Gate | Name | Current status | What is true today | What still blocks green |
|---|---|---|---|---|
| G0 | Baseline Truth | evidence pending | canonical version, capability inventory, tool-contract and docs-drift machinery exist | regenerate and execute current-head evidence after this documentation alignment |
| G1 | Scientific Correctness | strong implementation, evidence pending | real PyMC-Marketing statistical suites cover MMM, CLV, flighting, model comparison and decision invariants | current-head machine evidence must rerun the full statistical suite and record dependency identity |
| G2 | Service Recovery | partial | SQLite migrations, job records, idempotency primitives, cancellation state and stale-job recovery exist | production repository adapters, process/worker isolation, artifact durability, restart recovery with real statistical jobs, backup/restore and recovery evidence |
| G3 | Remote Security | partial | fail-closed security profiles, header-only credentials, scope policy, ownership helpers, request safety and secret redaction exist | prove HTTP principal propagation into real MCP tool calls, protect MCP resources with the same principal/policy, wire ownership through resource lifecycle, prove OAuth verifier runtime integration and cross-principal E2E denial |
| G4 | Operability | partial | structured logging, metrics foundations, liveness/readiness endpoints and local dependency checks exist | distributed traces, production dependency readiness, worker/job correlation, alert definitions, runbooks and operational evidence |
| G5 | Release Evidence | blocked | release-evidence collector and release identity helpers exist | PR CI, nightly statistical CI, security CI, compatibility canary, release workflow, clean wheel/container smoke and current-head generated evidence |
| AQG | Agent Quality Gate | partial | agent behavior tests and skill packages exist | remove pre-marked pass values, execute trace-based scenarios, run negative decision/security evals and record results in release evidence |

## 2026-08-26 hardening gates

The H-gates supplement the original G-gates. They do not replace them

| Gate | Purpose | Current status |
|---|---|---|
| H0 | Runtime truth and CI evidence | blocked until current-head CI/evidence is generated |
| H1 | Real HTTP principal reaches tool execution | not proven |
| H2 | Tools and MCP resources enforce object/tenant isolation | not proven end to end |
| H3 | Dashboard and server share one secure credential authority | not implemented |
| H4 | Statistical jobs are durable and transport-neutral with worker isolation | partial, current executor is in-process |
| H5 | Agent skills are routed and eval-backed by executable traces | partial |
| H6 | Upstream compatibility and capability admission gate feature growth | not yet enforced by CI |

## Gate definitions

### G0: Baseline Truth

Required properties

- package/runtime/documentation release identity agrees
- every public MCP tool/resource matches the generated capability inventory
- every public tool has a documented contract
- documentation drift checks pass
- release claims are backed by evidence from the commit being assessed

### G1: Scientific Correctness

Current code has strong coverage for

- channel-specific MMM configuration
- real model comparison semantics
- model-specific CLV workflows
- dynamic flighting with carryover and constraints
- continuity, saturation, conservation, reload, calibration-lineage and fingerprint invariants
- posterior summary dimensional correctness
- diagnostic gating before decision-grade outputs

The decision-policy thresholds are defined in `docs/DECISION-INTEGRITY.md` and implemented in `src/marketing_mcp/domain/diagnostics/engine.py`

### G2: Service Recovery

Green requires all of the following, not only a local job table

- expensive statistical work is represented by durable job state
- CPU-heavy sampling does not depend on the request event loop or API process lifetime
- metadata and artifacts survive process/instance replacement
- job state, cancellation, failure and result references survive restart
- idempotency detects semantic conflicts as well as duplicates
- production metadata and artifact adapters pass common contracts
- artifact integrity and orphan reconciliation are tested
- backup and restore are tested

### G3: Remote Security

Green requires

- insecure production HTTP refuses startup
- query-string credentials are rejected
- authenticated HTTP identity becomes the `Principal` used by the actual MCP invocation
- scopes are enforced by tool group
- object/tenant ownership is enforced on tools and MCP resources
- secrets are absent from logs, errors and evidence
- OAuth/API-key verification is wired into the production runtime, not only unit-tested in isolation
- cross-principal access is rejected through a real remote MCP session

### G4: Operability

Green requires

- request, tool, job and storage operations can be correlated
- logs are structured and redacted
- metrics expose request/job outcomes without high-cardinality labels
- traces connect MCP requests to later job execution
- liveness and readiness have distinct semantics
- production readiness checks required database, job and artifact dependencies
- operator alerts and runbooks cover the main failure families

### G5: Release Evidence

Green requires

- required PR workflow is present and green
- statistical workflow is present and green for the release candidate
- security/supply-chain checks run
- upstream compatibility canary is green or explicitly waived with evidence
- wheel and container are built from the same commit
- clean-install and container smoke tests pass
- hashes/digests and dependency versions are captured
- release evidence is generated by CI for the exact release commit

### Agent Quality Gate

Green requires

- every skill capability maps to the current capability/tool contract
- no committed eval fixture asserts its own success with a pre-marked pass value
- eval scenarios execute and capture tool traces
- negative scenarios protect diagnostics, causal claims, warnings and tenant/security boundaries
- final results are included in the release evidence pack

## Evidence currently available

`docs/release-evidence/v0.4-current-head.md` is a historical pre-hardening baseline and does not establish the status of later commits

Until a generated `<current-sha>.json` and matching summary exist and all required workflows have run, the current branch must not be described as production-ready, enterprise-ready, M4-complete or release-approved

## Release rules

No future minor release until G0 through G5, H0 through H6 and AQG are green from current-head CI evidence

No future major release until the M5 Decision-Grade requirements in `docs/superpowers/plans/2026-08-23-decision-governance-audit.md` are also proven, including immutable decision records, auditability, recovery and governance evidence
