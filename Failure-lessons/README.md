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

