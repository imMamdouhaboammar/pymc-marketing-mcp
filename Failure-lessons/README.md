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

---

## Operating Invariants Derived from These Lessons

1. **Storage Transport Agnosticism**: Never assume standard POSIX inode semantics (hard links, mode flags) on container volumes; always implement graceful fallbacks for cloud-mounted filesystems.
2. **Context Continuity**: Ensure asynchronous worker pools maintain valid execution contexts independent of ephemeral HTTP connection lifecycles.
3. **Statistical Invariant Preflight**: Validate domain math before allocating heavy MCMC sampling workloads.
4. **Defense-in-Depth with Auditable Overrides**: Maintain strict default fail-closed security postures, with clear, documented flags for non-standard environments.
