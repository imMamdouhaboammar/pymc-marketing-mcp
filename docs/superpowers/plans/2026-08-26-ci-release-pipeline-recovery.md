# CI and Release Pipeline Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub Actions execute reliably on the exact candidate commit and produce trustworthy release evidence before any public beta tag is published.

**Architecture:** First isolate why jobs currently terminate before steps run, then reduce the release-critical workflows to supported, pinned actions and deterministic uv environments. After bootstrap recovery, require core CI, security, statistical evidence, upstream canary, same-SHA package/container builds, and release evidence before publication.

**Tech Stack:** GitHub Actions, actions/checkout, astral-sh/setup-uv, Docker Buildx, pytest, Ruff, Pyright, uv, TruffleHog, pip-audit, CycloneDX, GitHub Releases

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- Current baseline SHA is `1c7fed0af32f9162d840f292a40a557b412978f9`
- A workflow definition existing in the repository is not evidence; the workflow must run and finish green
- Release-critical jobs must not use floating action refs such as `@main`
- The release must test and publish artifacts from one exact commit
- Statistical evidence must run separately from fast PR tests but must be attached to the release candidate
- Do not weaken tests merely to obtain a green workflow

---

## Task 1: Reproduce the zero-step GitHub Actions failure

**Files:**
- Inspect: `.github/workflows/ci.yml`
- Inspect: `.github/workflows/security.yml`
- Inspect: `.github/workflows/trufflehog.yml`
- Inspect: `.github/workflows/statistical.yml`
- Inspect: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: GitHub workflow-run metadata
- Produces: classified bootstrap failure with one reproducible fix

- [ ] **Step 1: Inspect current failed workflow runs**

Confirm that failed jobs show `steps: []`, `runner_id: 0`, and complete within seconds. Record run IDs in the implementation PR description.

- [ ] **Step 2: Validate workflow YAML locally**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml
for path in Path('.github/workflows').glob('*.yml'):
    yaml.safe_load(path.read_text())
    print('OK', path)
PY
```

Expected: every workflow parses successfully

- [ ] **Step 3: Check repository/action-policy causes before changing tests**

Verify GitHub Actions is enabled for the repository and determine whether the account/repository restricts third-party actions. If third-party actions are restricted, either explicitly allow the pinned actions used by this repository or replace them with shell commands running installed tools.

- [ ] **Step 4: Commit only the minimum bootstrap fix**

```bash
git add .github/workflows
git commit -m "ci: restore GitHub Actions bootstrap"
```

## Task 2: Pin every release-critical action

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/security.yml`
- Modify: `.github/workflows/trufflehog.yml`
- Modify: `.github/workflows/statistical.yml`
- Modify: `.github/workflows/upstream-canary.yml`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: supported GitHub Marketplace actions
- Produces: deterministic action references

- [ ] **Step 1: Remove floating refs from security workflows**

Replace `trufflesecurity/trufflehog@main` with a reviewed immutable release tag or commit SHA approved for this repository.

- [ ] **Step 2: Keep setup actions on explicit supported major versions**

The minimum allowed references are:

```text
actions/checkout@v4
astral-sh/setup-uv@v5
docker/setup-buildx-action@v3
docker/build-push-action@v6
actions/upload-artifact@v4
softprops/action-gh-release@v2
```

If repository policy requires commit-SHA pinning, pin all of these to reviewed SHAs instead of major tags.

- [ ] **Step 3: Add action-pin review notes**

Document the selected refs in the implementation PR and record when they should be reviewed again.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows
git commit -m "ci: pin release-critical actions"
```

## Task 3: Make the core CI lane deterministic

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` only if CI reveals a real dependency declaration defect
- Test: existing `tests/unit`, `tests/contract`, `tests/evals`, `tests/integration`, `tests/release`

**Interfaces:**
- Consumes: `uv.lock`, Python 3.12
- Produces: six independently green core CI jobs

- [ ] **Step 1: Verify frozen environment installation**

Run locally:

```bash
uv sync --frozen --extra dev
```

Expected: exit code `0`

- [ ] **Step 2: Execute exactly the CI commands locally**

Run:

```bash
uv run ruff check src tests scripts
uv run pyright
uv run python scripts/check_docs_drift.py
uv run python scripts/generate_capability_inventory.py --check
uv run python scripts/render_production_readiness.py --check
uv run pytest tests/unit tests/contract tests/evals -q -m "not statistical"
uv run pytest tests/integration -q -m "not statistical"
uv run pytest tests/release/test_g0_production_truth.py tests/release/test_h0_runtime_truth.py -q -m "not statistical"
uv build
```

Expected: every command exits `0`

- [ ] **Step 3: Add a clean-wheel smoke assertion**

After `uv build`, create a fresh environment, install only the built wheel, and run:

```bash
marketing-mcp --help
marketing-mcp-demo --help
marketing-mcp-auth --help
marketing-mcp-worker --help
```

Expected: all commands exit `0`

- [ ] **Step 4: Run Docker build smoke from the same source checkout**

Run:

```bash
docker build -t pymc-marketing-mcp:ci-test .
```

Expected: successful image build

- [ ] **Step 5: Commit any real CI/environment fixes**

```bash
git add .github/workflows/ci.yml pyproject.toml uv.lock
git commit -m "ci: make core verification deterministic"
```

## Task 4: Harden security and supply-chain CI

**Files:**
- Modify: `.github/workflows/security.yml`
- Modify: `.github/workflows/trufflehog.yml`
- Create: `scripts/check_forbidden_secret_patterns.py`
- Test: `tests/unit/test_secret_pattern_check.py`

