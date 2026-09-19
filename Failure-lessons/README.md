# Failure Lessons & Engineering Memory Knowledge Base

This directory is the durable engineering memory of `pymc-marketing-mcp`. It records important architectural bugs, operational edge cases, statistical discrepancies, and root-cause solutions encountered during deployment, aggressive testing, and production hardening.

> **Core Axiom**: We should pay for an engineering mistake once. After that, the repository should remember it.
>
> Failures are documented by **failure class**, not merely by the individual bug that exposed them.

---

## Rules We Now Enforce

Every engineering agent and contributor working on this repository must preserve these non-negotiable invariants:

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
11. **Never Accept Architectural Claims Without Runtime Counters**: Hardware and acceleration claims (e.g. SIMD hashing, zero-copy parsing, pure native streaming) must be backed by explicit runtime telemetry or unit test assertions. Speculative optimizations must never be documented as active reality without verification.
12. **Protection Middleware Must Expose Configurable Test Knobs**: Security and rate-limiting middleware must provide configurable environment knobs (`rate_limit_per_minute`) so that performance benchmarks, stress tests, and integration pipelines are not choked by false-positive throttling.
13. **Native Extension Builds Must Target the Active Runtime**: Native C-extension crates (PyO3) must explicitly link against the active virtual environment (`PYO3_PYTHON`) and configure platform-specific dynamic lookup (`-undefined dynamic_lookup` on macOS) to avoid unresolved symbol link errors during build and packaging.
14. **Document Protocol Boundaries Truthfully**: When native acceleration wraps an external runtime SDK (e.g. MCP Python SDK), protocol admission must truthfully reflect boundary transformations (`InteractionRequest` / `BoundaryRequest`) rather than claiming non-existent zero-copy passthroughs.
15. **Statistical Invariant Tests Must Derive Assertions Dynamically**: Tests verifying optimization invariants (e.g. spend conservation, channel bounds) must compute tolerances and expected values directly from input configurations rather than hardcoding static numbers that silently drift when fixtures change. Every computed variable in a test must have an assertion.
16. **Submodule Import Decoupling & Virtualenv Parity**: Package `__init__.py` files must not eagerly import optional or network-dependent client adapters that require dependencies beyond the base runtime contract. Monorepo sync must verify dependency parity across all subprojects.
17. **Issue Closure Discipline on Main Landing**: Every commit or PR implementing issue specifications must close corresponding issues with traceable test evidence (`Closes #X`), preventing phantom open issue accumulation and cognitive debt.
18. **Release Integrity Enforced in CI, Not SaaS Settings**: Release integrity must be mathematically guaranteed within repository CI workflows (via candidate commit SHA equality and digest verification) rather than relying on external SaaS administrative settings that may be restricted by plan or visibility.
19. **Explicit Provenance Allowlisting**: Release evidence, telemetry, and audit logs must strictly enforce an explicit allowlist (`_SAFE_ENV_KEYS`) of safe variables. Ambient environment dumps with denylists are strictly prohibited.
20. **Single-Build Promotion**: Release artifacts (wheel, sdist, containers) must be built once from a verified immutable commit SHA, tested in place, and promoted by cryptographic hash without rebuilding.
21. **Active Git Remote Verification in Composite Workspaces**: Never infer a Git remote target from ambient root documentation (`state.toon`, parent README) when working in composite or nested workspaces. Always resolve and verify `git remote -v`, active branch, and open PR status in the project directory before staging, committing, or pushing (`WS-REM-001`).
22. **Pre-Push Quality Gate Batching & Timeout Isolation**: Do not submit large monolithic batches of multi-file findings into automated gate fixes (`no-mistakes axi respond --action fix`). Remediate straightforward manifest, naming, and packaging findings locally before invoking quality gates, and partition remaining automated fixes into single-domain batches (`GATE-RUN-001`).
23. **Package Manifest Boundary for Review Path Filters**: Code review and static analysis path filters (`.coderabbit.yaml`, Sonar, linter scopes) must be derived directly from the active project's packaging manifest (`pyproject.toml`, `Cargo.toml`, `package.json`), never from generic templates that omit primary source trees (`src/**`) (`CFG-PATH-001`).
24. **Resource Identity Binding in Recovery**: Recovery authorization must strictly bind to the concrete resource instance (`job_id`) and originating tool family; completing recovery or executing usable continuations must reset lifecycle flags to prevent stale context leakage.
25. **Parameter-Kind Worker Introspection**: Never catch `TypeError` at the call site to detect function arity; always inspect `inspect.signature` parameter kinds (`POSITIONAL_ONLY`, `KEYWORD_ONLY`, `VAR_POSITIONAL`) before invocation to guarantee exactly-once execution.
26. **Atomic Resource Admission**: In-flight operation admission must be atomic within a single lock acquisition; never release a lock between checking for existing execution and registering new execution. Direct-operation identities must be scoped by tenant, principal, and canonical payload.
27. **Evaluator Schema Fidelity**: Evaluation trace fixtures and validator assertions must strictly conform to public API contracts; never inject synthetic helper fields into tool argument payloads that the live server rejects.
28. **Deterministic Testing for Governance Gates**: Never rely on stochastic sampling to trigger safety and decision gates in contract tests; always verify governance policies against deterministic injected failure payloads.
29. **Non-Interactive Credential Helpers in Automated Environments**: Automated agents and headless subshells must configure token-based, non-interactive credential helpers locally (`!gh auth git-credential`), clearing desktop GUI helpers (`osxkeychain`) to prevent silent subshell execution hangs.
30. **Container Shell Pipefail Safety & Container Lint Standards**: Automated AI security bot PRs must never be merged without full container lint (Hadolint/Super-Linter) verification; lockfiles (`uv.lock`, `Cargo.lock`) govern integrity rather than unpinned inline shell pipes.
31. **Semantic DOM & WCAG 2.1 AA Primitives in Analytical Dashboards**: All frontend UI components must enforce WCAG 2.1 AA: explicit `scope` on table headers, `htmlFor` on labels, accessible names for external links, and semantic button/keyboard handling on interactive controls.
32. **Programmatic Branch Protection with Exact CI Status Checks**: Default branches must programmatically enforce branch protection with strict status checks matching exact CI job names before declaring production readiness.
33. **Statistical Test Sampler Step-Size Calibration Across CPU Microarchitectures**: Statistical test fixtures with reduced warm-up/draw counts on high-dimensional posteriors must set `target_accept >= 0.97` to prevent platform-specific CPU divergence flakiness.
34. **Sole Active Repository Law**: The ONLY active repository locally and remotely across this entire project is `https://github.com/imMamdouhaboammar/pymc-marketing-mcp`. All other repositories, specification directories, and legacy workspaces are read-only donors or frozen specs. Every git commit, PR, and remote push MUST be executed strictly inside `pymc-marketing-mcp/` targeting `imMamdouhaboammar/pymc-marketing-mcp.git`. Pushing to any other repository is strictly prohibited (`WS-ACT-001`).

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

