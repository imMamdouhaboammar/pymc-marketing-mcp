# Plan-Orchestrate Result

**Plan**: `docs/plans/2026-09-07-2241-fix-production-readiness-plan.md`
**Lang**: python
**ECC mode**: plugin
**Steps**: 18
**Scope**: all

Prepared commands only; none executed. ECC plugin installation was detected under the resolved user home. Tracked source counts after excluding generated/vendor/build/dependency/test-fixture paths: Python 176, TypeScript/JavaScript 15. Python exceeds 60%; no PyTorch dependency was found in the manifest or lockfile. Python uses the generic build resolver, not a nonexistent python-build-resolver.

The source plan is `requirements-only`. U1 still requires approved deployment/provider/identity/governance decisions and numeric operating targets. These prompts do not upgrade plan readiness or authorize implementation. Independent repairs require their own authorization; dependent units wait for prerequisite evidence. Each command links to the source plan's explicit Step anchor, not a companion-only anchor.

## Steps overview

```toon
steps[18]{step,title,tags,chain}:
  1,Resolve deployment contract,design,"ecc:planner,ecc:architect"
  2,Minimize evidence environment,impl security,"ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer"
  3,Enforce gate-specific proof,impl security,"ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer"
  4,Isolate profile automation,build,"ecc:build-error-resolver"
  5,Upgrade action runtimes,migration build,"ecc:architect,ecc:tdd-guide,ecc:build-error-resolver,ecc:python-reviewer"
  6,Bound upstream compatibility,migration,"ecc:architect,ecc:tdd-guide,ecc:python-reviewer"
  7,Repair calibration mapping,impl test,"ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer"
  8,Fix reload optimization,impl test,"ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer"
  9,Partition statistical work,impl test,"ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer"
  10,Enforce branch governance,review security,"ecc:security-reviewer,ecc:python-reviewer,ecc:code-reviewer"
  11,Wire production OAuth,impl security,"ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer"
  12,Execute standalone jobs,impl test security,"ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer"
  13,Add shared SQL,impl db,"ecc:tdd-guide,ecc:database-reviewer,ecc:python-reviewer"
  14,Add integrity storage,impl security,"ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer"
  15,Integrate shared capabilities,impl test security,"ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer"
  16,Prove operations and restore,test,"ecc:tdd-guide,ecc:e2e-runner"
  17,Prove agent safety,test security,"ecc:tdd-guide,ecc:e2e-runner,ecc:security-reviewer,ecc:python-reviewer"
  18,Rehearse candidate release,test build,"ecc:tdd-guide,ecc:e2e-runner,ecc:build-error-resolver"
```

---

## Step 1 — Resolve deployment contract

**Intent**: Resolve U1's deployment and operating decisions before dependent work. No prerequisites.
**Tags**: design
**Chain rationale**: Planner bounds the decisions; architect checks their consistency. This chain produces an approved contract, not infrastructure changes.

```bash
/ecc:orchestrate custom "ecc:planner,ecc:architect" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-1] Resolve U1 deployment contract for the multi-user MCP service in docs/SPEC.md. Acceptance: owners approve SQL/object-store/OAuth/topology and GitHub governance choices; numeric workload limits and RPO/RTO are recorded; every enabled capability has an identity and persistence path. Out of scope: product implementation and automatic billing or visibility changes."
```

## Step 2 — Minimize evidence environment

**Intent**: Repair #5 with an explicit provenance allowlist and a redacted historical review. No prerequisites.
**Tags**: impl, security
**Chain rationale**: TDD establishes the leakage regression; Python review checks collector behavior; security review closes the sensitive-data boundary.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-2] Repair #5 in release_evidence.py and its collector using explicit minimal CI provenance. Acceptance: unknown sentinel variables and HOME/session metadata never enter JSON or Markdown; supported CI SHA/run attribution remains; focused evidence tests and redacted historical exposure review are recorded. Out of scope: unrelated logging refactors or automatic history rewriting."
```

## Step 3 — Enforce gate-specific proof

**Intent**: Repair #4 after U2; collection must validate rather than rerun tests or builds.
**Tags**: impl, security
**Chain rationale**: TDD falsifies permissive proof handling; Python review checks shared consumers; security review gates trust and provenance.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-3] After U2, repair #4 with one gate-proof validator for collector and readiness renderer; separate collection from execution. Acceptance: empty/skipped/local/wrong-SHA/mixed-run proof denies release; complete trusted proof greens only mapped gates; legacy evidence stays readable but unverified. Out of scope: weakening gate definitions to fit existing tests."
```