**Interfaces:**
- Consumes: repository checkout and dependency lock
- Produces: deterministic secret scan, dependency audit, and SBOM

- [ ] **Step 1: Write a failing unit test for forbidden secret-pattern scanning**

Test cases must include the historical browser persistence shape `keyHash: fullSecret`, raw `mcp_live_` values in tracked fixture text, and benign prefixes without complete secrets.

- [ ] **Step 2: Implement the scanner as a Python script**

The script must return non-zero when a forbidden complete secret pattern is present and zero for safe prefixes/documentation examples.

- [ ] **Step 3: Replace grep-only policy with the tested scanner**

Run in CI:

```bash
uv run python scripts/check_forbidden_secret_patterns.py
```

- [ ] **Step 4: Keep TruffleHog as an independent second layer**

Use the pinned reviewed action and `--only-verified`; do not rely on it as the only secret-control mechanism.

- [ ] **Step 5: Make dependency audit use the project environment**

Install `pip-audit` into the CI tool environment and audit the resolved production dependencies. A vulnerability waiver must be a reviewed repository artifact with package, CVE, reason, compensating control, and expiry date.

- [ ] **Step 6: Generate CycloneDX SBOM and upload it**

The artifact name must include `${{ github.sha }}`.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/security.yml .github/workflows/trufflehog.yml scripts/check_forbidden_secret_patterns.py tests/unit/test_secret_pattern_check.py
git commit -m "ci: harden security and supply-chain verification"
```

## Task 5: Correct the statistical workflow fan-out

**Files:**
- Modify: `.github/workflows/statistical.yml`
- Modify or create: `scripts/run_statistical_suite.py`
- Test: `tests/unit/test_statistical_suite_router.py`

**Interfaces:**
- Consumes: named statistical suite from the matrix
- Produces: each matrix job runs only its intended tests instead of the entire statistical suite six times

- [ ] **Step 1: Write the suite-to-test mapping test**

Define exact mappings for:

```text
mmm
flighting
clv
model-selection
calibration
serialization
```

Each suite must resolve to at least one existing statistical test path and no unknown suite may silently run all tests.

- [ ] **Step 2: Implement the suite router**

Example invocation:

```bash
uv run python scripts/run_statistical_suite.py mmm
```

The script must call pytest with the exact path set for that suite.

- [ ] **Step 3: Change the matrix values to stable machine names**

Use the six names above, and pass `${{ matrix.suite }}` to the router.

- [ ] **Step 4: Collect evidence once per matrix job**

Evidence must include suite name, exact SHA, dependency versions, test count, failures, and duration.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/statistical.yml scripts/run_statistical_suite.py tests/unit/test_statistical_suite_router.py
git commit -m "ci: make statistical matrix suites explicit"
```

## Task 6: Make release workflow prove one artifact identity

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `scripts/collect_release_evidence.py`
- Test: `tests/release/test_release_artifact_identity.py`

**Interfaces:**
- Consumes: exact release commit
- Produces: wheel, sdist, container digest, SBOM, checksums, release evidence, provenance record

- [ ] **Step 1: Write the failing release identity test**

The evidence schema must require:

```json
{
  "commit_sha": "40-hex-sha",
  "package_version": "semver",
  "wheel_sha256": "64-hex-digest",
  "sdist_sha256": "64-hex-digest",
  "container_digest": "sha256:...",
  "sbom_artifact": "non-empty",
  "ci_run_id": "non-empty"
}
```

- [ ] **Step 2: Build package and container from the checked-out tag commit**

The workflow must not check out a second branch or rebuild from an unpinned ref.

- [ ] **Step 3: Smoke-test the built container**

Start the container in a non-production local profile and verify `/health/live`, `/health/ready`, and MCP initialize/list-tools.

- [ ] **Step 4: Generate checksums and provenance**

At minimum produce SHA-256 checksums and an evidence JSON bound to `${{ github.sha }}`. If GitHub artifact attestations are enabled for the repository, generate an attestation for the package and container.

- [ ] **Step 5: Prevent publish when evidence is incomplete**

`softprops/action-gh-release` must run only after verification, build, smoke, security inputs, and evidence generation succeed.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/release.yml scripts/collect_release_evidence.py tests/release/test_release_artifact_identity.py
git commit -m "release: bind evidence to package and container identity"
```

## Task 7: Require the CI gates on main

**Files:**
- Repository settings / branch protection
- Document: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: stable workflow check names
- Produces: protected main branch

- [ ] **Step 1: Stabilize required check names**

Required minimum checks:

```text
Lint, Types & Docs Drift
Unit & Contract Tests
MCP Protocol & Integration Tests
Release Truth Gates
Package & Build Smoke
Docker Build Smoke
Security & Supply Chain
```

- [ ] **Step 2: Configure main branch protection**

Require pull requests and the release-critical status checks. Do not require scheduled-only statistical jobs on every PR; require their evidence before release tagging instead.

- [ ] **Step 3: Record governance in readiness docs**

Document the exact required checks and release-only checks.

## Acceptance criteria

This plan is complete only when:

- a new commit on the implementation branch starts GitHub Actions jobs normally
- all six core CI jobs execute steps and pass
- security, secret scanning, and SBOM workflows pass
- the statistical matrix runs distinct suites rather than the full suite six times
- package and Docker smoke tests pass from the same SHA
- release evidence records exact SHA, dependency versions, package hashes, and container digest
- a failed mandatory check prevents publication
- main branch protection requires the stable release-critical checks
