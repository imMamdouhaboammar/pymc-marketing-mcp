# Architecture

## Architectural principle

The MCP boundary stays thin. Protocol handlers translate controlled requests into application-service calls. Statistical computation belongs to PyMC-Marketing. This project owns contracts, validation, diagnostic and decision policy, persistence, authorization boundaries, job orchestration, output shaping and provenance

## Current v0.4.0 runtime

```text
MCP client
  -> stdio or Streamable HTTP
  -> MCP tools/resources
  -> Application services
     -> DatasetService
     -> ModelingService
     -> DiagnosticsService
     -> DecisionService
     -> PlottingService
     -> CLVService
     -> JobService
  -> PyMCMarketingAdapter
  -> PyMC-Marketing + PyMC + ArviZ

Current persistence
  -> SQLiteMetadataStore
  -> SQLiteJobRepository on the same SQLite connection
  -> LocalArtifactStore / NetCDF artifacts

Current job execution
  -> AsyncioJobExecutor inside the service process
  -> fit job handler may delegate blocking fit work to the process thread pool
```

The current architecture is appropriate for local development and controlled single-process use. It is not yet the target production topology

## MCP boundary

`src/marketing_mcp/mcp/server.py` is composition-only and registers focused tool modules for datasets, MMM, decisions, CLV, model selection and jobs, plus MCP resources

Tool modules accept an optional execution-context provider and enforce scope policy. Trusted stdio uses a local principal with all known scopes

Remote HTTP still has an open integration requirement: the authenticated request identity must be proven to become the same principal used by every MCP tool invocation. MCP resources also need request-scoped authorization rather than direct metadata reads

## Application and statistical domains

- Dataset service: file registration, fingerprinting, inspection, MMM validation and panel checks
- Modeling service: controlled model configuration, fit/calibration lifecycle, artifact persistence and package provenance
- Diagnostics service: sampler diagnostics, posterior-predictive checks, cross-validation and prior sensitivity
- Decision service: contributions, incrementality, response curves, scenarios, budget allocation and flighting
- CLV service: purchase/churn, value and lifetime-value model workflows
- Plotting service: posterior and model artifacts
- PyMC adapter: official PyMC-Marketing computation boundary
- Security domain: principals, scopes, ownership helpers, OAuth verifier and request safety
- Jobs domain: job records, repository, state transitions, cancellation and current in-process execution

## Diagnostic and decision flow

```text
Dataset
  -> validate
  -> fit model
  -> diagnose
  -> descriptive evidence
  -> decision gate
       -> rejected: block decision-grade tools
       -> approved_with_caution: allow with warnings
       -> approved: allow
  -> scenario / incremental ROAS / optimization
  -> evidence + uncertainty + provenance
```

See `docs/DECISION-INTEGRITY.md` for the exact policy

## Budget data flow

```text
Historical model inputs
  -> recent allocation by channel or channel x dimensions
  -> requested counterfactual OR constrained optimizer
  -> typed xarray allocation
  -> PyMC-Marketing response path
  -> posterior comparison
  -> compact evidence + warnings + provenance
```

For multidimensional models the allocation domain verifies exact cell coverage before passing the DataArray to PyMC-Marketing

## Current persistence limits

SQLite and local artifacts are concrete runtime dependencies in `Application` today

Migrations now exist and the jobs table persists job state, but production-grade durability is not established by that alone. The current architecture does not yet provide the planned PostgreSQL metadata/job adapters, production object-store adapter, immutable artifact references, reconciliation or backup/restore workflow

## Current job limits

The current job API exposes `submit_fit_mmm_job`, `get_job_status`, `cancel_job` and `list_jobs`

Those are project-specific compatibility tools, not an implementation of the MCP Tasks extension

The current executor uses in-process asyncio tasks. Therefore an API-process crash can terminate active compute even though job records are persisted. The target design keeps `JobService` transport-neutral and moves CPU-heavy statistical execution to isolated workers/processes with durable heartbeats and recovery

## Target production topology

```text
Remote MCP clients
  -> authenticated Streamable HTTP API
  -> Principal + tenant context
  -> scope + object authorization
  -> application services
       -> read/control operations
       -> durable JobService submissions

Control/API service
  -> production metadata repository
  -> production artifact store
  -> metrics/logs/traces

Worker service/process pool
  -> durable job claim/heartbeat
  -> PyMC-Marketing sampling
  -> immutable artifact write
  -> transactional result/job update

Production storage
  -> PostgreSQL or equivalent durable metadata/jobs
  -> object storage for datasets/models/plots
```

The public MCP contract should not depend on the chosen queue/database/cloud provider

## Compatibility

The project currently declares Python `>=3.12,<3.14`, PyMC-Marketing `>=1.0.0` and MCP Python SDK `>=2,<3`

Exact versions for a verified release come from `uv.lock` plus machine-generated release evidence, not from a hand-maintained architecture statement

See `docs/API-COMPATIBILITY.md`

## Target architectural invariants

Before production release the architecture must prove

- one authenticated principal flows through transport, tools, resources and jobs
- object ownership and tenant isolation are enforced on every resource path
- request handling is separated from long-running statistical compute
- metadata/artifacts survive instance replacement
- model artifacts are immutable and checksum-addressed
- jobs are idempotent, cancellable and recoverable
- observability correlates request, tool, job, model and artifact operations
- the MCP capability surface remains generated/tested against actual discovery
- future MCP Tasks support is an adapter over the existing job domain rather than a second job model
