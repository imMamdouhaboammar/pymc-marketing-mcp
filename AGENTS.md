# pymc-marketing-mcp Agent Guide

Decision-safe MCP interface over PyMC-Marketing for Bayesian marketing science

> 🚨 **UNBREAKABLE OPERATIONAL INVARIANT: SOLE ACTIVE REPOSITORY LAW**
> 
> **THIS IS THE ONLY ACTIVE REPOSITORY LOCALLY AND REMOTELY ACROSS THE PROJECT:**
> 👉 **`https://github.com/imMamdouhaboammar/pymc-marketing-mcp`**
> 
> - Every git commit, PR, and remote push MUST be executed within this repository.
> - Pushing to any other repository (such as `pymc-marketing-platform`) is strictly forbidden.
> - Always verify `git remote -v` points to `imMamdouhaboammar/pymc-marketing-mcp.git`.

Supported runtime: Python `>=3.12,<3.14` (3.12 and 3.13). The Ruff `py311` target is a lint/parser compatibility setting, not the declared runtime support floor

## Read before changing code

1. `docs/README.md` for documentation truth hierarchy
2. `docs/PRODUCTION-READINESS.md` for current status and blockers
3. `docs/CAPABILITIES.md` and `docs/TOOL-CONTRACTS.md` for the public MCP surface
4. `docs/DECISION-INTEGRITY.md` for decision-gate behavior
5. `docs/superpowers/plans/README.md` for the active stabilization/hardening execution order

Do not infer that a planned task, existing test file or historical review means a production property is already complete

## Commands

```bash
uv run pytest -m "not statistical" -v
uv run pytest -m statistical -v
uv run pytest -v
uv run ruff check src tests scripts
uv run python scripts/generate_capability_inventory.py --check
uv run python scripts/check_docs_drift.py
uv build
```

Bare `uv run pytest` includes the real statistical suite. Use `-m "not statistical"` for a bounded development loop

## Engineering workflow

Material work follows

```text
Inspect current source + evidence
  -> select focused skills/workflows
  -> write failing test
  -> implement the smallest correct change
  -> run focused tests
  -> independent review
  -> run wider verification
  -> update capability/docs/evidence
  -> commit
```

For multi-step work, use the repository Superpowers planning/TDD workflow defined by the active plans. Do not implement directly from an old plan without checking current source first

## Focused skills

Use only the skills relevant to the change rather than loading every available skill

| Change | Focus |
|---|---|
| Tests | Python testing / pytest coverage patterns |
| Service/repository design | Python design patterns + Superpowers TDD |
| MCP tool/resource changes | MCP server patterns + capability contract review |
| Docker/deployment | Docker patterns + production-readiness requirements |
| pandas/numpy/xarray performance | Python performance patterns + statistical invariants |
| Statistical semantics | PyMC-Marketing source/API review + real statistical tests |
| Security boundary | scope/ownership/request-safety review + negative authorization tests |
| Agent skill/eval changes | capability routing + tool-trace negative evals |

Skill/router advice never overrides executable repository contracts or release gates

## Public contract rules

- Public capability names/status live in `src/marketing_mcp/capabilities.py`
- Regenerate `docs/CAPABILITIES.md` whenever the registry changes
- Every public tool must remain documented in `docs/TOOL-CONTRACTS.md`
- Every decision-gated capability must match actual service enforcement and `docs/DECISION-INTEGRITY.md`
- Deprecated capabilities remain explicit until removal is a deliberate compatibility change
- Experimental capabilities must not be described as verified/stable without executable evidence

## Statistical rules

- Model-dependent quantities come from PyMC-Marketing/PyMC/ArviZ, never an LLM calculation
- Release-critical statistical behavior requires real-library tests
- Rejected models block decision-grade operations
- Warnings and extrapolation caveats remain visible
- Causal certainty must not be inferred from diagnostic approval
- Changing diagnostic thresholds is a statistical/decision-policy change, not a copy edit

## Security rules

- Remote clients are untrusted
- Do not add arbitrary code, shell, SQL or unsafe deserialization surfaces
- Do not accept credentials in query strings
- Never log raw credentials or raw customer/dataset rows
- New remote tools/resources must use the authenticated request principal, required scope and object/tenant authorization
- Trusted stdio behavior must not accidentally become the fallback identity for protected remote requests
- Security changes require bypass, cross-tenant and secret-exposure negative tests

## Jobs and persistence rules

- Current local jobs use SQLite + in-process async execution
- Do not call this production worker durability until process/worker isolation and restart evidence exist
- Keep JobService transport-neutral so future MCP Tasks support can be an adapter rather than a second state model
- Persistence changes require restart, partial-write and integrity tests

