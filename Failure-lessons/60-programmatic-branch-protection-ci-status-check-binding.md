# Lesson 60: Programmatic Branch Protection & Exact CI Status Check Binding

### Context
Repository release governance, branch protection configuration, and CI gate enforcement on `imMamdouhaboammar/pymc-marketing-mcp`.

### What happened
During repository audits prior to production cutover, the default branch `main` had no active branch protection rules or required status checks. Issue #11 ("Protect main with stable required checks before release") had been opened to address this vulnerability. Because branches were not protected, direct pushes or unreviewed pull requests could land on `main` without waiting for CI checks.

### Observable symptom
```text
Issue #11: Protect main with stable required checks before release
State: OPEN
Protection status on main: None (unprotected)
```

### Impact
Unprotected main branches allow broken code, unformatted commits, failing tests, or unverified dependencies to enter production directly, invalidating baseline assumptions and breaking downstream dependent services.

### Incorrect assumption
Assumed that creating GitHub Actions workflows (`ci.yml`, `release.yml`) automatically protects `main`, or that branch protection configuration is an administrative UI task that does not need programmatic specification.

### Root cause
**Confirmed**. GitHub repositories default to unprotected branches. Branch protection rules require explicit binding via the GitHub REST API or Terraform/IaC, specifying the exact context strings of required status check jobs.

### Why the architecture allowed it
The repository bootstrapping script created GitHub workflows but did not invoke the GitHub API to enforce branch protection rules on `main`.

### Fix
Programmatically configured branch protection using the GitHub REST API:
```bash
gh api --method PUT /repos/imMamdouhaboammar/pymc-marketing-mcp/branches/main/protection \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Unit & Contract Tests",
      "MCP Protocol & Integration Tests",
      "Release Truth Gates",
      "Lint, Types & Docs Drift"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
```
This guarantees:
1. Strict requirement: Branch must be up-to-date with `main` before merging.
2. All 4 core CI status checks must be green.
3. Force pushes and branch deletions are strictly disabled.
4. Admins are subject to the same protections.

### Verification
1. Queried `gh api /repos/imMamdouhaboammar/pymc-marketing-mcp/branches/main/protection` and verified 200 OK with all 4 required status checks active.
2. Closed Issue #11 with audit confirmation.
3. Subsequent PRs (e.g. PR #34) were required to pass checks before merging.

### Prevention rule
> **Before declaring a repository production-ready, the default branch must have branch protection programmatically applied with strict status checks matching exact CI job names, preventing force pushes and unverified merges.**

### Reusable lesson
CI workflows define what *can* be tested; branch protection rules define what *must* pass before code can land. A CI pipeline without branch protection is purely advisory. Always programmatically enforce required checks in project bootstrap scripts.

### Related code
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `scripts/fast_deploy.sh`

### Related tests
- `tests/release/test_candidate_provenance.py`
- `tests/release/test_g0_production_truth.py`

### Status
Resolved
