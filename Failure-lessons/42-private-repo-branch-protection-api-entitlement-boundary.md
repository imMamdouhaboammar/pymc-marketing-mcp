# Lesson 42: Private Repository GitHub Branch Protection API Entitlement Boundary

### Context
Automated release governance and branch protection configuration for `main` in private GitHub repositories (Issue #11).

### What happened
An automated script/agent attempted to verify or enable branch protection rules on `main` via `gh api repos/:owner/:repo/branches/main/protection`. The API returned `HTTP 404: Branch not protected` (or `HTTP 403: Forbidden`), blocking automated scripts that assumed branch protection could be programmatically provisioned and audited via standard REST endpoints.

### Observable symptom
```text
$ gh api repos/imMamdouhaboammar/pymc-marketing-mcp/branches/main/protection
{
  "message": "Branch not protected",
  "status": "404"
}
gh: Branch not protected (HTTP 404)
```

### Impact
Issue #11 remained blocked as an unresolved release gate, creating the false impression that code changes were missing, when in fact the issue was purely an external GitHub account/plan entitlement boundary.

### Incorrect assumption
Assumed that GitHub branch protection and repository rulesets APIs are universally available and configurable programmatically across all repository tiers (free, private, organization).

### Root cause
**Confirmed**. GitHub restricts branch protection and ruleset API management on private repositories for personal free accounts; branch protection on private personal repos requires either repository visibility change to public or manual configuration via the GitHub web UI. Automated API calls cannot bypass this provider entitlement.

### Why the architecture allowed it
The release governance document treated external SaaS platform configuration identically to in-repo code artifacts, failing to distinguish between automated code verification gates and manual platform administration.

### Fix
1. Explicitly categorized Issue #11 as a **Platform Administrative Setting (Blocked on Owner Entitlement)**.
2. Hardened `.github/workflows/release.yml` with fail-closed cryptographic candidate SHA binding (`test "${TAG_SHA}" = "${CANDIDATE_SHA}"`) so that release integrity is enforced mathematically inside CI regardless of whether remote branch protection is active on GitHub.

### Verification
Release candidate workflow tests (`tests/release/test_candidate_provenance.py`) confirm that unverified or mismatched commits are rejected at the CI level.

### Prevention rule
> **Never make release candidates or CI suites depend on programmatic mutation of external SaaS administrative entitlements (like branch protection rules or IAM bindings). Always enforce supply-chain integrity fail-closed within the repository's own workflows (e.g. SHA-pinned release gates).**

### Reusable lesson
When auditing platform readiness, maintain a strict separation between "In-Repo Code Invariants" (which agents can fix and test) and "Host Platform Entitlements" (which require human owner decisions or administrative web UI actions).

### Related code
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `tests/release/test_candidate_provenance.py`

### Related tests
- `tests/release/test_candidate_provenance.py::test_release_checkout_is_bound_to_the_requested_candidate`

### Related lessons
- [01-fail-closed-anonymous-http-binding.md](./01-fail-closed-anonymous-http-binding.md)
- [31-mcp-protocol-inversion-and-admission-boundary.md](./31-mcp-protocol-inversion-and-admission-boundary.md)

### Status
Resolved (Mitigated via In-Repo CI Integrity Gates)
