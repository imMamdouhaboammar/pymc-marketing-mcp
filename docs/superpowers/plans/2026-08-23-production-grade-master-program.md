# Production-Grade Master Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinate the complete stabilization of PyMC Marketing MCP from the current v0.4.x codebase into a release-candidate production service with verified scientific behavior, secure remote access, recoverable long-running jobs, durable state, CI evidence, and executable agent evals.

**Architecture:** Treat stabilization as a dependency-ordered program rather than one large refactor. Each workstream has an independent plan and an acceptance gate. No new public statistical capability is added until the scientific correctness and production truth gates are green.

**Tech Stack:** Python 3.12+, PyMC-Marketing 1.0.0, PyMC 6, MCP Python SDK 2.x, Pydantic 2.12, SQLite local storage, PostgreSQL production metadata, GCS production artifacts, Uvicorn/Starlette, pytest, Ruff, OpenTelemetry, GitHub Actions, Cloud Build.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Preserve the diagnostics decision gate before simulation or optimization.
- Do not permit arbitrary Python or user-supplied PyMC execution.
- Keep stdio local mode lightweight.
- Production HTTP must fail closed when authentication is unavailable.
- Release-critical statistical claims require real PyMC-Marketing tests.
- Any tool description, README claim, skill instruction, or dashboard copy must match current verified behavior.
- Do not add unrelated model families before Gate G5 is green.
- Every task must end in tests and a reviewable commit.

---

## Program Worktree

Implementation should start from an isolated worktree or equivalent isolated branch using:

```bash
git fetch origin
git worktree add ../pymc-marketing-mcp-prod -b feat/production-grade-stabilization origin/main
cd ../pymc-marketing-mcp-prod
uv sync --extra dev
```

Record the baseline before edits:

```bash
uv run pytest -n auto -v
uv run pytest -m statistical -v
uv run ruff check src tests
uv build
uv run marketing-mcp-demo --fast
```

Save the exact command outputs or CI links in `docs/release-evidence/` during execution.

---

## Wave 0: Freeze and Baseline

### Task 0.1: Declare the stabilization freeze

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Create: `docs/PRODUCTION-READINESS.md`

**Produces:** A visible statement that new capability work is paused until scientific and production gates pass.

- [x] Add `Production readiness` wording to README that describes the current release as advanced beta or release candidate rather than production-grade.
- [x] Add an unreleased changelog section named `Stabilization Program`.
- [x] Create `docs/PRODUCTION-READINESS.md` with the G0 through G5 gates copied from the stabilization spec.
- [ ] Run markdown link checks used by the repository, or add a link-check task under the CI plan if none exists yet.
- [x] Commit:

```bash
git add README.md CHANGELOG.md docs/PRODUCTION-READINESS.md
git commit -m "docs: declare production stabilization gates"
```

### Task 0.2: Capture current-head evidence

**Files:**
- Create: `docs/release-evidence/v0.4-current-head.md`

**Produces:** A non-handwritten baseline record derived from command output.

- [x] Run the full fast suite and record pass/fail count.
- [x] Run the current statistical suite separately.
- [x] Run Ruff and build.
- [x] Run MCP stdio and HTTP integration tests.
- [x] Record current Python, PyMC-Marketing, PyMC, ArviZ, MCP, xarray, and h5netcdf versions from the active lock.
- [x] Record the commit SHA used for all commands.
- [x] Do not label unexecuted v0.4 phases as verified.
- [x] Commit the evidence file.

---

## Wave 1: Production Truth

Execute:

`docs/superpowers/plans/2026-08-23-production-truth-release-discipline.md`

Exit gate: G0.

No scientific API changes begin until G0 is green.

---

## Wave 2: Scientific Contract Hardening

Execute:

`docs/superpowers/plans/2026-08-23-scientific-contract-hardening.md`

Exit gate: G1.

Required outcomes:
- channel-specific configuration is behaviorally real
- model comparison semantics are correct
- CLV APIs are model-specific
- dynamic flighting is either a true optimization or explicitly renamed as heuristic
- plotting aggregation is dimension-safe

---

## Wave 3: MCP Boundary Refactor

Execute the MCP boundary section in:

`docs/superpowers/plans/2026-08-23-security-mcp-hardening.md`

Exit condition:
- `src/marketing_mcp/mcp/server.py` becomes orchestration only
- tool groups register from focused modules
- auth context and tool scopes have stable interfaces
- MCP discovery snapshot is tested

---

## Wave 4: Security

Continue:

`docs/superpowers/plans/2026-08-23-security-mcp-hardening.md`

Exit gate: G3 security subset that does not depend on jobs/storage.