## Documentation truth rules

Documentation is part of the release contract

When changing versions, tools, transforms, transports, decision gates, security boundaries, persistence behavior or deployment topology, update the relevant current-state docs in the same change

Historical docs must say `historical` or clearly name their historical release scope

No document may mark G0-G5, H0-H6 or AQG green from assertion alone. Current-head machine evidence is required

## Cloud Run & Remote MCP Deployment Architecture

- **Transport**: Streamable HTTP (`MARKETING_MCP_TRANSPORT=streamable-http`) on port `8080`.
- **Compute Sizing**: 4 vCPUs, 8GiB RAM, `--no-cpu-throttling`, 1800s timeout to accommodate PyTensor C++/BLAS JIT compilation and MCMC multi-chain sampling.
- **Persistent Storage**: Google Cloud Storage (GCS) FUSE volume mounted at `/var/lib/marketing-mcp` for durable storage of inbox datasets and posterior NetCDF traces across container lifecycles.
- **Fail-Closed Default**: Public binding (`0.0.0.0`) requires authentication unless explicitly overridden by `MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true` for public beta deployments.

## Public Beta & FastMCP Execution Context Rules

- When `AUTH_ENABLED=false` and `MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true`, the server defaults its context provider to `stdio_context_provider`.
- FastMCP's streamable HTTP transport executes tools asynchronously in background coroutine pools where ASGI request context is decoupled. The ambient `stdio_context_provider` ensures all tools execute with valid scopes (`all_scopes()`) and default tenant ownership without dropping context.

## Storage Resiliency & Cloud Storage FUSE Invariants

- Cloud Storage FUSE mounts emulate POSIX filesystems without native inode hardlinks.
- `LocalArtifactStore` must never assume `os.link` is supported. If `os.link` fails with `OSError` (Errno 38 `ENOSYS`), it must gracefully fall back to atomic rename (`os.replace` / `shutil.move`).
- Mode flag changes (`chmod`) must tolerate filesystem-level `OSError` without aborting dataset or artifact operations.
- Materialization context managers must write raw payload bytes to temporary disk paths before yielding to native C libraries (NetCDF4 / HDF5).
- Multi-gigabyte artifacts (up to 2GB) must be streamed and hashed in 1MB chunks using `read_chunks` and `put_stream`. Never use `read_bytes` for traces or large datasets.
- Use `materialize()` with `symlink_to` rather than copying files into `/tmp`, preventing RAM exhaustion on Cloud Run's in-memory `tmpfs`.
- Resumable downloads are served via `GET /artifacts/{namespace}/{digest}/download` with HTTP Range (`206 Partial Content`) support.

## Fast Deploy Workflow & Credential Hygiene

Deploy to Google Cloud Run with one command using dynamic placeholders and automatic GCP project detection:

```bash
# Public beta mode (unauthenticated, ready for all AI clients)
./scripts/fast_deploy.sh beta

# Secure production mode (with auto-generated or custom API key)
./scripts/fast_deploy.sh secure
```

**Credential & Configuration Hygiene**:
- **Zero Hardcoded Secrets**: Never commit `.env` files, API keys, service account JSON files, or personal emails to git.
- **Dynamic Placeholders**: Scripts must always resolve configuration dynamically via `${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}` and `${GCS_BUCKET_NAME:-${PROJECT_ID}-pymc-mcp-artifacts}`.
- Automated 7-day TTL lifecycle policies are applied to GCS persistence buckets for temporary files.

The script automatically:
1. Validates `gcloud` authentication and project context.
2. Enables required Google Cloud APIs (`run`, `artifactregistry`, `cloudbuild`, `storage`).
3. Provisions the Artifact Registry repository and Cloud Storage persistence bucket.
4. Builds the container image via Google Cloud Build.
5. Deploys to Cloud Run with GCS FUSE volume mount and optimal compute flags.
6. Prints ready-to-copy client configuration snippets for Claude Desktop, Cursor, Windsurf, OpenCode, and Claude Code CLI.

## Resilience, Checkpoints & Sandbox Tools

The following resilient tools are exposed to prevent MCP connection dropouts and simplify sandbox export:
- `poll_job_progress(job_id, timeout_seconds=5)`: Non-blocking heartbeat polling across MCMC sub-stages.
- `recover_execution_state(job_id)`: Inspects recorded checkpoints after container restarts.
- `resume_job(job_id)`: Resumes execution of failed/interrupted jobs from the latest valid checkpoint.
- `export_artifact_to_sandbox(digest, namespace, client_sandbox_path)`: Provides direct download URLs, resumable `curl` commands, SHA256 checksum verification, and Python load scripts.
- `cleanup_server_storage(max_age_hours=24)`: Purges `/tmp` scratch directories, expired delivered artifacts, and orphan blobs.