### Context
Where this class of problem appeared.

### What happened
Short factual description.

### Why it mattered / Impact
Correctness, business, reliability, statistical, or operational impact.

### Observable symptom
What was actually observed (errors, unexpected outputs, logs).

### Initial assumption / Incorrect assumption
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

### Related code
Stable module, symbol, or file references.

### Related tests
Relevant regression, contract, or statistical tests.

### Status
One of: Resolved, Partially mitigated, Unresolved, Superseded.
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

## Historical Post-Mortem Archive (Lessons 01–61)

Detailed case studies from earlier container deployment, hardening, and multi-repo sessions remain indexed in [lessons-index.md](./lessons-index.md) and archived below:

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
* [35: Fictional Crypto Acceleration & Streaming Claims](./35-fictional-crypto-acceleration-and-streaming-claims.md)
* [36: Rate Limiter Choke on High-Throughput Benchmarks](./36-rate-limiter-choke-on-high-throughput-benchmarks.md)
* [37: macOS PyO3 Linker Symbol Resolution & Virtualenv Incompatibility](./37-macos-pyo3-linker-symbol-resolution-and-virtualenv.md)
* [38: Dual-Parse Protocol Boundary & Typed Interaction Contracts](./38-dual-parse-protocol-boundary-and-typed-contracts.md)
* [39: Statistical Test Assertion Drift & Budget Conservation Invariant](./39-statistical-test-assertion-drift-and-budget-conservation.md)
* [40: Multi-Virtualenv Submodule Import Collision](./40-multi-virtualenv-submodule-import-collision.md)
* [41: Phantom Open Issue Accumulation vs Branch Landing Drift](./41-phantom-open-issue-accumulation-vs-branch-landing-drift.md)
* [42: Private Repo Branch Protection API Entitlement Boundary](./42-private-repo-branch-protection-api-entitlement-boundary.md)
* [43: Release Evidence Environment Allowlist Hygiene](./43-release-evidence-environment-allowlist-hygiene.md)
* [44: Exact Candidate SHA Binding & Single-Build Promotion](./44-exact-candidate-sha-binding-and-single-build-promotion.md)
* [45: Multidimensional Allocation Normalization in Decision Service](./45-multidimensional-allocation-normalization.md)
* [46: Bogus Provenance Acceptance on Uncalibrated Confidence](./46-bogus-provenance-acceptance-on-uncalibrated-confidence.md)
* [47: Conflation of Media Response & Customer Acquisition Cohorts](./47-conflation-of-media-response-and-customer-acquisition-cohorts.md)
* [48: Registry Negative Guards & RFC-Gated Objectives](./48-registry-negative-guards-and-rfc-gated-objectives.md)
* [49: Boundary Overlap in Text Replacement Code Modifications](./49-boundary-overlap-in-text-replacement-code-modifications.md)
* [50: Pre-Push Quality Gate Bounded Timeout & Remediated Batch Sizing](./50-pre-push-quality-gate-bounded-execution-drift.md)
* [51: Resource-Bound Recovery and Disconnect Lifecycle Reset](./51-resource-bound-recovery-and-lifecycle-reset.md)
* [52: Composite Workspace Git Remote Misdirection](./52-composite-workspace-git-remote-misdirection.md)
* [53: Positional Parameter Inspection and Exactly-Once Worker Dispatch](./53-positional-parameter-inspection-and-worker-dispatch.md)
* [54: Atomic Direct-Operation Admission and Scoped Canonical Identities](./54-atomic-operation-admission-and-canonical-scoping.md)
* [55: Evaluator Schema Fidelity and Public Tool Contract Alignment](./55-evaluator-schema-fidelity-and-contract-alignment.md)
* [56: Deterministic Contract Injection for Stochastic Failure Gates](./56-deterministic-contract-injection-for-stochastic-failure-gates.md)
* [57: Desktop GUI Keychain Blocks in Headless/Agentic CI Subshells](./57-desktop-keychain-hang-in-headless-agentic-subshells.md)
* [58: Automated AI Security Patches Breaking Container Linting Standards (Hadolint / Super-Linter)](./58-automated-security-patch-container-linter-compliance.md)
* [59: Frontend Accessibility & WCAG 2.1 AA Compliance in Analytical Dashboards](./59-frontend-accessibility-wcag-compliance-in-analytical-dashboards.md)
* [60: Programmatic Branch Protection & Exact CI Status Check Binding](./60-programmatic-branch-protection-ci-status-check-binding.md)
* [61: MCMC Posterior Sampler Step-Size Calibration Across CPU Architectures](./61-mcmc-posterior-sampler-step-size-calibration-across-cpu-architectures.md)
