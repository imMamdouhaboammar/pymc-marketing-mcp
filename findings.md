# Current Repository Findings: 2026-08-26

This file summarizes the current hardening review of PyMC Marketing MCP v0.4.0

The previous 2026-08-22 research snapshot described a much smaller repository with 17 MCP tools and early planned phases. That snapshot is superseded by the current codebase and remains available in Git history

## Executive assessment

The statistical/domain side of the repository is materially stronger than a prototype. Real PyMC-Marketing tests cover MMM fitting, multidimensional models, calibration, CLV, model comparison, flighting and decision invariants

The main risk is now a mismatch between implemented primitives and end-to-end production properties

The repository should be treated as advanced beta / release-candidate implementation until current-head evidence proves the complete production path

## P0 findings

### 1. Remote identity propagation is not proven through MCP execution

HTTP authentication middleware and tool scope checks both exist

However, `create_http_app()` currently creates the MCP server without a request-scoped context provider, while tool modules fall back to the trusted stdio context when no provider is supplied

Required evidence

```text
limited-scope HTTP token
  -> authenticated request
  -> real MCP session
  -> real tool call
  -> request Principal
  -> required scope allow/deny
```

This is H1 and blocks remote production security

### 2. MCP resources bypass the tool authorization pattern

Resource handlers currently read metadata/artifacts directly and do not receive request execution context

Remote production requires the same principal, scope and object/tenant authorization policy for resources such as model, dataset, diagnostics, lineage, plot and CLV resources

This is H2

### 3. Ownership helpers exist but lifecycle wiring is incomplete

The code has `attach_ownership`, `inherit_ownership` and dataset/model/job authorization helpers

The production property is stronger: every created/derived resource must receive ownership, every read/mutation must authorize it and legacy local records need an explicit remote migration policy

Primitive/helper tests do not prove that property

### 4. Dashboard API-key management is not a production credential authority

The current dashboard generates credentials in the browser and can persist raw secret material in Firestore/localStorage

The server authentication path is configured separately

Target

```text
backend generates raw key once
  -> stores verifier/hash only
  -> returns raw secret once
  -> revocation changes the verifier used by MCP auth
```

This is H3

### 5. Current asynchronous jobs are not production worker isolation

The repository now has SQLite job records, status/cancellation/idempotency primitives and stale-job recovery

Execution still uses an in-process `AsyncioJobExecutor`, while MMM fitting may run through the API process thread pool

A process/container crash can therefore stop active compute even though the job row survives

Target requires process/worker isolation, durable heartbeat/recovery and production metadata/artifact repositories

This is G2/H4

### 6. Release/operability gates were marked greener than the available evidence

The repository contains release-test files, logging/metrics/readiness foundations and a release-evidence collector

But current requirements also call for PR CI, nightly statistical CI, security/supply-chain CI, compatibility canary, release workflow, traces, alerts/runbooks and a generated evidence pack for the exact candidate commit

Those broader artifacts are not all present today

`docs/PRODUCTION-READINESS.md` now reflects the difference between implementation and release proof

### 7. Agent eval evidence is not yet fully executable

Agent behavior tests/skills exist, but committed eval fixtures still include pre-marked pass values and do not yet provide the complete runtime tool-trace evidence required by AQG/H5

### 8. Compatibility needs an admission policy before feature growth

The project is on PyMC-Marketing 1.x and has a broad lower-bound dependency declaration

Before feature thaw the repository needs a locked production lane, latest-allowed canary and capability-admission checklist so an upstream API change cannot silently alter decision semantics

This is H6

## Current strengths

- explicit capability registry checked against MCP discovery
- generated capability documentation
- thin/focused MCP tool modules
- real PyMC-Marketing statistical tests
- diagnostic decision state persisted on models
- scenario versus optimization separation
- dynamic flighting tests
- model-specific CLV paths
- model/dataset fingerprints and calibration lineage
- query-string credential rejection
- scope catalog and ownership primitives
- SQLite migrations and local job state
- liveness/readiness and observability foundations
- detailed stabilization/hardening plans with release gates

## Documentation issues found and corrected in the hardening branch

The audit found conflicting claims across README, readiness, architecture, security, deployment, statistical policy, verification and historical review documents

Examples included

- one document saying advanced beta while another claimed full M4/Enterprise readiness
- stale PyMC-Marketing 0.19/v0.2 architecture text
- a historical 17-tool verification matrix presented as current
- diagnostic R-hat policy documented more strictly than the code
- incremental ROAS omitted from the documented decision gate despite service enforcement
- single-instance SQLite/GCS-FUSE deployment described as production architecture
- historical v0.3 review presented as a current final review

The active documentation truth model is now `docs/README.md`

## Recommended execution order

1. H0 current-head truth/evidence baseline
2. H1 HTTP principal propagation
3. H2 tool/resource ownership isolation
4. H3 dashboard/server credential authority
5. G2/H4 production jobs/storage/recovery
6. G4/G5 observability and CI/release evidence
7. AQG/H5 executable agent evals
8. H6 upstream compatibility/capability admission
9. only then resume new public statistical capabilities

Full plan index: `docs/superpowers/plans/README.md`
