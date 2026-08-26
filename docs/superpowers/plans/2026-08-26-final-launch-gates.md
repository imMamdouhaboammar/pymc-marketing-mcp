# Final Launch Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and enforce the final GO/NO-GO process for local beta, authenticated remote beta, release candidate, and production GA so the repository cannot call itself released based on partial or stale evidence.

**Architecture:** Convert launch approval into a machine-verifiable evidence manifest plus a small human operational review. Beta and GA use different mandatory gate sets, but every waived GA-only condition must be explicit in beta release notes. Publication is a terminal step after verification, not a trigger that performs verification after the fact.

**Tech Stack:** GitHub Actions, pytest release gates, release evidence JSON/Markdown, Docker, package smoke tests, statistical suite, security scans, SBOM, branch protection, operational runbooks

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- No launch decision uses evidence from a different commit than the candidate
- No mandatory gate may be manually marked green without machine evidence
- Public beta release notes must disclose any accepted beta-only limitations
- GA may not waive external persistence, durable worker separation, production identity, backup/restore, or exact-artifact provenance
- Experimental capabilities remain labeled experimental in release docs
- A red mandatory GitHub check means NO-GO
- A security finding with plausible credential, tenant-isolation, or remote-auth impact means NO-GO until triaged and resolved or formally proven non-applicable

---

## Task 1: Define the launch evidence manifest

**Files:**
- Create: `src/marketing_mcp/release/manifest.py`
- Modify: `scripts/collect_release_evidence.py`
- Test: `tests/release/test_launch_manifest.py`

**Interfaces:**
- Consumes: CI run outputs, test summaries, package/container identities
- Produces: `LaunchEvidenceManifest`

- [ ] **Step 1: Write schema tests**

The manifest must reject missing or malformed values for:

```text
commit_sha
version
release_tier
ci_run_id
core_ci_status
security_status
statistical_status
upstream_canary_status
package_hashes
container_digest
sbom_reference
capability_inventory_hash
production_readiness_hash
```

- [ ] **Step 2: Define release tiers as an enum**

Exact values:

```text
beta-local
beta-remote
rc
production-ga
```

- [ ] **Step 3: Encode mandatory gates by tier**

`beta-local` requires package/local verification. `beta-remote` additionally requires remote auth/tenant/security/Docker verification. `rc` requires the full candidate matrix. `production-ga` additionally requires production persistence, external worker, production identity, backup/restore, operability, and provenance.

- [ ] **Step 4: Make collector write deterministic JSON**

Sort keys, record UTC collection time, and include the exact git SHA returned by git/GitHub rather than a user-supplied arbitrary string.

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/release/manifest.py scripts/collect_release_evidence.py tests/release/test_launch_manifest.py
git commit -m "feat: define machine-verifiable launch manifest"
```

## Task 2: Add the public-beta release gate

**Files:**
- Create: `tests/release/test_beta_launch_gate.py`
- Modify: `.github/workflows/release.yml`
- Modify: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: launch manifest with `beta-remote`
- Produces: beta GO/NO-GO result

- [ ] **Step 1: Encode mandatory beta blockers**

The test must fail if any of these are false:

```text
core CI green
security/secret scan green
package clean-install green
Docker smoke green
remote API-key auth E2E green
scope denial E2E green
tenant tool denial E2E green
tenant resource denial E2E green
credential revocation E2E green
capability/docs drift green
no unresolved P0 launch finding
```

- [ ] **Step 2: Encode worker capability rule**

If `submit_fit_mmm_job` is stable, external-worker restart evidence is mandatory. If that evidence is absent, beta can proceed only when the capability is marked experimental or excluded from the advertised stable set.

- [ ] **Step 3: Add beta limitation fields**

If beta uses SQLite/local artifacts, release notes must state `single-instance beta persistence` and the deployment docs must not recommend horizontal API scaling.

- [ ] **Step 4: Wire the gate before the publish step**

Run:

```bash
uv run pytest tests/release/test_beta_launch_gate.py -q
```

Expected: release job stops before publication on failure

- [ ] **Step 5: Commit**

```bash
git add tests/release/test_beta_launch_gate.py .github/workflows/release.yml docs/PRODUCTION-READINESS.md
git commit -m "release: enforce public beta launch gate"
```

## Task 3: Add production-GA gate

**Files:**
- Create: `tests/release/test_production_ga_gate.py`
- Modify: `.github/workflows/release.yml`
- Modify: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: `production-ga` launch manifest
- Produces: GA GO/NO-GO result

- [ ] **Step 1: Require all beta/RC checks**

GA inherits every remote-beta and RC mandatory check.

- [ ] **Step 2: Require production persistence evidence**

Mandatory evidence:

```text
external metadata provider contract green
object storage contract green
fresh-instance persistence lifecycle green
backup/restore drill green
artifact reconciliation green
```

- [ ] **Step 3: Require durable compute evidence**

Mandatory evidence:

```text
API exits after durable submission
standalone worker completes job
fresh API reads persisted result
atomic worker claim test green
worker heartbeat readiness test green
```

- [ ] **Step 4: Require production identity evidence**

Mandatory evidence:

```text
external issuer/JWKS happy path green
wrong issuer/audience/expiry/signature tests green
missing tenant claim fails in multi-tenant mode
cross-tenant MCP tool and resource tests green
```

- [ ] **Step 5: Require operability evidence**

At minimum require production-configured trace exporter, alert routing test, readiness dependency failures, and documented runbooks for database outage, object storage outage, stuck worker, auth-provider failure, and rollback.

- [ ] **Step 6: Require artifact provenance**

Wheel/sdist hashes and container digest must bind to the same commit. SBOM must be attached. If repository supports artifact attestation/signing, require the attestation reference.

- [ ] **Step 7: Commit**

```bash
git add tests/release/test_production_ga_gate.py .github/workflows/release.yml docs/PRODUCTION-READINESS.md
git commit -m "release: enforce production GA gate"
```

## Task 4: Add release-candidate deployment smoke

**Files:**
- Create: `scripts/release_smoke.py`
- Create: `tests/integration/test_release_smoke_contract.py`
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: built candidate container
- Produces: remote-style MCP smoke result

- [ ] **Step 1: Define the smoke sequence**

The script must verify:

```text
GET /health/live -> 200
GET /health/ready -> 200
unauthenticated /mcp -> 401 when auth enabled
authenticated MCP initialize succeeds
list_tools returns the expected public tool count
read-only key cannot call decision tool
revoked key is rejected
```

- [ ] **Step 2: Avoid long statistical fitting in the release smoke**

The smoke verifies packaging/runtime/auth/protocol wiring. Full PyMC sampling remains in the statistical release lane.

- [ ] **Step 3: Execute against the built image, not source uvicorn**

Start the exact candidate container and run `release_smoke.py` against it.

- [ ] **Step 4: Commit**

```bash
git add scripts/release_smoke.py tests/integration/test_release_smoke_contract.py .github/workflows/release.yml
git commit -m "test: smoke the exact candidate container"
```

## Task 5: Add operational rollback criteria

**Files:**
- Create: `docs/runbooks/release-rollback.md`
- Create: `docs/runbooks/auth-outage.md`
- Create: `docs/runbooks/worker-stall.md`
- Create: `docs/runbooks/storage-outage.md`
- Modify: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: deployed release
- Produces: deterministic operator response to launch failure

- [ ] **Step 1: Define automatic rollback signals**

At minimum:

```text
readiness failure after deployment
MCP initialize failure above threshold
credential verification error spike
worker queue age above threshold
artifact integrity failures
new cross-tenant authorization failure
```

- [ ] **Step 2: Define rollback actions**

Include previous image digest/tag, database migration compatibility check, worker drain/stop procedure, and post-rollback verification commands.

- [ ] **Step 3: Define auth-provider outage behavior**

New OAuth sessions fail closed. Existing API keys continue only according to explicit deployment policy; never silently bypass auth.

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks docs/PRODUCTION-READINESS.md
git commit -m "docs: add launch rollback and outage runbooks"
```

