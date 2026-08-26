# PyMC Marketing MCP — Implementation Plan & Phase Tracking

**Goal:** Evolve `pymc-marketing-mcp` into a decision-safe, hardened Bayesian marketing science platform with PyMC-Marketing.

**Baseline:** v0.4.0 (Release Candidate) — 446 passing tests, 0 lint/pyright errors, 39 public capabilities, machine-verified release evidence.

---

## Phases & Hardening Waves

### Core Capability Phases (Completed)
- **Phase 1: Adstock & Saturation Zoo + Channel Priors** ✅ — Full curve library with per-channel configuration.
- **Phase 2: Visual Posterior Artifacts** ✅ — Posterior plots, saturation curves, and waterfall contributions.
- **Phase 3: Customer Lifetime Value (CLV) Analytics** ✅ — BG/NBD, Gamma-Gamma, and sBG customer analytics suite.
- **Phase 4: Dynamic Flighting & Budget Optimization** ✅ — Multi-period media flighting with carryover dynamics and constraints.
- **Phase 5: Bayesian Model Comparison** ✅ — PSIS-LOO, WAIC, and Bayesian stacking weights.

### Hardening Master Program (Waves A–G Completed)
- **Wave A (Gate H0: Runtime Truth Baseline)** ✅ — Version alignment, CI workflows (`ci.yml`, `statistical.yml`, `security.yml`, `upstream-canary.yml`, `release.yml`), and release evidence framework.
- **Wave B (Gates H1 + H2 / G3: Request-Scoped Auth & Object Isolation)** ✅ — `ContextVar[ExecutionContext]`, `RequestScopedContextProvider`, `AuthorizationService`, and tenant isolation on all tools/resources.
- **Wave C (Gate H3: Credential Control Plane Security)** ✅ — `CredentialService`, salted SHA-256 verifier storage (`SQLiteCredentialRepository`), `/control/credentials` HTTP API, and zero browser secret storage.
- **Wave D (Gates G2 + H4: Durable Jobs & Process Worker)** ✅ — Canonical semantic idempotency hashing, `ProcessJobWorker`, and `marketing-mcp-worker` CLI.
- **Wave E (Gate G4: Observability & Tracing)** ✅ — Single-line structured JSON logging with secret scrubbing, low-cardinality metrics, and distributed `trace_span` propagation.
- **Wave F (Gates AQG + H5: Agent Quality Gate & Skill Evals)** ✅ — Dynamic trace-driven agent evaluations and decision-safety assertions.
- **Wave G (Gate H6: Upstream Compatibility & Admission Gate)** ✅ — Upstream canary test automation against latest PyMC-Marketing and ArviZ.

---

## Key Architectural Invariants
1. **Decision Integrity**: Statistical outputs are computed exclusively by PyMC-Marketing/ArviZ; rejected models block decision-grade tools (`DECISION-INTEGRITY.md`).
2. **Security**: Remote callers use request-scoped authentication; credentials stored exclusively as salted SHA-256 verifiers with immediate revocation.
3. **Durability**: Background jobs use process-isolated workers and state survives server restarts.
4. **Documentation**: Zero docs drift across all 11 core documents (`check_docs_drift.py`).