## Step 4 — Isolate profile automation

**Intent**: Repair #8 without rewriting history. No prerequisites; use only an approved output destination or disable automation.
**Tags**: build
**Chain rationale**: The generic build resolver owns workflow policy and runtime/package verification; Python has no language-specific build resolver.

```bash
/ecc:orchestrate custom "ecc:build-error-resolver" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-4] Repair #8 in profile_summary_cards.yml: remove main write authority; disable automation absent an approved nonproduct destination. Acceptance: an authorized run leaves main SHA unchanged; wheel/sdist omit profile output; normal product PR checks still run. Out of scope: deleting historical commits or repository-wide cosmetic cleanup."
```

## Step 5 — Upgrade action runtimes

**Intent**: Repair #13 after U4, coordinating every active workflow through one CI integrator.
**Tags**: migration, build
**Chain rationale**: Architect scopes the migration; TDD covers policy; build resolver verifies actual workflows; Python reviewer closes implementation review.

```bash
/ecc:orchestrate custom "ecc:architect,ecc:tdd-guide,ecc:build-error-resolver,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-5] After U4, repair #13 by inventorying active Actions and transitive runtimes, then pin reviewed maintained SHAs. Acceptance: every active reference is covered; checkout/setup-uv no longer resolve to Node20; representative workflow logs preserve ref/cache/permission/artifact behavior without runtime warnings. Out of scope: insecure runtime opt-outs or speculative upgrades of application dependencies."
```

## Step 6 — Bound upstream compatibility

**Intent**: Repair #15 using the supported upstream API, keeping future-major exploration separate. No prerequisites.
**Tags**: migration
**Chain rationale**: Architect chooses the bounded compatibility change; TDD covers resolver/plot regressions; Python reviewer checks the application contract.

```bash
/ecc:orchestrate custom "ecc:architect,ecc:tdd-guide,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-6] Repair #15 across pyproject.toml, uv.lock, plotting service and canaries; confirm the locked upstream API first. Acceptance: unsupported majors cannot resolve; supported clean install and real numerical plotting pass; future-major probes neither alter the release lock nor claim import-only compatibility. Out of scope: adopting a new upstream major without compatibility proof."
```

## Step 7 — Repair calibration mapping

**Intent**: Repair #6 after U6 without adding calibration behavior or changing diagnostic policy.
**Tags**: impl, test
**Chain rationale**: TDD captures the public-contract regression; E2E runner exercises real calibration and lineage; Python reviewer closes the change.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-7] After U6, repair #6 by aligning declared lift inputs with the supported upstream calibration API. Acceptance: minimal valid input avoids AttributeError and invalid input returns stable errors; real calibration creates a distinct child with unchanged parent; child decisions remain blocked until fresh diagnosis. Out of scope: new calibration features or mutating parent models."
```

## Step 8 — Diagnose and fix reload optimization

**Intent**: Repair #7 only after a controlled reproducer identifies the cause. Depends on U6/U7 to serialize shared adapter edits.
**Tags**: impl, test
**Chain rationale**: TDD begins with before/after characterization; E2E runner validates actual persistence and solver behavior; Python reviewer checks the narrow repair.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-8] After U6/U7, diagnose #7 using identical data, seed, budget, bounds and horizon before/after reload; repair the demonstrated cause. Acceptance: feasible results conserve budget within agreed tolerance; non-convergence or missing success flags persist no recommendation; diagnostics thresholds remain unchanged. Out of scope: fabricated allocations or retry-only masking of solver failure."
```

## Step 9 — Partition statistical work