Required outcomes:
- no query-string credentials
- production remote mode fails closed
- principal and scope information reaches tool execution
- secrets never appear in logs or error envelopes

---

## Wave 5: Jobs and Durable State

Execute:

`docs/superpowers/plans/2026-08-23-jobs-storage-recovery.md`

Exit gate: G2.

Required outcomes:
- expensive statistical calls submit jobs
- jobs survive restart
- cancellation is persisted
- metadata uses production database adapter in production mode
- artifacts use object storage adapter in production mode
- restart and backup/restore tests pass

---

## Wave 6: Observability and CI

Execute:

`docs/superpowers/plans/2026-08-23-observability-ci-release.md`

Exit gates: G4 and G5.

Required outcomes:
- structured logs, metrics, traces
- readiness and dependency health
- PR, nightly, and compatibility canary workflows
- wheel and container smoke tests
- release evidence generated by CI

---

## Wave 7: Agent Skills and Evals

Execute:

`docs/superpowers/plans/2026-08-23-agent-skills-evals.md`

Exit condition:
- every skill capability maps to a current tool contract
- evals run rather than contain pre-marked pass values
- negative scenarios protect diagnostics and causal claims
- tool trace assertions prove behavior

---

## Wave 8: Release Candidate

### Task 8.1: Build the release candidate evidence pack

**Files:**
- Create: `docs/release-evidence/v0.5.0-rc1.md`
- Update: `docs/PRODUCTION-READINESS.md`
- Update: `docs/API-COMPATIBILITY.md`
- Update: `docs/FINAL-REVIEW.md`

**Acceptance commands:**

```bash
uv sync --frozen --extra dev
uv run ruff check src tests
uv run pytest -n auto -v
uv run pytest -m statistical -v
uv build
python -m venv /tmp/pymc-mcp-wheel-test
/tmp/pymc-mcp-wheel-test/bin/pip install dist/*.whl
/tmp/pymc-mcp-wheel-test/bin/marketing-mcp --help
docker build -t pymc-marketing-mcp:rc .
```

Then execute HTTP auth, restart recovery, migration, and job-cancellation integration tests.

### Task 8.2: Production readiness review

Review each invariant from the spec. Any failed invariant blocks release.

Required sign-off categories:
- scientific correctness
- MCP contract correctness
- security
- state recovery
- compute control
- observability
- CI and release
- agent behavior

### Task 8.3: Version and package release

Only after the evidence pack is green:

- bump one version source of truth to `0.5.0`
- generate derived version references
- build wheel and image from the same commit
- tag the exact commit
- publish the release notes generated from the verified changelog

---

## Cross-Program Acceptance Matrix

| Capability | Unit | Contract | Integration | Statistical | Agent Eval | Release Blocker |
|---|---:|---:|---:|---:|---:|---:|
| Dataset ingest | yes | yes | yes | no | yes | yes |
| MMM fit | yes | yes | yes | yes | yes | yes |
| Diagnostics | yes | yes | yes | yes | yes | yes |
| Contributions/iROAS | yes | yes | yes | yes | yes | yes |
| Budget simulation | yes | yes | yes | yes | yes | yes |
| Budget optimization | yes | yes | yes | yes | yes | yes |
| Flighting | yes | yes | yes | yes | yes | yes |
| Calibration | yes | yes | yes | yes | yes | yes |
| CLV | yes | yes | yes | yes | yes | yes |
| Model comparison | yes | yes | yes | yes | yes | yes |
| Plot resources | yes | yes | yes | yes | no | yes |
| Auth/scopes | yes | yes | yes | no | yes | yes |
| Jobs | yes | yes | yes | no | yes | yes |
| Persistence/restart | yes | yes | yes | no | no | yes |
| Observability | yes | yes | yes | no | no | yes |

---

## Stop Conditions

Stop implementation and open a focused investigation when any of the following occurs:

1. A PyMC-Marketing 1.0 API behaves differently from repository documentation.
2. A statistical test passes only by weakening the diagnostics gate.
3. Flighting optimization cannot preserve weekly state through the official response API.
4. Postgres/object storage introduces non-deterministic model identity.
5. OAuth implementation requires a protocol behavior inconsistent with the pinned MCP SDK.
6. A migration can orphan or overwrite an existing model artifact.

The investigation must produce either a corrected design or an explicit capability downgrade before execution resumes.

---

## Final Definition of Done

This master program is complete when:

- G0 through G5 are green
- no public capability has contract-to-behavior drift
- all release-critical statistical operations have real statistical tests
- production HTTP is authenticated and scoped
- sampling operations are recoverable jobs
- cloud state survives restart
- operator signals and runbooks exist
- CI creates release evidence
- agent skills are executable-eval backed
- the release candidate can be installed and exercised from a clean environment