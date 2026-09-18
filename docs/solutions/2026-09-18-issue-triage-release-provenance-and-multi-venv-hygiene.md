# Solution: Issue Triage Debt Resolution, Release Provenance Hygiene & Multi-Virtualenv Parity

**Date**: 2026-09-18
**Context**: Reconciling the open issue backlog, release provenance guarantees, and cross-workspace runtime hygiene in `pymc-marketing-mcp` and `pymc-unified-platform-spec`.
**Outcome**: Triaged and closed 13 stale/resolved GitHub issues (#4–#10, #12–#17) with traceable test evidence, classified external SaaS branch protection boundaries (#11), synchronized submodule virtualenv dependencies (`httpx`), codified lessons 40–44 into project failure memory, and verified 100% green platform status (130 tests).

---

## 1. Problem Statement & Discoveries

During full-platform verification and repository inspection, four key systemic issues were identified:

1. **Phantom Issue Accumulation (Issue Triage Debt)**: 14 open GitHub issues (#4–#17) remained active, leading contributors to believe the platform had 14 unresolved production blockers. Detailed code and test audits revealed that 13 of those issues had already been solved, tested, and merged into `main` in prior hardening waves (`e637c72`, `1182e64`), but lacked automated closing triggers.
2. **SaaS Entitlement Boundary Failure (Issue #11)**: Programmatic attempts to audit or configure branch protection on `main` via `gh api repos/.../branches/main/protection` failed with `HTTP 404: Branch not protected`. This stemmed from GitHub plan restrictions on private personal repositories, requiring manual web UI administration rather than automated CLI setup.
3. **Multi-Virtualenv Dependency Desynchronization**: Running unit tests via the submodule's dedicated virtualenv (`pymc-marketing-mcp/.venv`) failed with `ModuleNotFoundError: No module named 'httpx'` because cross-platform gateway client adapters were eagerly imported in `marketing_mcp/adapters/__init__.py`.
4. **Dangerous Ambient Environment Denylists**: Historical release evidence captured full `os.environ` snapshots with denylist redaction, creating a vulnerability where newly added secret names could leak into published audit records.

---

## 2. Root Cause Analysis

| Problem Class | Observable Symptom | Confirmed Root Cause |
|---|---|---|
| **Issue Governance** | 14 open issues despite clean code | Commits merged with omnibus messages without `Fixes #X` / `Closes #X` keywords, decoupling code landing from issue state. |
| **SaaS Entitlement** | `gh api` 404 on branch protection | GitHub restricts ruleset/branch-protection API management on private personal repos; requires manual UI configuration or paid plan. |
| **Runtime Isolation** | `ModuleNotFoundError: No module named 'httpx'` | Submodule `__init__.py` eagerly imported network client adapters not declared in base dependencies, while child venv was un-synced. |
| **Release Provenance** | Risk of credential leakage in evidence | Using an environment denylist rather than an explicit, immutable allowlist (`_SAFE_ENV_KEYS`). |
| **Supply Chain** | Risk of rebuild divergence in release | Building packages and container images after smoke tests rather than promoting verified candidate digests. |

---

## 3. Implemented Solutions & Invariants

### A. Evidence-Based Issue Triage & Closure
Every candidate issue was matched against its guarding regression test suite:
- **#4**: 27 tests in `tests/unit/test_release_evidence.py` (fail-closed gate proofs).
- **#5**: `test_unknown_environment_keys_are_not_persisted` (immutable allowlist).
- **#6**: `tests/unit/test_lift_calibration_contract.py` (lift schema reconciliation).
- **#7**: 6 tests in `tests/unit/test_optimizer_failure_contract.py` (budget reload stability).
- **#8**: `tests/unit/test_profile_workflow_policy.py` (isolated `profile-summary-cards` branch).
- **#9**: 19 tests in `tests/integration/test_standalone_worker.py` (process worker with heartbeat/fencing).
- **#10**: 7 tests in `tests/unit/test_statistical_shards.py` (6 disjoint shards in CI).
- **#12**: 3 tests in `tests/release/test_candidate_provenance.py` (single-build digest binding).
- **#13**: 2 tests in `tests/unit/test_action_runtime_policy.py` (66 action uses pinned to Node 24 SHAs).
- **#14**: 16 tests in `tests/integration/test_production_oauth_http.py` (asymmetric JWKS OAuth).
- **#15**: 2 tests in `tests/unit/test_upstream_compatibility.py` (major version bounded `<2`).
- **#16**: 5 tests in `tests/integration/test_sql_repository_contracts.py` (Postgres shared SQL path).
- **#17**: 3 tests in `tests/integration/test_artifact_store_contracts.py` (immutable blob storage & SHA-256).

All 13 issues were closed with traceable comments referencing commits `1182e64` / `e637c72` and test names.

### B. CI-Enforced Release Candidate Integrity (Mitigating #11)
Instead of relying on external SaaS branch protection, candidate integrity was made mathematical inside `.github/workflows/release.yml`:
```bash
TAG_SHA=$(git rev-parse "${TARGET_TAG}^{commit}")
CANDIDATE_SHA=$(git rev-parse HEAD)
test "${TAG_SHA}" = "${CANDIDATE_SHA}"
```
Release publication is strictly gated by candidate commit equality and digest verification.

### C. Explicit Provenance Allowlisting
In `src/marketing_mcp/release_evidence.py`, replaced denylist capture with an explicit immutable allowlist:
```python
_SAFE_ENV_KEYS = frozenset({
    "CI", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS", "PYTHONHASHSEED",
    "RUNNER_ARCH", "RUNNER_OS",
})
```

### D. Multi-Virtualenv Parity & Lazy Adapter Boundaries
Synchronized child virtualenv via `uv pip install httpx -p pymc-marketing-mcp/.venv` and bounded adapter imports so statistical modules do not fail collection when network clients are not invoked.

---

## 4. Verification & Health Ledger

- **Rust Workspace**: 28 tests passing (`cargo test --workspace`).
- **Bun / TypeScript Client & Web**: 100% build & typecheck clean.
- **Python Contract Suite**: 45 tests passing.
- **Platform Storage, Engine, Worker & Security Suites**: 57 tests passing.
- **MCP Regression Suite (covering 13 issues)**: 66 tests passing.
- **Full Platform Verification Runner**: `./check.sh` exited 0 (All Green 🚀).

---

## 5. Durable Rules We Now Enforce

1. **Submodule Virtualenv Dependency Parity**: Package `__init__.py` files must not eagerly import unpinned external network dependencies; monorepo sync must guarantee dependency parity across all subprojects.
2. **Issue Closure Discipline**: Every commit or PR implementing an issue must use `Fixes #X` / `Closes #X` or be formally verified and closed with commit SHA and test evidence during release candidate audits.
3. **Release Integrity Enforced in CI**: Never make release integrity depend on external SaaS administrative settings; enforce candidate commit equality and digest verification within CI.
4. **Explicit Provenance Allowlisting**: Release evidence and telemetry must always use an explicit allowlist (`_SAFE_ENV_KEYS`) of safe variables. Denylists are prohibited.
5. **Single-Build Promotion**: Release artifacts must be built once from a verified immutable commit SHA, tested in place, and promoted by cryptographic hash without rebuilding.