**Intent**: Repair #10 after U3/U5; scientific all-green exit also needs U7/U8.
**Tags**: impl, test
**Chain rationale**: TDD checks collection arithmetic; E2E runner checks real shard and aggregate outcomes; Python reviewer closes the scripts and workflow contract.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-9] After U3/U5, repair #10 by partitioning actual statistical node IDs, including tests outside the statistical directory. Acceptance: union equals full collection with only approved duplicates; missing/failed/cancelled/wrong-SHA shards deny aggregate; failure evidence uploads and collector duplicate execution is removed. Out of scope: reducing scientific sampling rigor to speed up CI."
```

## Step 10 — Enforce branch governance

**Intent**: Address #11 after U1/U4/U5/U9. Remote administration remains an explicitly authorized owner action.
**Tags**: review, security
**Chain rationale**: Security review checks governance and bypasses; Python reviewer checks policy tests; code reviewer verifies actual enforcement evidence, not documentation alone.

```bash
/ecc:orchestrate custom "ecc:security-reviewer,ecc:python-reviewer,ecc:code-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-10] After U1/U4/U5/U9, address #11 with administrator-approved GitHub entitlement remediation and stable app-bound required checks. Acceptance: live main rules match policy; failing/missing checks block merge while reviewed green PRs can merge; safe rehearsal proves unauthorized force/direct updates denied. Out of scope: automatic subscription purchases or making the repository public."
```

## Step 11 — Wire production OAuth

**Intent**: Repair #14 after the U1 identity contract is approved, preserving API-key and stdio profiles.
**Tags**: impl, security
**Chain rationale**: TDD exercises real configuration and HTTP paths; Python review checks composition; security reviewer closes issuer, tenant and token validation.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-11] After U1 identity approval, repair #14 through canonical settings/auth composition with asymmetric JWKS and trusted tenant mapping. Acceptance: real HTTP MCP calls preserve principal and scopes; bad signature/claims and cross-tenant access fail closed; safe key rotation and API-key/stdio regressions pass. Out of scope: building a custom identity provider."
```

## Step 12 — Execute standalone jobs

**Intent**: Repair #9 after U6. Same-host proof is intermediate, not final shared-production acceptance.
**Tags**: impl, test, security
**Chain rationale**: TDD covers transitions; E2E runner proves independent processes; Python reviewer checks integration; security reviewer closes persisted identity and fencing risks.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-12] After U6, repair #9 with enqueue-only API, validated standalone fit handler and durable claim/lease/fencing semantics. Acceptance: worker completes after API exit; tenant ownership and dataset authorization survive; stale attempts cannot publish and cancellation/concurrent-claim tests pass. Out of scope: introducing a new message broker."
```

## Step 13 — Add shared SQL

**Intent**: Repair #16 after U1/U12 using the approved production SQL contract, with explicit migrations and rollback.
**Tags**: impl, db
**Chain rationale**: TDD implements repository contracts; database reviewer checks real concurrency and migrations; Python reviewer closes application integration.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:database-reviewer,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-13] After U1/U12, repair #16 using approved PostgreSQL metadata/job/credential repositories and explicit backend selection. Acceptance: real SQL contract/concurrency tests pass; two instances share state and revocation with no SQLite outage fallback; migration/import rehearsal preserves ownership and safely rolls back interruption. Out of scope: supporting multiple production SQL engines."
```

## Step 14 — Add integrity storage

**Intent**: Repair #17 after U1/U12 and coordinate the storage contract with U13 before composition edits.
**Tags**: impl, security
**Chain rationale**: TDD checks shared/local adapter contracts; Python reviewer checks publication and cleanup; security reviewer closes ownership and integrity boundaries.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-14] After U1/U12 and U13 contract coordination, repair #17 with one approved shared artifact adapter plus local storage. Acceptance: cross-instance reload verifies immutable size/checksum refs; corrupt/missing/cross-tenant objects fail safely; interrupted upload and orphan cleanup cannot damage valid references. Out of scope: implementing both S3 and GCS."
```

## Step 15 — Integrate shared capabilities

**Intent**: Connect U11/U13/U14 through actual dataset, model, CLV, plot and worker services rather than unused adapters.
**Tags**: impl, test, security
**Chain rationale**: TDD establishes capability contracts; E2E runner proves the multi-instance path; Python reviewer checks integration; security reviewer closes cross-process authorization.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-15] After U11/U13/U14, integrate shared dataset/model/CLV/plot refs into actual production services and worker composition. Acceptance: API A registers, worker B fits and API C diagnoses/plots; container replacement loses no required bytes; cross-tenant access fails and shared revocation is observed. Out of scope: expanding the public capability catalogue."
```

## Step 16 — Prove operations and restore

