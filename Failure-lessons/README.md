# Failure Lessons & Production Hardening Post-Mortems

This directory codifies real-world architectural bugs, operational edge cases, and root-cause solutions encountered while deploying, testing, and hardening `pymc-marketing-mcp` on Google Cloud Run and remote container environments.

Following the Compound Engineering loop, `/fable-learning`, and `/convo-learn` methodologies, every failure is analyzed with:
- **Executive Summary & Context**
- **Symptom & Error Signature**
- **Root Cause Analysis**
- **Resolution & Architecture Diff**
- **Verification Evidence & Invariants**

---

## Post-Mortem Index

| # | Lesson / Post-Mortem | Impact Area | Severity | Key Takeaway |
|---|---|---|---|---|
| 01 | [Fail-Closed Anonymous HTTP Binding](./01-fail-closed-anonymous-http-binding.md) | Network / Security Posture | Critical | Defense-in-depth security checks must provide explicit, auditable escape hatches (`MARKETING_MCP_ALLOW_ANONYMOUS_HTTP`) for unauthenticated managed environments. |
| 02 | [FastMCP Async Worker Context Decoupling](./02-fastmcp-async-worker-context-decoupling.md) | Transport / Context Propagation | High | In decoupled ASGI streamable HTTP architectures, tool background workers do not share request context; fallback to an ambient `stdio_context_provider` when auth is disabled. |
| 03 | [GCS FUSE POSIX Hardlink Incompatibility](./03-gcs-fuse-posix-hardlink-incompatibility.md) | Storage / File Systems | Critical | Object storage FUSE mounts do not implement POSIX hardlinks (`os.link`) or permissions (`chmod`). Wrap with atomic replace / move fallbacks. |
| 04 | [Relative Ingest Path Resolution Boundary](./04-relative-ingest-path-resolution-boundary.md) | Data Ingestion / Path Safety | Medium | Safe path resolvers must anchor relative user inputs against `ingest_root` before canonical resolution, rather than resolving against process CWD. |
| 05 | [NetCDF Model Materialization File Write Omission](./05-netcdf-materialization-file-write-omission.md) | Storage / Model Inference | High | Materialization context managers must write physical payload bytes to temporary disk paths before yielding to native C libraries (NetCDF/HDF5). |
| 06 | [Bayesian RFM Mathematical Domain Invariants](./06-bayesian-rfm-domain-invariants.md) | Statistical Modeling / Data Hygiene | High | Bayesian BTYD count models mathematically enforce $x = 0 \implies t_x = 0$ and $t_x \le T$. Preflight guards must catch invalid distributions before MCMC sampling. |
| 07 | [Remote Client Sandbox Data Ingestion & Diagnostic Usability](./07-remote-client-sandbox-data-ingestion.md) | Ingestion / Error Diagnostics | P0 Blocker | Multi-modal ingestion ('content', 'content_base64', 'url') solves client filesystem isolation; batch model validation eliminates repetitive round-trips. |
| 08 | [1GB Large Artifact Streaming & Cloud Run RAM Limits](./08-large-artifact-streaming-and-ram-limits.md) | Storage / Container Lifecycle | P0 Blocker | Stream-hash in 1MB chunks, materialize via symlinks to preserve RAM, and serve resumable HTTP Range requests for multi-gigabyte NetCDF traces. |
| 09 | [MCP Call Collapse & Intermediate State Checkpointing](./09-mcp-call-collapse-and-intermediate-checkpointing.md) | Resilience / Transport | High | Prevent client timeouts during multi-minute MCMC sampling by recording granular stage checkpoints and offering bounded heartbeat polling. |
| 10 | [State Machine Crash Recovery & Resumption](./10-state-recovery-and-crash-resumption.md) | State Machine / High Availability | High | Allow resumption transitions from FAILED/CANCELLED, auto-reconcile stale running jobs on container startup, and resume from latest valid checkpoint. |
| 11 | [Artifact Sandbox Push & Server Garbage Collection](./11-artifact-sandbox-push-and-server-garbage-collection.md) | Storage / Client UX | High | Deliver artifacts directly to client sandboxes with curl and SHA256 verification; automate server-side cleanup of /tmp, expired files, and orphan blobs. |
| 12 | [Saturation Curve Rendering & Decision Identifiability Caveats](./12-saturation-curves-response-fidelity-and-decision-caveats.md) | Plotting / Decision Quality | High | Use canonical `model.plot.saturation_curves` with DataArray `curve`, break down response curves per-channel, and carry forward upstream dataset validation warnings (`LONG_ZERO_SPEND_RUN`) into budget optimization output. |
| 13 | [Native Rust C-Extension Acceleration & Diagnostic Gatekeeper](./13-native-rust-acceleration-pyo3-and-mcmc-gatekeeper.md) | Performance / LLM Latency | High | Accelerate CSV preflight 2,800x (3.7s to 1.31ms) via SIMD Rust, enforce 0.1ms fail-closed split R-hat MCMC decision gates, downsample curves with LTTB, and guarantee zero-downtime Python fallback. |
| 14 | [PyO3 Major Version Breaking API Changes (0.23 → 0.29)](./14-pyo3-major-version-breaking-api-changes.md) | Dependency Management / Rust Extension | High | Never auto-merge multi-version PyO3 bumps without `cargo check`; security-motivated dependabot PRs still require compile verification before merge. |
| 15 | [Universal MCP Agent Transport Interop](./15-universal-mcp-agent-transport-interop.md) | Transport / Discovery | High | Remote AI agent runtimes require `/.well-known/mcp.json` discovery payload and open public endpoint whitelisting for Streamable HTTP. |
| 16 | [Artifact Export Credential Leakage](./16-artifact-export-credential-leakage.md) | Security / Storage | High | Redact authorization tokens, credentials, and sensitive headers when returning artifact export links to AI clients. |
| 17 | [Dataset Ingestion SSRF and Memory Exhaustion](./17-dataset-ingestion-ssrf-and-memory-exhaustion.md) | Security / Ingestion | High | Block internal private network ranges (SSRF protection) and enforce strict streaming size limits on remote dataset URLs. |
| 18 | [Silent SQLite Cleanup Syntax Error](./18-silent-sqlite-cleanup-syntax-error.md) | Storage / Maintenance | Medium | Fix syntax errors in SQLite cleanup queries to prevent silent accumulation of orphaned metadata records. |
| 19 | [Job Recovery Unhandled Exceptions](./19-job-recovery-unhandled-exceptions.md) | State Machine / Resilience | High | Wrap state recovery and deserialization routines in defensive error handlers to prevent unhandled 500 crashes on corrupt jobs. |
| 20 | [Daily Time Series Continuity Gaps](./20-daily-time-series-continuity-gaps.md) | Statistical Modeling / Time Series | Medium | Identify and report daily time-series missing periods and date gaps before MCMC sampling to prevent model fitting failure. |
| 21 | [Deceptive Async Job Checkpoints](./21-deceptive-async-job-checkpoints.md) | State Machine / Diagnostics | High | Ensure progress percentages monotonically increase and map truthfully to discrete execution lifecycle stages. |
| 22 | [Budget Optimizer Line Search Instability](./22-budget-optimizer-line-search-instability.md) | Optimization / Numerical Stability | High | Add fallback optimization strategies with gradient clipping when line search encounters numerical instability or singular matrices. |
| 23 | [Default Tenant Metadata Leakage](./23-default-tenant-metadata-leakage.md) | Multi-Tenancy / Security | High | Ensure multi-tenant queries strictly isolate default tenant records from authenticated tenant namespaces. |
| 24 | [Prior Sensitivity Contract Fidelity](./24-prior-sensitivity-contract-fidelity.md) | Contracts / Schema | Medium | Maintain complete parameter schema coverage when serializing prior sensitivity analysis envelopes. |
| 25 | [Remote Dataset Content-Type Verification](./25-remote-dataset-content-type-verification.md) | Ingestion / Validation | Medium | Validate HTTP Content-Type headers and payload magic bytes before attempting CSV/Parquet parsing from remote URLs. |
| 26 | [Adversarial Harsh Regression Matrix](./26-adversarial-harsh-regression-matrix.md) | Quality Assurance / Resilience | High | Subject all platform endpoints to adversarial inputs (collinear, zero-padded, invalid panels) to verify fail-closed defenses. |
| 27 | [Silent Rust Exclusion in Production Packaging](./27-silent-rust-exclusion-in-production-packaging.md) | Packaging / Container Delivery | Critical | Multi-stage Docker build must compile native extension and assert runtime acceleration; expose backend state in `/health`. |
| 28 | [Statistical Authority Duplication & Fallback AttributeError](./28-statistical-authority-duplication-and-fallback-attribute-error.md) | Statistical Semantics / Fallback Hygiene | Critical | Rust must never hold statistical decision authority; demote split $\hat{R}$ to test fixtures and ensure Python fallback has 100% method parity. |
| 29 | [Pseudonative Serialization Roundtrip Penalty](./29-pseudonative-serialization-roundtrip-penalty.md) | Serialization / Transport Performance | High | Avoid traversing Python object trees into native Serde across PyO3; use CPython's `json.dumps` for Python dicts and Serde for native structs. |
| 30 | [Unconnected Edge Accelerators & LLM Token Bloat](./30-unconnected-edge-accelerators-and-llm-token-bloat.md) | LLM Context Consumption / Transport | Medium-High | Connect LTTB downsampling to response curves and sparklines to dataset summaries to slash prompt token bloat while keeping full-res canonical data. |
| 31 | [MCP Protocol Inversion & Unprotected Ingress Admission](./31-mcp-protocol-inversion-and-admission-boundary.md) | Ingress Protection / Protocol Framing | High | Fast native request admission and size enforcement (<50MB) rejects invalid payloads without allocating Python heap objects. |
| 32 | [Deceptive Cancellation & Orphan Compute Fences](./32-deceptive-cancellation-and-orphan-compute-fence.md) | Async Jobs / Compute Resource Fences | High | Cancelling an async job must halt underlying computation; cooperative checkpoint tokens prevent runaway orphan MCMC sampling. |
| 33 | [PyO3 Build in Slim Rust Container Missing Python Interpreter & ABI Mismatch](./33-pyo3-build-in-rust-slim-missing-python-interpreter.md) | Container Packaging / Native Compilation | Critical | Base Rust builder stage on target CPython container runtime (python:3.12-slim) so pyo3-build-config has exact headers and eliminates minor version ABI incompatibilities. |

