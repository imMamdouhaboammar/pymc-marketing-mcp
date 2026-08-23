# Production Truth and Release Discipline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one verifiable source of truth for versioning, capability inventory, compatibility, documentation claims, and release evidence before any further feature work.

**Architecture:** Keep package metadata canonical and derive human-facing version references and capability inventories from code. Add tests that compare MCP discovery, docs, and package metadata so drift becomes a failing build rather than a manual review problem.

**Tech Stack:** Python 3.12+, importlib.metadata, MCP SDK discovery client, pytest, Ruff, hatchling/uv, GitHub Actions in the later CI plan.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Current release claims must be reduced when behavior is not verified.
- No file may independently hardcode the release version unless generated from the canonical version.
- Release evidence must come from executed commands.
- Existing historical release documents remain historical records and must not be silently rewritten as current evidence.

---

### Task 1: Create a canonical runtime version API

**Files:**
- Modify: `src/marketing_mcp/__init__.py`
- Modify: `src/marketing_mcp/cli.py`
- Test: `tests/unit/test_version_contract.py`

**Interfaces:**
- Produces: `marketing_mcp.__version__: str`
- Produces: `marketing_mcp.version_info() -> dict[str, str | None]`

- [x] Write a failing test asserting the health endpoint uses `marketing_mcp.__version__` rather than a literal.
- [x] Write a failing test asserting `version_info()` includes the application version and installed PyMC-Marketing version.
- [x] Implement `version_info()` using `importlib.metadata` and safe missing-package handling.
- [x] Replace the `"0.4.0"` literal in the health response with `__version__`.
- [x] Run:

```bash
uv run pytest tests/unit/test_version_contract.py -v
uv run pytest tests/integration/test_http_health.py -v
```

- [x] Commit:

```bash
git add src/marketing_mcp/__init__.py src/marketing_mcp/cli.py tests/unit/test_version_contract.py
git commit -m "fix: centralize runtime version reporting"
```

### Task 2: Add a generated capability inventory

**Files:**
- Create: `src/marketing_mcp/capabilities.py`
- Create: `scripts/generate_capability_inventory.py`
- Create: `tests/integration/test_capability_inventory.py`
- Generate: `docs/CAPABILITIES.md`

**Interfaces:**
- Produces: `Capability` Pydantic/dataclass record with `name`, `kind`, `domain`, `status`, `decision_gate_required`, `evidence_test_ids`.
- Produces: `get_capability_inventory() -> list[Capability]`.

- [x] Define an explicit capability record for every MCP tool and resource.
- [x] Mark unverified capabilities as `experimental` rather than `stable`.
- [x] Generate `docs/CAPABILITIES.md` from this registry.
- [x] Add an integration test that starts the MCP server and compares discovered tool/resource names with the inventory.
- [x] Fail if a discovered tool has no capability record or a stable capability has no evidence-test reference.
- [x] Run:

```bash
uv run pytest tests/integration/test_capability_inventory.py -v
uv run pytest tests/unit/test_capability_rules.py tests/unit/test_capability_evidence.py tests/unit/test_capabilities_doc.py -v
uv run python scripts/generate_capability_inventory.py --check
uv run pytest -m statistical -q  # evidence cited by stable capabilities
```

- [x] Commit the registry, generator, generated document, and tests.

### Task 3: Separate historical review from current release evidence

**Files:**
- Preserve: `docs/FINAL-REVIEW.md` as historical v0.3 evidence or rename it with git history preservation if desired.
- Create: `docs/release-evidence/README.md`
- Create: `scripts/collect_release_evidence.py`
- Test: `tests/unit/test_release_evidence.py`

**Interfaces:**
- Produces: `collect_release_evidence(commit_sha: str) -> dict`.

- [x] Define the evidence schema: commit SHA, timestamp, platform, Python version, dependency versions, commands, exit codes, test counts, artifact hashes.
- [x] Write tests for deterministic JSON serialization and secret redaction.
- [x] Implement command-result ingestion from CI environment variables and machine-readable pytest/build output where available.
- [x] Generate a Markdown summary from the JSON evidence object.
- [x] Document that manually edited pass/fail claims are not release evidence.
- [x] Commit.

### Task 4: Add documentation drift checks

**Files:**
- Create: `scripts/check_docs_drift.py`
- Test: `tests/unit/test_docs_drift.py`
- Modify: `README.md`
- Modify: `docs/API-COMPATIBILITY.md`
- Modify: `docs/TOOL-CONTRACTS.md`

**Checks:**
- version references match canonical version or are explicitly historical
- tool names in tool-contract docs exist in capability inventory
- documented supported adstock/saturation names exist in schemas
- documented transport names exist in CLI choices
- documented decision-gated tools match code policy

- [x] Write one failing fixture per drift type.
- [x] Implement the checker as a pure Python script returning non-zero on drift.
- [x] Update current docs to pass the checker while downgrading unverified claims.
- [x] Run:

```bash
uv run python scripts/check_docs_drift.py
uv run pytest tests/unit/test_docs_drift.py tests/unit/test_agents_commands.py -v
```

- [x] Commit.

### Task 5: Pin the release packaging contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `Dockerfile`
- Modify: `scripts/deploy_cloud_run.sh`
- Modify: `cloudbuild.yaml`
- Create: `scripts/verify_release_identity.py`
- Test: `tests/unit/test_release_identity.py`

**Contract:**
- one application version
- one git commit identity
- image labels include version and commit
- wheel metadata version matches runtime version
- deployment scripts do not invent an independent default tag

- [x] Add OCI labels to Docker image for source revision and application version using build args.
- [x] Remove fixed `v0.5.0` default image tag from deployment script.
- [x] Require image tag or derive it from canonical package version and commit.
- [x] Add tests for tag derivation and invalid version mismatch.
- [x] Add a verification script that inspects built wheel metadata and supplied image metadata inputs.
- [x] Commit.

### Task 6: Establish Gate G0

**Files:**
- Modify: `docs/PRODUCTION-READINESS.md`
- Create: `tests/release/test_g0_production_truth.py`

- [ ] Test that runtime, package, capability inventory, and docs are consistent.
- [ ] Test that every stable capability has at least one referenced executable evidence test.
- [ ] Test that all current MCP tools are present in `docs/TOOL-CONTRACTS.md`.
- [ ] Test that historical documents are marked with their historical version.
- [ ] Run the full fast suite.
- [ ] Mark G0 green only from CI evidence.

## Acceptance Criteria

This plan is complete when:

- health endpoint and package expose the same version
- capability inventory equals actual MCP discovery
- unverified v0.4 capabilities are visibly experimental
- docs drift fails tests
- deployment image identity is tied to package/commit identity
- a machine-generated current-head release evidence document exists
- Gate G0 is green