**Intent**: Prove U16 after U15 against U1's approved numerical targets. Unit tests cannot substitute for measured restore and alert drills.
**Tags**: test
**Chain rationale**: TDD adds failure-path coverage; E2E runner closes real workload, backup, restore and operator-alert validation.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-16] After U15 and approved U1 targets, prove production probes, worker heartbeat, resource limits and coordinated SQL/object restore. Acceptance: dependency/worker faults affect readiness correctly; isolated restore verifies checksums and ownership within approved RPO/RTO; workload limits and delivered operator alerts are measured. Out of scope: multi-region active-active deployment."
```

## Step 17 — Prove agent safety

**Intent**: Prove AQG/H5 after U7/U8/U9/U15 through fresh production-profile tool traces and declared provider coverage.
**Tags**: test, security
**Chain rationale**: TDD defines negative trajectories; E2E runner executes them; security reviewer checks hostile inputs and tenancy; Python reviewer validates evidence and policy assertions.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:security-reviewer,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-17] After U7/U8/U9/U15, prove decision safety with real held-out MCP trajectories and captured tool traces. Acceptance: rejected/undiagnosed/calibration-child models cannot bypass diagnosis; cross-tenant/revoked/malicious-input cases fail safely; fresh AQG evidence declares provider coverage and never treats missing credentials as PASS. Out of scope: adding new agent capabilities."
```

## Step 18 — Rehearse candidate release

**Intent**: Prove #12 after U3/U5/U10/U16/U17 and all transitive gates. Rehearse without publication; a later promotion requires explicit release approval.
**Tags**: test, build
**Chain rationale**: TDD tests provenance tampering; E2E runner verifies exact wheel/sdist/container smoke behavior; generic build resolver closes same-byte pipeline validation.

```bash
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:build-error-resolver" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-18] After U3/U5/U10/U16/U17, rehearse #12 with publication disabled: build wheel/sdist/container once from a frozen candidate and verify exact bytes. Acceptance: wrong tag/SHA/version/digest or missing gates deny promotion; candidate-only proof binds successful install/container smoke; release/security/operations sign-offs precede any publication. Out of scope: publication before explicit release approval."
```

---

## Batch execution

Prepared sequence only, not executed. This is a **sequential, gated** handoff list: stop after each command until its acceptance evidence and prerequisite approvals are checked. Do not launch these as parallel tasks or treat a bulk paste as approval to proceed through failed gates. U1 must resolve deployment blockers first. The batch is **not permission for billing, repository visibility changes, remote governance changes, production deployment or publication**. Shared workflows, composition files, adapter files, lockfiles and planning state retain one integration owner. A green orchestration response without the source plan's required real evidence does not close a unit.