---

## Operating Invariants Derived from These Lessons

1. **Storage Transport Agnosticism**: Never assume standard POSIX inode semantics (hard links, mode flags) on container volumes; always implement graceful fallbacks for cloud-mounted filesystems.
2. **Context Continuity**: Ensure asynchronous worker pools maintain valid execution contexts independent of ephemeral HTTP connection lifecycles.
3. **Statistical Invariant Preflight**: Validate domain math before allocating heavy MCMC sampling workloads.
4. **Defense-in-Depth with Auditable Overrides**: Maintain strict default fail-closed security postures, with clear, documented flags for non-standard environments.
5. **Zero-RAM Large Artifact Handling**: Stream and hash artifacts in bounded chunks (1MB) and materialize via symlinks to protect container RAM disks (`tmpfs`).
6. **Granular Checkpointing & Bounded Polling**: Long-running asynchronous Bayesian jobs must persist sub-stage progress to tolerate client disconnections and container restarts.
7. **Proactive Resource Reclamation**: Maintain automated garbage collection for local scratch disks and enforce cloud storage lifecycle TTL policies.
8. **Zero Mathematical Reimplementation**: Keep Bayesian MCMC models 100% in Python; use Rust strictly as an edge accelerator for I/O sniffing, gatekeeping, quantiles, and token compression.
9. **Transparent Fallback Parity**: Always provide 100% behavioral fallback parity in pure Python when native binary extensions are absent.

