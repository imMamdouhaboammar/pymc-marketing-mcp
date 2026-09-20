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

The project currently declares Python `>=3.12,<3.14`, PyMC-Marketing `>=1.1.0,<2` and MCP Python SDK `>=2,<3`

Exact versions for a verified release come from `uv.lock` plus machine-generated release evidence, not from a hand-maintained architecture statement

See `docs/API-COMPATIBILITY.md`

## Rust Interaction Engine

The `marketing_mcp_fast` Rust extension (`crates/marketing_mcp_fast/`) provides a
**Rust-backed MCP interaction fast path** for latency-sensitive infrastructure.

**Precise terminology**: This is a `Rust interaction engine` or `native admission layer`. It is
NOT a "Rust MCP Server" — the MCP protocol server is the official Python MCP SDK (FastMCP).

### Capability Evidence Table

| Capability | Location | Runtime caller | Status |
|---|---|---|---|
| Native request admission (size and JSON-RPC validation) | `engine.rs::admit_and_validate_request` | `NativeAdmissionMiddleware` on POST /mcp | **IMPLEMENTED_NOT_YET_BENCHMARKED** |
| `jsonrpc == "2.0"`, id, params and tools/call validation | `engine.rs` | Same middleware | **IMPLEMENTED_AND_VERIFIED** |
| Notification semantics (id absent only) | `engine.rs` | Same middleware | **IMPLEMENTED_AND_VERIFIED** |
| HTTP Range header parsing | `engine.rs::parse_range_header` | `http/artifacts.py` artifact download | **IMPLEMENTED_AND_VERIFIED** |
| Job admission token (interaction-level, not canonical job ID) | `engine.rs::admit_job_submission` | `mcp/tools/jobs.py` submit_fit_mmm_job | **IMPLEMENTED_AND_VERIFIED** |
| Truthful cancellation transition | `JobService` + native acknowledgment | `mcp/tools/jobs.py` cancel_job | **IMPLEMENTED_AND_VERIFIED** |
| LTTB transport representation | `sparklines.rs` | `DecisionService.response_curves` | **IMPLEMENTED_NOT_YET_BENCHMARKED** |
| Sparkline generation | `sparklines.rs` | response curves and dataset telemetry | **IMPLEMENTED_NOT_YET_BENCHMARKED** |
| Native JSON final-wire serialization | no supported FastMCP wire caller | none | **REMOVE_CLAIM** |
| Typed Rust/Python dispatch boundary | documentation only | none | **PLANNED** |
| CSV preflight validation | `csv_preflight.rs` | accelerator facade | **IMPLEMENTED_AND_VERIFIED** |
| Native invocation counters | `engine.rs` atomics | integration tests | **IMPLEMENTED_AND_VERIFIED** |
| Rust ON/OFF parity lane | explicit disable environment flag | native CI workflow | **IMPLEMENTED_NOT_YET_BENCHMARKED** |
| Artifact streaming, hashing and backpressure | Python generator | Python only | **PLANNED** |
| SIMD SHA-256 | no crate or production caller | none | **REMOVE_CLAIM** |
| "1 MB bounded Rust stream buffers" | Python 1 MiB reads only | none | **REMOVE_CLAIM** |
| End-to-end MCP benchmarks (p50/p95/p99) | admission benchmark only | none | **PLANNED** |
| Docker runtime activation | native library in image | Docker smoke workflow | **IMPLEMENTED_NOT_YET_BENCHMARKED** |

### Separation of Concerns

```text
Rust owns:
  - Latency-sensitive MCP interaction infrastructure
  - Request size enforcement and JSON-RPC framing validation
  - HTTP range header parsing
  - Job admission tokens (interaction-level)
  - Cancellation acknowledgment
  - LTTB transport visualization downsampling
  - CSV preflight byte-level inspection

Python/ArviZ owns (authoritative, never delegated to Rust):
  - PyMC / PyMC-Marketing statistical computation
  - MCMC R-hat, ESS, divergence diagnostics
  - Diagnostic gate decisions (pass/caution/block)
  - Budget allocation semantics
  - Model acceptance and rejection
  - Cross-validation, prior sensitivity, calibration
  - Posterior interpretation
```

### Experimental / Non-Authoritative

`fast_mcmc_diagnostics` and `fast_compute_split_rhat` exist in the Rust crate for
benchmarking and parity testing only. They are explicitly non-authoritative. Access them via
`marketing_mcp.accelerators.experimental.EXPERIMENTAL_*` to make the restriction visible.
Calling them from production decision paths is a correctness bug.