## Native Rust Acceleration Engine (`marketing_mcp_fast`)

To optimize latency and eliminate timeouts for conversational AI clients (Claude, Cursor, ChatGPT):
- **C-Extension Module**: Compiled Rust crate `crates/marketing_mcp_fast` exposing native PyO3 functions linked to `src/marketing_mcp_fast.so`.
- **Pillar 1 (SIMD CSV Preflight)**: Sniffs delimiters, counts rows, detects nulls, and validates non-negative spend in Rust before touching pandas. Benchmarked at **~2,800x speedup** (3.7s to 1.31ms on a 3,000-row x 10-col CSV).
- **Pillar 2 (MCMC Diagnostics Gatekeeper)**: Evaluates Gelman-Rubin split $\hat{R}$ and Bulk-ESS across parameters in **0.10ms**, rejecting unconverged models before triggering heavy simulations.
- **Pillar 3 (Curve Compression & Sparklines)**: Employs Largest-Triangle-Three-Buckets (LTTB) to compress 1,000-point response curves down to 25–50 points to preserve LLM token budgets; generates inline Unicode sparklines (` ▂▃▄▅▆▇█`).
- **Pillar 4 (Zero-Downtime Fallback Parity)**: If the native Rust binary is absent, pure Python implementations execute transparently with 100% test parity.
- **Darwin/Linux Linker Flag**: Builds must use `RUSTFLAGS="-C link-arg=-undefined -C link-arg=dynamic_lookup"` so Python runtime symbols resolve dynamically. Rust unit tests run with `cargo test --no-default-features`.

## Failure Lessons & Operational Hardening

All real-world post-mortems and architectural bug fixes are codified in `Failure-lessons/`:
- `01-fail-closed-anonymous-http-binding.md`: Container crash on 0.0.0.0 without auth.
- `02-fastmcp-async-worker-context-decoupling.md`: Background worker 401 AUTH_REQUIRED fix.
- `03-gcs-fuse-posix-hardlink-incompatibility.md`: Errno 38 hardlink fallback for GCS FUSE.
- `04-relative-ingest-path-resolution-boundary.md`: Resolving relative filenames against `ingest_root`.
- `05-netcdf-materialization-file-write-omission.md`: Ensuring payload bytes written before native NetCDF read.
- `06-bayesian-rfm-domain-invariants.md`: Enforcing $x = 0 \implies t_x = 0$ for BG/NBD models.
- `07-remote-client-sandbox-data-ingestion.md`: Multi-modal data ingestion (content, base64, url) and actionable error diagnostics.
- `08-large-artifact-streaming-and-ram-limits.md`: 1GB chunked streaming, HTTP Range requests, and zero-RAM symlink materialization.
- `09-mcp-call-collapse-and-intermediate-checkpointing.md`: Intermediate stage checkpoints and bounded heartbeat polling to prevent HTTP timeouts.
- `10-state-recovery-and-crash-resumption.md`: State machine transitions from FAILED/CANCELLED and automatic crash recovery on startup.
- `11-artifact-sandbox-push-and-server-garbage-collection.md`: Direct curl/SHA256 sandbox export and automated server-side garbage collection.
- `12-saturation-curves-response-fidelity-and-decision-caveats.md`: Saturation curve rendering, response curve granularity, and propagating data sparsity warnings to budget optimization.
- `13-native-rust-acceleration-pyo3-and-mcmc-gatekeeper.md`: Rust C-extension acceleration, PyO3 dynamic linking on Darwin/Linux, split R-hat edge-case gatekeeping, and zero-downtime Python fallback parity.
- `14-pyo3-major-version-breaking-api-changes.md`: Never auto-merge multi-version pyo3 bumps without `cargo check --workspace`; pyo3 0.24+ has breaking `IntoPyObject` / `Bound<'py, PyAny>` API changes incompatible with our 0.23 code. Dependabot PR #18 deferred pending migration sprint.

## Release claim rule

Before calling work production-ready, release-ready, M4-complete or equivalent, verify that `docs/release-evidence/` contains generated evidence for the exact commit and that the required CI/security/statistical/recovery/agent gates are green

If that evidence is absent, describe the implementation and remaining blockers without promoting the maturity label