```bash
/ecc:orchestrate custom "ecc:planner,ecc:architect" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-1] Resolve U1 deployment contract for the multi-user MCP service in docs/SPEC.md. Acceptance: owners approve SQL/object-store/OAuth/topology and GitHub governance choices; numeric workload limits and RPO/RTO are recorded; every enabled capability has an identity and persistence path. Out of scope: product implementation and automatic billing or visibility changes."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-2] Repair #5 in release_evidence.py and its collector using explicit minimal CI provenance. Acceptance: unknown sentinel variables and HOME/session metadata never enter JSON or Markdown; supported CI SHA/run attribution remains; focused evidence tests and redacted historical exposure review are recorded. Out of scope: unrelated logging refactors or automatic history rewriting."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-3] After U2, repair #4 with one gate-proof validator for collector and readiness renderer; separate collection from execution. Acceptance: empty/skipped/local/wrong-SHA/mixed-run proof denies release; complete trusted proof greens only mapped gates; legacy evidence stays readable but unverified. Out of scope: weakening gate definitions to fit existing tests."
/ecc:orchestrate custom "ecc:build-error-resolver" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-4] Repair #8 in profile_summary_cards.yml: remove main write authority; disable automation absent an approved nonproduct destination. Acceptance: an authorized run leaves main SHA unchanged; wheel/sdist omit profile output; normal product PR checks still run. Out of scope: deleting historical commits or repository-wide cosmetic cleanup."
/ecc:orchestrate custom "ecc:architect,ecc:tdd-guide,ecc:build-error-resolver,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-5] After U4, repair #13 by inventorying active Actions and transitive runtimes, then pin reviewed maintained SHAs. Acceptance: every active reference is covered; checkout/setup-uv no longer resolve to Node20; representative workflow logs preserve ref/cache/permission/artifact behavior without runtime warnings. Out of scope: insecure runtime opt-outs or speculative upgrades of application dependencies."
/ecc:orchestrate custom "ecc:architect,ecc:tdd-guide,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-6] Repair #15 across pyproject.toml, uv.lock, plotting service and canaries; confirm the locked upstream API first. Acceptance: unsupported majors cannot resolve; supported clean install and real numerical plotting pass; future-major probes neither alter the release lock nor claim import-only compatibility. Out of scope: adopting a new upstream major without compatibility proof."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-7] After U6, repair #6 by aligning declared lift inputs with the supported upstream calibration API. Acceptance: minimal valid input avoids AttributeError and invalid input returns stable errors; real calibration creates a distinct child with unchanged parent; child decisions remain blocked until fresh diagnosis. Out of scope: new calibration features or mutating parent models."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-8] After U6/U7, diagnose #7 using identical data, seed, budget, bounds and horizon before/after reload; repair the demonstrated cause. Acceptance: feasible results conserve budget within agreed tolerance; non-convergence or missing success flags persist no recommendation; diagnostics thresholds remain unchanged. Out of scope: fabricated allocations or retry-only masking of solver failure."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-9] After U3/U5, repair #10 by partitioning actual statistical node IDs, including tests outside the statistical directory. Acceptance: union equals full collection with only approved duplicates; missing/failed/cancelled/wrong-SHA shards deny aggregate; failure evidence uploads and collector duplicate execution is removed. Out of scope: reducing scientific sampling rigor to speed up CI."
/ecc:orchestrate custom "ecc:security-reviewer,ecc:python-reviewer,ecc:code-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-10] After U1/U4/U5/U9, address #11 with administrator-approved GitHub entitlement remediation and stable app-bound required checks. Acceptance: live main rules match policy; failing/missing checks block merge while reviewed green PRs can merge; safe rehearsal proves unauthorized force/direct updates denied. Out of scope: automatic subscription purchases or making the repository public."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-11] After U1 identity approval, repair #14 through canonical settings/auth composition with asymmetric JWKS and trusted tenant mapping. Acceptance: real HTTP MCP calls preserve principal and scopes; bad signature/claims and cross-tenant access fail closed; safe key rotation and API-key/stdio regressions pass. Out of scope: building a custom identity provider."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-12] After U6, repair #9 with enqueue-only API, validated standalone fit handler and durable claim/lease/fencing semantics. Acceptance: worker completes after API exit; tenant ownership and dataset authorization survive; stale attempts cannot publish and cancellation/concurrent-claim tests pass. Out of scope: introducing a new message broker."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:database-reviewer,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-13] After U1/U12, repair #16 using approved PostgreSQL metadata/job/credential repositories and explicit backend selection. Acceptance: real SQL contract/concurrency tests pass; two instances share state and revocation with no SQLite outage fallback; migration/import rehearsal preserves ownership and safely rolls back interruption. Out of scope: supporting multiple production SQL engines."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-14] After U1/U12 and U13 contract coordination, repair #17 with one approved shared artifact adapter plus local storage. Acceptance: cross-instance reload verifies immutable size/checksum refs; corrupt/missing/cross-tenant objects fail safely; interrupted upload and orphan cleanup cannot damage valid references. Out of scope: implementing both S3 and GCS."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:python-reviewer,ecc:security-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-15] After U11/U13/U14, integrate shared dataset/model/CLV/plot refs into actual production services and worker composition. Acceptance: API A registers, worker B fits and API C diagnoses/plots; container replacement loses no required bytes; cross-tenant access fails and shared revocation is observed. Out of scope: expanding the public capability catalogue."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-16] After U15 and approved U1 targets, prove production probes, worker heartbeat, resource limits and coordinated SQL/object restore. Acceptance: dependency/worker faults affect readiness correctly; isolated restore verifies checksums and ownership within approved RPO/RTO; workload limits and delivered operator alerts are measured. Out of scope: multi-region active-active deployment."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:security-reviewer,ecc:python-reviewer" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-17] After U7/U8/U9/U15, prove decision safety with real held-out MCP trajectories and captured tool traces. Acceptance: rejected/undiagnosed/calibration-child models cannot bypass diagnosis; cross-tenant/revoked/malicious-input cases fail safely; fresh AQG evidence declares provider coverage and never treats missing credentials as PASS. Out of scope: adding new agent capabilities."
/ecc:orchestrate custom "ecc:tdd-guide,ecc:e2e-runner,ecc:build-error-resolver" "[Plan: docs/plans/2026-09-07-2241-fix-production-readiness-plan.md#step-18] After U3/U5/U10/U16/U17, rehearse #12 with publication disabled: build wheel/sdist/container once from a frozen candidate and verify exact bytes. Acceptance: wrong tag/SHA/version/digest or missing gates deny promotion; candidate-only proof binds successful install/container smoke; release/security/operations sign-offs precede any publication. Out of scope: publication before explicit release approval."
```