## Task 6: Add branch and release governance

**Files:**
- Repository branch protection / ruleset settings
- Modify: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: stable GitHub check names
- Produces: main/release protection policy

- [ ] **Step 1: Protect `main`**

Require pull request review and the release-critical PR checks defined in the CI recovery plan.

- [ ] **Step 2: Prevent accidental direct release tags from unverified commits**

Document that release tags are created only after the exact commit has the required candidate evidence. Where repository rulesets support tag protection, protect `v*` release tags.

- [ ] **Step 3: Require signed or attested release artifacts where supported**

A raw Git tag alone is not provenance evidence.

- [ ] **Step 4: Record the policy in readiness docs**

## Task 7: Generate the final GO/NO-GO report

**Files:**
- Create through CI: release evidence JSON and Markdown
- Modify through generated tooling: `docs/PRODUCTION-READINESS.md`

**Interfaces:**
- Consumes: exact candidate evidence
- Produces: one release decision

- [ ] **Step 1: Compute, do not hand-write, gate status**

The report must list each mandatory gate as PASS/FAIL with evidence references.

- [ ] **Step 2: Include known limitations**

Beta example limitations may include single-instance persistence or experimental async jobs only if the beta gate permits them and the docs describe them accurately.

- [ ] **Step 3: Require zero mandatory failures for GO**

Any mandatory FAIL produces `NO-GO` and the release workflow exits non-zero before publication.

- [ ] **Step 4: Attach report to GitHub Release**

Attach evidence JSON/Markdown, SBOM, SHA256SUMS, wheel/sdist, and container digest/provenance reference.

## Beta GO checklist

A remote public beta is GO only when all are true:

- core GitHub CI executes and is green
- security and secret scans are green
- full required statistical evidence is green for stable statistical capabilities
- package clean install is green
- candidate Docker image smoke is green
- request-scoped HTTP identity works through real MCP
- scope and tenant denials work through real MCP tools/resources
- API-key issue/use/revoke path works E2E
- capability registry/docs/runtime have no known launch-relevant drift
- durable async job claims match actual maturity
- exact-commit launch manifest is complete

## GA GO checklist

Production GA additionally requires:

- external shared metadata backend
- external object storage
- API/worker execution separation
- worker claim/recovery/heartbeat evidence
- production external issuer verification
- backup/restore drill
- artifact reconciliation drill
- distributed tracing exporter
- production alert routing
- rollback/outage runbooks
- same-SHA wheel/container/SBOM/provenance
- protected main and release governance
- G0-G5, H0-H6, AQG all green on the exact GA commit

## Acceptance criteria

This plan is complete when the repository can produce a deterministic machine-generated `GO` or `NO-GO` for each release tier and GitHub cannot publish a release when a mandatory gate is red or missing
