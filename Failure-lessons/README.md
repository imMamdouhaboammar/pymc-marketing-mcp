# Failure Lessons & Engineering Memory Knowledge Base

This directory is the durable engineering memory of `pymc-marketing-mcp`. It records important architectural bugs, operational edge cases, statistical discrepancies, and root-cause solutions encountered during deployment, aggressive testing, and production hardening.

> **Core Axiom**: We should pay for an engineering mistake once. After that, the repository should remember it.
>
> Failures are documented by **failure class**, not merely by the individual bug that exposed them.

---

## Rules We Now Enforce

Every engineering agent and contributor working on this repository must preserve these 10 non-negotiable invariants:

1. **One Model Registry**: Model identity and resolution must have one canonical implementation (`ModelRegistry.resolve`) that normalizes prefixes, UUIDs, and URI schemes, and strictly validates model type invariants.
2. **One Artifact Readiness Contract**: Never expose a model or job as `completed` before physical artifact publication, checksum verification, and registry indexation are fully committed (`serialize -> validate -> atomic move -> register -> expose`).
3. **One Validation Source of Truth**: One domain invariant must have one canonical validation implementation. Every asynchronous submission endpoint must run synchronous preflight validation before queue admission.
4. **One Decision Evaluation Path**: Decision endpoints representing the same economic model must share one canonical response-evaluation path and respect normalized target scaling. Never optimize unscaled raw monetary variables.
5. **Lineage Checks Fail Closed**: Lineage checks must fail closed. Entity ID overlap $\ne$ modeling cohort. Both dataset fingerprint, currency, time bounds, and population hashes must match before multi-model composition is permitted.
6. **Transitional Job States Must Terminate**: A transitional state (`cancelling`) must never become an indefinite durable state. Late worker completions must be fenced and discarded if a job was cancelled.
7. **Panel Estimates Expose Empirical Support**: In hierarchical and panel models, never present prior-dominated posterior estimates as empirical evidence. Always classify and expose empirical support metadata (`observed`, `weak_support`, `no_empirical_support`, `extrapolated`, `prior_dominated`).
8. **Official Workflows Must Satisfy Downstream Prerequisites**: If a downstream official workflow requires an artifact capability (e.g. `log_likelihood` for LOO/WAIC model selection), the upstream official workflow must produce it by default or declare that requirement before fitting.
9. **User Errors Are Not INTERNAL Errors**: Caller errors are never INTERNAL errors. All domain and validation exceptions must map to a standardized, machine-readable error taxonomy with explicit remediation guidance. Suggested `next_actions` must originate from the registered capability catalog.
10. **Completion Claims Require Fresh Adversarial Evidence**: A regression test is not proven useful until it can be shown to fail when the relevant fix is removed or the defect is reintroduced. Green tests $\ne$ verified requirements without red-green falsification.

---

## Primary Failure Classes

| Document | Primary Focus | Key Lessons |
|---|---|---|
| [decision-integrity.md](./decision-integrity.md) | Optimizer scale invariance, simplex parameterization, target scaling | `DEC-001`, `DEC-002` |
| [model-lineage.md](./model-lineage.md) | Multi-model CLV composition, fail-closed verification, cohort hashing | `CLV-001` |
| [artifact-lifecycle.md](./artifact-lifecycle.md) | Frozen dataclass immutability, atomic publication, readiness race conditions | `ART-001`, `ART-002` |
| [job-lifecycle.md](./job-lifecycle.md) | Async state machine guarantees, cancellation fencing, payload compactness | `JOB-001`, `JOB-002` |
| [validation-contracts.md](./validation-contracts.md) | Preflight vs worker admission parity, canonical domain validators | `MMM-VAL-001`, `DATA-001` |
| [model-registry.md](./model-registry.md) | Unified model resolution across types, prefix normalization | `CLV-REG-001` |
| [panel-mmm.md](./panel-mmm.md) | Multi-dimensional xarray coordinate preservation, zero-support detection | `PANEL-001`, `PANEL-002` |
| [statistical-workflows.md](./statistical-workflows.md) | Workflow sequencing, LOO/WAIC prerequisites, capability manifests | `MODEL-SEL-001` |
| [api-contracts.md](./api-contracts.md) | Normalized error taxonomy, traceback sanitization, registered `next_actions` | `API-ERR-001`, `API-NEXT-001` |
| [testing-and-verification.md](./testing-and-verification.md) | Red-green verification protocol, adversarial fixtures, anti-pattern catalog | `TEST-001` |
| [lessons-index.md](./lessons-index.md) | Master lookup table mapping lessons, rules, systems, and regression tests | Master Cross-Reference |

---

## Failure-Lesson Schema

Every failure lesson in this directory follows a structured engineering post-mortem schema:

```markdown
## [Failure Identifier]: [Descriptive Name]

### What happened
Short factual description.

### Why it mattered
Correctness, business, reliability, statistical, or operational impact.

### Observable symptom
What was actually observed (errors, unexpected outputs, logs).

### Initial assumption
What was originally believed or what the implementation implicitly assumed.

### Root cause
The confirmed root cause (labeled Confirmed, Strongly indicated, or Still uncertain).

### Why the system allowed it
The architectural weakness, missing guard, or testing gap.

### Fix
The implemented fix at the proper architectural abstraction level.

### Verification
The regression test or adversarial experiment proving the fix.

### Prevention rule
A concise, binding engineering invariant.

### Reusable lesson
Where else this pattern or principle applies across the codebase.

### Related failures
Cross-links to related failure lessons.
```

