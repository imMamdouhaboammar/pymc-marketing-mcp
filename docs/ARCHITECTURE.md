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
     -> CredentialService
  -> PyMCMarketingAdapter
  -> PyMC-Marketing + PyMC + ArviZ

Persistence
  -> SQLiteMetadataStore
  -> SQLiteJobRepository
  -> SQLiteCredentialRepository
  -> LocalArtifactStore / NetCDF artifacts

Job execution & Worker separation
  -> AsyncioJobExecutor (in-process local execution)
  -> ProcessJobWorker / marketing-mcp-worker CLI (process-isolated worker loop)
```

## MCP boundary and request-scoped identity

`src/marketing_mcp/mcp/server.py` is composition-only and registers focused tool modules for datasets, MMM, decisions, CLV, model selection and jobs, plus MCP resources.

For Streamable HTTP transport:
- `MCPAuthMiddleware` converts authenticated headers (Bearer JWT / API-key) into an immutable `Principal` and binds it to `_current_execution_context` (`ContextVar[ExecutionContext]`) for the lifetime of the request.
- `RequestScopedContextProvider` supplies this context to all tool and resource invocations, strictly failing closed (`AUTH_REQUIRED`) on unauthenticated requests.
- `AuthorizationService` enforces scope policies and tenant/object isolation across all tools and MCP resources (`marketing://models/{model_id}`, `marketing://datasets/{dataset_id}`, diagnostics, lineage, plots, CLV).
- Trusted stdio uses `stdio_context_provider()` which yields a local principal with all known scopes.

## Application and statistical domains

- Dataset service: file registration, fingerprinting, inspection, MMM validation and panel checks
- Modeling service: controlled model configuration, fit/calibration lifecycle, artifact persistence and package provenance
- Diagnostics service: sampler diagnostics, posterior-predictive checks, cross-validation and prior sensitivity
- Decision service: contributions, incrementality, response curves, scenarios, budget allocation and flighting
- CLV service: purchase/churn, value and lifetime-value model workflows
- Plotting service: posterior and model artifacts
- PyMC adapter: official PyMC-Marketing computation boundary
- Credential service: backend API key generation (256-bit entropy), verifier-only database storage, constant-time verification, and immediate revocation
- Security domain: principals, scopes, authorization service, OAuth verifiers, request safety, and audit logging
- Jobs domain: job records, repository, state transitions, canonical semantic idempotency hashing, cancellation, and process worker isolation

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

## Scientific Skill knowledge surface

The canonical procedural guidance lives in validated `.agents/skills/*` packages. The MCP server bundles the same manifests and `SKILL.md` content at build time and exposes it lazily through standard resources plus the compact `get_skill_guidance` fallback tool. This keeps procedural scientific guidance distinct from tool schemas and keeps statistical computation in application/PyMC-Marketing code.

The static catalog, selected Skill resources, manifests, tool/workflow/gate maps, shared scientific references, deterministic content hashes, and private list-cache hints are described in generated `docs/SCIENTIFIC-SKILLS.md`. No non-standard `skills/list` RPC is advertised. MCP prompts are intentionally omitted because resources plus the model-callable router provide the smaller cross-host interoperability surface without duplicating workflow text.

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

## Persistence and durability

Metadata, job records, and credential verifiers are managed through thread-safe SQLite stores (`SQLiteMetadataStore`, `SQLiteJobRepository`, `SQLiteCredentialRepository`).

Crash recovery automatically marks interrupted running jobs as failed on server restart (`recover_stale_running_jobs()`).

## Job execution and MCP task boundary

The job API exposes compatibility tools (`submit_fit_mmm_job`, `get_job_status`, `cancel_job`, `list_jobs`).

`UnsupportedTasksExtensionAdapter` ensures the server does not falsely advertise unsupported MCP Tasks extension capabilities, maintaining a clean adapter boundary for future protocol upgrades without altering internal job models.

Compute can be run either via in-process async tasks or via the process-isolated `marketing-mcp-worker` CLI.

## Observability

- Structured logging with single-line JSON formatting and automatic secret redaction (`StructuredJSONFormatter`).
- Low-cardinality Prometheus-compatible metric counters, histograms, and gauges (`MetricsCollector`).
- Distributed tracing context propagation with `trace_span`, `current_trace_id`, and `current_span_id`.

## Compatibility

The project currently declares Python `>=3.12,<3.14`, PyMC-Marketing `>=1.0.0` and MCP Python SDK `>=2,<3`

Exact versions for a verified release come from `uv.lock` plus machine-generated release evidence, not from a hand-maintained architecture statement

See `docs/API-COMPATIBILITY.md`
