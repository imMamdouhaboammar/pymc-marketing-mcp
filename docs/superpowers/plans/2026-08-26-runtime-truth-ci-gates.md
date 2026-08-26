# Runtime Truth and CI Gate Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make current-head executable evidence the only source of production-readiness truth, catch security/statistical drift before merge, and prevent documentation or release metadata from claiming behavior the assessed commit has not proved.

**Architecture:** Generate a machine-readable evidence bundle from CI, derive readiness/status documentation from that bundle, split PR/nightly/release workflows by cost and risk, and add explicit hardening gates H0-H6 alongside G0-G5 without allowing hand-edited green status.

**Tech Stack:** GitHub Actions, uv, pytest, Ruff, Pyright, Docker, SBOM/security scanners, existing release-evidence scripts.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- A rerun is not a substitute for fixing a flaky release-critical test.
- Gate state must identify exact git SHA, lock/dependency versions, platform and test command.
- Documentation may summarize evidence but must not independently set pass/fail.
- PR CI must stay bounded; real stochastic sampling can run in protected/nightly lanes.
- Release artifacts must be built from the same commit whose gates passed.

---

### Task 1: Regenerate current-head baseline and retire stale root findings

**Files:**
- Modify: `docs/release-evidence/v0.4-current-head.md` or create a dated current-head evidence file
- Move/archive: `findings.md` -> `docs/archive/2026-08-22-findings.md`
- Create: `docs/release-evidence/2026-08-26-current-head.md`
- Modify: `scripts/collect_release_evidence.py`

- [ ] **Step 1: Capture exact versions and SHA**

Run:

```bash
git rev-parse HEAD
uv sync --frozen --extra dev
uv run python - <<'PY'
import importlib.metadata as m
for name in ["pymc-marketing", "pymc", "arviz", "mcp", "xarray", "pydantic", "numpy", "pandas"]:
    print(name, m.version(name))
PY
```

- [ ] **Step 2: Execute baseline commands once and record raw outcomes**

```bash
uv run ruff check src tests
uv run pytest -n auto -q
uv run pytest -m statistical -q
uv run pytest tests/integration -q
uv build
docker build -t pymc-marketing-mcp:hardening-baseline .
```

- [ ] **Step 3: Extend the evidence collector schema**

Target JSON fields:

```json
{
  "commit_sha": "...",
  "package_version": "...",
  "dependencies": {},
  "commands": [],
  "gate_results": {},
  "artifact_hashes": {},
  "generated_at": "..."
}
```

- [ ] **Step 4: Archive stale `findings.md` with an explicit historical banner**
- [ ] **Step 5: Commit**

```bash
git add docs scripts findings.md
git commit -m "docs(evidence): refresh current-head runtime truth"
```

---

### Task 2: Make readiness status machine-derived

**Files:**
- Create: `src/marketing_mcp/readiness_evidence.py`
- Create: `scripts/render_production_readiness.py`
- Modify: `docs/PRODUCTION-READINESS.md`
- Test: `tests/unit/test_readiness_evidence.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class GateEvidence:
    gate: str
    status: Literal["green", "red", "not_run"]
    commit_sha: str
    tests: tuple[str, ...]
    evidence_file: str
```

```python
def render_readiness(evidence: Sequence[GateEvidence]) -> str: ...
```

- [ ] **Step 1: Write tests proving docs cannot mark a gate green without evidence**
- [ ] **Step 2: Implement evidence parsing and deterministic rendering**
- [ ] **Step 3: Add a docs-drift test comparing generated output to committed readiness**

```bash
uv run pytest tests/unit/test_readiness_evidence.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/readiness_evidence.py scripts/render_production_readiness.py docs/PRODUCTION-READINESS.md tests/unit/test_readiness_evidence.py
git commit -m "feat(release): derive readiness status from executable evidence"
```

---

### Task 3: Add Pyright and fix Python/Ruff target drift

**Files:**
- Modify: `pyproject.toml`
- Create: `pyrightconfig.json` if configuration is clearer outside TOML
- Test: CI configuration in Task 4

- [ ] **Step 1: Add `pyright` to dev dependencies**
- [ ] **Step 2: Set Ruff target to Python 3.12 to match `requires-python >=3.12,<3.14`**
- [ ] **Step 3: Scope first strict checks to contracts/boundaries**

Initial required paths:

```text
src/marketing_mcp/security
src/marketing_mcp/mcp
src/marketing_mcp/storage
src/marketing_mcp/jobs
src/marketing_mcp/schemas
```

- [ ] **Step 4: Run type check and fix real boundary errors without mass `ignore` directives**

```bash
uv run pyright
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pyrightconfig.json src tests
git commit -m "chore(types): add boundary type checking"
```

---

### Task 4: Create bounded PR CI

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`

**Required jobs:**

```text
lint-and-types
unit-contract
mcp-integration
security-contract
package-smoke
docker-smoke
docs-and-capability-drift
```

- [ ] **Step 1: Use a frozen install in every job**

```yaml
- run: uv sync --frozen --extra dev
```

- [ ] **Step 2: Run deterministic fast test groups**

```bash
uv run pytest tests/unit tests/contract -q
uv run pytest tests/integration/test_mcp_protocol.py tests/integration/test_mcp_auth_http.py -q
uv run pytest tests/release/test_g0_production_truth.py -q
```

- [ ] **Step 3: Add security-specific tests as soon as the H1/H2 files land**
- [ ] **Step 4: Build wheel/sdist and install wheel into a clean venv**
- [ ] **Step 5: Build Docker image with no production secrets**
- [ ] **Step 6: Fail on docs/capability/readiness drift**
- [ ] **Step 7: Upload JUnit and evidence artifacts on failure**
- [ ] **Step 8: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml
git commit -m "ci: add bounded production hardening checks"
```