---

## When to Update This Knowledge Base

Documents in this directory must be updated when:
1. A similar defect reappears or bypasses existing defenses.
2. A deeper root-cause explanation or cleaner abstraction is discovered.
3. The underlying platform architecture or library dependencies change.
4. Stronger regression test coverage or adversarial fixtures are authored.
5. A previously codified lesson proves incomplete or overly narrow.

---

## Historical Post-Mortem Archive (Lessons 01–34)

Detailed case studies from earlier container deployment and Cloud Run hardening sessions remain indexed in [lessons-index.md](./lessons-index.md) and archived below:

* [01: Fail-Closed Anonymous HTTP Binding](./01-fail-closed-anonymous-http-binding.md)
* [02: FastMCP Async Worker Context Decoupling](./02-fastmcp-async-worker-context-decoupling.md)
* [03: GCS FUSE POSIX Hardlink Incompatibility](./03-gcs-fuse-posix-hardlink-incompatibility.md)
* [04: Relative Ingest Path Resolution Boundary](./04-relative-ingest-path-resolution-boundary.md)
* [05: NetCDF Model Materialization File Write Omission](./05-netcdf-materialization-file-write-omission.md)
* [06: Bayesian RFM Mathematical Domain Invariants](./06-bayesian-rfm-domain-invariants.md)
* [07: Remote Client Sandbox Data Ingestion & Diagnostic Usability](./07-remote-client-sandbox-data-ingestion.md)
* [08: 1GB Large Artifact Streaming & Cloud Run RAM Limits](./08-large-artifact-streaming-and-ram-limits.md)
* [09: MCP Call Collapse & Intermediate State Checkpointing](./09-mcp-call-collapse-and-intermediate-checkpointing.md)
* [10: State Machine Crash Recovery & Resumption](./10-state-recovery-and-crash-resumption.md)
* [11: Artifact Sandbox Push & Server Garbage Collection](./11-artifact-sandbox-push-and-server-garbage-collection.md)
* [12: Saturation Curve Rendering & Decision Identifiability Caveats](./12-saturation-curves-response-fidelity-and-decision-caveats.md)
* [13: Native Rust C-Extension Acceleration & Diagnostic Gatekeeper](./13-native-rust-acceleration-pyo3-and-mcmc-gatekeeper.md)
* [14: PyO3 Major Version Breaking API Changes (0.23 → 0.29)](./14-pyo3-major-version-breaking-api-changes.md)
* [15: Universal MCP Agent Transport Interop](./15-universal-mcp-agent-transport-interop.md)
* [16: Artifact Export Credential Leakage](./16-artifact-export-credential-leakage.md)
* [17: Dataset Ingestion SSRF and Memory Exhaustion](./17-dataset-ingestion-ssrf-and-memory-exhaustion.md)
* [18: Silent SQLite Cleanup Syntax Error](./18-silent-sqlite-cleanup-syntax-error.md)
* [19: Job Recovery Unhandled Exceptions](./19-job-recovery-unhandled-exceptions.md)
* [20: Daily Time Series Continuity Gaps](./20-daily-time-series-continuity-gaps.md)
* [21: Deceptive Async Job Checkpoints](./21-deceptive-async-job-checkpoints.md)
* [22: Budget Optimizer Line Search Instability](./22-budget-optimizer-line-search-instability.md)
* [23: Default Tenant Metadata Leakage](./23-default-tenant-metadata-leakage.md)
* [24: Prior Sensitivity Contract Fidelity](./24-prior-sensitivity-contract-fidelity.md)
* [25: Remote Dataset Content-Type Verification](./25-remote-dataset-content-type-verification.md)
* [26: Adversarial Harsh Regression Matrix](./26-adversarial-harsh-regression-matrix.md)
* [27: Silent Rust Exclusion in Production Packaging](./27-silent-rust-exclusion-in-production-packaging.md)
* [28: Statistical Authority Duplication & Fallback AttributeError](./28-statistical-authority-duplication-and-fallback-attribute-error.md)
* [29: Pseudonative Serialization Roundtrip Penalty](./29-pseudonative-serialization-roundtrip-penalty.md)
* [30: Unconnected Edge Accelerators & LLM Token Bloat](./30-unconnected-edge-accelerators-and-llm-token-bloat.md)
* [31: MCP Protocol Inversion & Unprotected Ingress Admission](./31-mcp-protocol-inversion-and-admission-boundary.md)
* [32: Deceptive Cancellation & Orphan Compute Fences](./32-deceptive-cancellation-and-orphan-compute-fence.md)
* [33: PyO3 Build in Slim Rust Container Missing Python Interpreter & ABI Mismatch](./33-pyo3-build-in-rust-slim-missing-python-interpreter.md)
* [34: Dockerfile POSIX /bin/sh Process Substitution Syntax Error](./34-dockerfile-posix-sh-process-substitution-syntax-error.md)
