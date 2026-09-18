# Lesson 41: Phantom Open Issue Accumulation vs Branch Landing Drift

### Context
Release management, repository governance, and issue lifecycle tracking in `imMamdouhaboammar/pymc-marketing-mcp`.

### What happened
14 GitHub issues (#4 through #17) remained in `OPEN` state for nearly two weeks, even though 13 of those issues (#4-#10, #12-#17) had already been fully implemented, regression-tested, and merged into `main` via earlier hardening waves (`e637c72`, `1182e64`).

### Observable symptom
Contributors and AI agents querying `gh issue list` saw an apparent backlog of 14 critical production blockers, leading to false assumptions about platform maturity, redundant research spikes, and hesitation to advance release candidates.

### Impact
Created substantial cognitive and planning overhead ("Issue Triage Debt"), misrepresenting an advanced, verified 90%+ production-ready codebase as having dozens of open defects.

### Incorrect assumption
Assumed that merging implementation PRs and feature branches into `main` would automatically close or reconcile corresponding issue tracker tickets, even without commit messages using standard issue-closing syntax (`Fixes #X`, `Closes #X`).

### Root cause
**Confirmed**. The code merge lifecycle was decoupled from the issue tracking lifecycle. Major multi-issue hardening waves were merged with omnibus commit messages that did not explicitly link or close individual issue numbers on GitHub.

### Why the architecture allowed it
The project lacked an automated issue verification gate or issue-closure step in the release verification pipeline (`check.sh` and `release.yml`).

### Fix
1. Audited all 14 issues against the codebase, identifying the exact passing test suites and commits proving each requirement.
2. Formally closed all 13 verified issues using `gh issue close` with traceable evidence comments referencing exact commits (`1182e64`, `e637c72`) and test names.
3. Left the 1 genuinely external blocker (#11) open with clear categorization.

### Verification
`gh issue list` reduced from 14 open issues to 1 open issue (#11). All 66 regression tests mapped to the 13 issues pass 100% on `main`.

### Prevention rule
> **Every commit or PR that implements an issue specification must include explicit GitHub closing keywords (`Closes #X` / `Fixes #X`) or be immediately verified and closed with commit SHA and test evidence during release candidate audits. Never allow verified code on `main` to drift from open issue state.**

### Reusable lesson
When joining or auditing an active repository, never assume that open issue count reflects code health. Run an evidence-based code/test audit to reconcile open issues against current HEAD before embarking on redundant reimplementations.

### Related code
- `.github/workflows/ci.yml`
- `task_plan.md`
- `state.toon`

### Related tests
- `tests/unit/test_lift_calibration_contract.py`
- `tests/unit/test_optimizer_failure_contract.py`
- `tests/integration/test_standalone_worker.py`
- `tests/integration/test_production_oauth_http.py`

### Related lessons
- [31-mcp-protocol-inversion-and-admission-boundary.md](./31-mcp-protocol-inversion-and-admission-boundary.md)
- [testing-and-verification.md](./testing-and-verification.md)

### Status
Resolved