---

### Task 5: Create dedicated statistical nightly workflow

**Files:**
- Create: `.github/workflows/statistical.yml`
- Modify: `scripts/collect_release_evidence.py`

**Matrix:**

```text
single-dimension MMM
multidimensional MMM
channel-specific transform config
flighting
CLV real models
model comparison
calibration/lineage
save-load invariants
```

- [ ] **Step 1: Run fixed-seed statistical tests with controlled CPU/thread counts**

```yaml
env:
  OMP_NUM_THREADS: "1"
  MKL_NUM_THREADS: "1"
```

- [ ] **Step 2: Do not use automatic retries for stochastic failures**
- [ ] **Step 3: Save dependency versions, machine metadata and per-test duration**
- [ ] **Step 4: Generate a statistical evidence artifact tied to SHA**
- [ ] **Step 5: Commit**

```bash
git add .github/workflows/statistical.yml scripts/collect_release_evidence.py
git commit -m "ci(statistical): add nightly decision-grade evidence suite"
```

---

### Task 6: Add security and supply-chain CI

**Files:**
- Create: `.github/workflows/security.yml`
- Modify: `Dockerfile` as findings require
- Create: `docs/security/CI-POLICY.md`

**Checks:**

- dependency vulnerability audit
- secret scanning
- Python static security scan
- container vulnerability scan
- SBOM generation
- forbidden raw credential patterns in dashboard artifacts

- [ ] **Step 1: Define severity policy that fails CI instead of only reporting**
- [ ] **Step 2: Add a repository scan that rejects committed `keyHash: fullSecret`, API keys, JWT secrets and known secret prefixes in fixtures outside explicit test snapshots**
- [ ] **Step 3: Produce SPDX/CycloneDX SBOM for release builds**
- [ ] **Step 4: Commit**

```bash
git add .github/workflows/security.yml docs/security Dockerfile dashboard
git commit -m "ci(security): add supply-chain and credential leak gates"
```

---

### Task 7: Add upstream compatibility canary

**Files:**
- Create: `.github/workflows/upstream-canary.yml`
- Create: `scripts/compatibility_canary.py`
- Modify: `docs/API-COMPATIBILITY.md`
- Test: `tests/integration/test_upstream_canary_contract.py`

**Lanes:**

```text
locked: exact uv.lock
latest-allowed: newest versions satisfying declared bounds
pre-release: optional non-blocking visibility lane
```

- [ ] **Step 1: Canary adapter imports/constructors**
- [ ] **Step 2: Run minimal real MMM fit/save/load**
- [ ] **Step 3: Run MCP discovery and authenticated roundtrip**
- [ ] **Step 4: Detect output-shape/API drift explicitly**
- [ ] **Step 5: Never auto-widen dependency constraints from a passing canary**
- [ ] **Step 6: Commit**

```bash
git add .github/workflows/upstream-canary.yml scripts/compatibility_canary.py docs/API-COMPATIBILITY.md tests/integration/test_upstream_canary_contract.py
git commit -m "ci(canary): continuously test upstream compatibility"
```

---

### Task 8: Build release workflow around immutable identity

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `scripts/collect_release_evidence.py`
- Modify: `scripts/verify_release_identity.py`

- [ ] **Step 1: Require G0-G5 plus H0-H6 and Agent Quality Gate**
- [ ] **Step 2: Build wheel/sdist and container from the same checkout**
- [ ] **Step 3: Record SHA256 for wheel/sdist and image digest**
- [ ] **Step 4: Run clean-install and container MCP smoke tests**
- [ ] **Step 5: Generate release evidence before publish**
- [ ] **Step 6: Reject publishing the same version with different hashes**
- [ ] **Step 7: Commit**

```bash
git add .github/workflows/release.yml scripts
git commit -m "ci(release): bind artifacts to verified commit evidence"
```

---

### Task 9: Establish H0 Runtime Truth gate

**Files:**
- Create: `tests/release/test_h0_runtime_truth.py`
- Modify: `docs/PRODUCTION-READINESS.md`

**Assertions:**

```text
readiness status is renderable from evidence
all green gates reference current SHA
capability inventory equals MCP discovery
package/runtime/docs version agree
required workflows exist
current evidence file contains executed command results
no stale root findings present as current truth
```

- [ ] **Step 1: Write release assertions**
- [ ] **Step 2: Run**

```bash
uv run pytest tests/release/test_g0_production_truth.py tests/release/test_h0_runtime_truth.py -v
```

- [ ] **Step 3: Render readiness from evidence**
- [ ] **Step 4: Commit**

```bash
git add tests/release docs/PRODUCTION-READINESS.md
git commit -m "test(release): establish runtime truth hardening gate"
```

## Acceptance Criteria

This plan is complete when:

- current-head evidence is machine-readable and reproducible enough to audit
- readiness cannot become green without executable evidence
- every PR runs bounded correctness/security/package checks
- real statistical behavior runs in dedicated protected/nightly CI
- upstream compatibility is continuously visible
- release artifacts are cryptographically tied to the verified commit
- H0 can be evaluated without hand-editing status text
