---
title: Marketing Reconciliation Engine - Engineering Tasks
type: feat
date: 2026-09-12
source_plan: docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-plan.md
source_brief: docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-engineering-brief.md
execution: code
---

# Marketing Reconciliation Engine - Engineering Tasks

This file is the implementation ledger for the Marketing Reconciliation Engine v1.

The canonical plan owns product behavior. The staff engineer brief owns implementation shape. This file owns execution order, atomic task boundaries, coding orders, context lenses, acceptance checks, and handoff state.

Do not use a checked box as proof. Mark a task complete only after the task's named evidence has run against the current implementation state.

---

## How to Use This Ledger

### Task states

```toon
task_states[6]{state,meaning}:
  todo,Not started
  ready,Dependencies and context are satisfied
  active,One writer is implementing the task
  verify,Implementation exists and named checks are running
  blocked,A named dependency or contradiction prevents correct work
  done,Acceptance evidence is fresh and reviewed
```

The markdown checkbox is the durable human marker.

Use `[ ]` for `todo`, `ready`, `active`, `verify`, or `blocked`.

Use `[x]` only for `done`.

If a task becomes blocked, add a short `Blocker:` line under that task. Do not rewrite the task into a workaround that changes scope.

### Execution discipline

For each task:

1. Load the listed context lenses.
2. Read the exact current files before editing.
3. State the invariant and prohibited side effect in the working notes.
4. Create or identify a failing check when the task changes behavior.
5. Make the smallest coherent code change.
6. Run the focused check.
7. Run the adjacent contract checks listed by the task.
8. Inspect the diff.
9. Mark the task complete only when the acceptance evidence exists.

### Shared rules

```toon
shared_rules[12]{rule}:
  one active writer owns each shared contract
  no arbitrary provider actuation in v1
  no new broker queue scheduler or workflow engine
  no dynamic recipe plugin framework in v1
  no model retuning as reconciliation
  no diagnostic threshold changes to make a model pass
  no caller-controlled force path
  no caller-controlled recipe selection
  no cross-tenant incident reads or actions
  no high-cardinality metric labels
  no generated-doc hand edits when a generator owns the file
  no completion claim without fresh final-state verification
```

---

## Context Lens Index

```toon
lenses[9]{id,name,primary_context}:
  L0,Product Contract,source plan and R1-R19
  L1,Decision Safety,DECISION-INTEGRITY plus DecisionGate
  L2,Jobs and Concurrency,JobRepository state worker idempotency fencing
  L3,Persistence,PersistenceBackend migrations metadata storage
  L4,Security and Tenancy,Principal scope policy auth integration
  L5,MCP and Capability,tool modules server capabilities discovery
  L6,Observability,metrics structured logging traces redaction
  L7,Release Evidence,production readiness AQG H5 docs drift
  L8,Simplicity,existing patterns no speculative abstractions
```

---

## Coding Order Index

```toon
coding_orders[10]{id,tasks,exit}:
  CO0,T00 T01 T02,baseline and current contracts are characterized
  CO1,T10 T11 T12 T13,domain policy and fingerprint contract are test-backed
  CO2,T20 T21 T22 T23 T24,durable incident and attempt persistence is proven
  CO3,T30 T31 T32 T33 T34,shadow reconciliation is side-effect safe
  CO4,T40 T41 T42,subject-scoped atomic job recovery is proven independently
  CO5,T50 T51 T52 T53,safe_auto detect act verify loop is idempotent and fenced
  CO6,T60 T61 T62 T63,MCP security and capability surface are proven
  CO7,T70 T71 T72,observability and agent negative evidence are proven
  CO8,T80 T81 T82,documentation and generated contracts match runtime
  CO9,T90 T91 T92 T93,integrated verification review and handoff are complete
```

Do not start a coding order until every dependency order named above has met its exit gate.

---

# CO0 - Refresh Baseline and Freeze Current Contracts

## [ ] T00. Confirm current repository baseline

**Lenses:** L0, L7, L8

**Goal:** Confirm that implementation begins from the expected repository state and that no product code changed after the planning baseline without review.

**Read:**

- `docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-plan.md`
- `docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-engineering-brief.md`
- `AGENTS.md`
- `task_plan.md`
- current `main` commit and diff since `e637c72fe75961ccae4f74e01d440b18e6ed35c9`

**Steps:**

1. Confirm the only expected post-baseline changes are reconciliation planning documents unless newer product commits have landed intentionally.
2. If product code changed, inspect whether any touched seam invalidates this ledger.
3. Record any contract drift before writing code.
4. Do not update the implementation baseline silently when a changed seam affects persistence, jobs, authorization, MCP discovery, or diagnostics.

**Acceptance:**

- current code owners referenced by this ledger still exist
- no unreviewed implementation drift invalidates CO1-CO6
- any meaningful drift has a documented plan adjustment before coding

**Stop if:** the current code materially changes job recovery, persistence composition, tenant auth, decision gates, or capability registration.

**Commit boundary:** none. This is a read-only preflight.

---

## [ ] T01. Characterize current job recovery behavior

**Lenses:** L0, L2, L8

**Goal:** Freeze current stale-lease recovery behavior before introducing a subject-scoped repair.

**Read:**

- `src/marketing_mcp/jobs/repository.py`
- `src/marketing_mcp/jobs/state.py`
- `src/marketing_mcp/jobs/process_worker.py`
- `tests/unit/test_process_worker.py`
- `tests/unit/test_job_state_machine.py`

**Steps:**

1. Identify every state transition performed by `recover_stale_running_jobs()`.
2. Confirm behavior for retries remaining and retries exhausted.
3. Confirm behavior for live leases.
4. Confirm behavior for cancelling and cancelled jobs.
5. Confirm stale worker publication is blocked by fence token checks after recovery.
6. Identify whether a focused test already proves each case.

**Acceptance:** a short working note maps current predicate, mutation, and postcondition to existing tests.

**Required evidence:** existing focused job tests pass before any recovery refactor.

**Stop if:** current code behavior differs from the source plan's assumptions.

**Commit boundary:** none unless a missing characterization test is added. If a test is added, commit it separately from the recovery implementation.

---

## [ ] T02. Characterize auth, MCP, capability, and docs generation seams

**Lenses:** L4, L5, L7, L8

**Goal:** Freeze the exact public and security extension points before new tools are added.

**Read:**

- `src/marketing_mcp/security/policy.py`
- request context and principal modules used by current tools
- `src/marketing_mcp/mcp/server.py`
- one existing focused MCP tool module such as `src/marketing_mcp/mcp/tools/decisions.py`
- `src/marketing_mcp/capabilities.py`
- `tests/integration/test_mcp_protocol.py`
- `tests/integration/test_mcp_discovery_snapshot.py`
- `tests/integration/test_capability_inventory.py`
- `scripts/generate_capability_inventory.py`
- `scripts/check_docs_drift.py`

**Steps:**

1. Confirm how handlers resolve principal and tenant context.
2. Confirm how tool scope is mapped and enforced.
3. Confirm how cross-tenant object isolation is represented in current tests.
4. Confirm how server registration affects MCP discovery.
5. Confirm how capability declarations map to generated docs and evidence test IDs.
6. Confirm which docs are generated and which are hand-maintained.

**Acceptance:** extension points are known before CO6 starts.

**Commit boundary:** none.

---

# CO1 - Domain Contract and Pure Policy

## [ ] T10. Create reconciliation domain vocabulary

**Lenses:** L0, L1, L8

**Depends on:** T00

**Goal:** Add the smallest typed vocabulary needed to represent incidents and policy decisions without storage or transport dependencies.

**Primary files:**

- create `src/marketing_mcp/domain/reconciliation.py`
- create `tests/unit/test_reconciliation_domain.py`

**Required concepts:**

```toon
domain_values[7]{concept,minimum_variants}:
  FaultClass,operational data_integrity epistemic commercial
  ActionMode,shadow safe_auto approval_required prohibited
  IncidentState,open actionable verifying healed escalated failed
  SubjectKind,job dataset model
  VerificationStatus,not_run passed failed
  AttemptOutcome,planned no_op healed failed escalated denied
  RecipeKey,recover_expired_job_lease only for v1 automatic repair
```

**Steps:**

1. Write failing tests for enum or value validation and lifecycle transitions.
2. Add types with no imports from MCP, SQLite, or provider modules.
3. Keep illegal lifecycle transitions explicit.
4. Make terminal states clear.
5. Do not model shadow as an incident terminal state.
6. Do not add provider-specific subject kinds for v1.

**Tests first:**

- unknown fault class cannot silently become operational
- healed cannot transition back to actionable without a new incident
- verification failure cannot transition to healed
- epistemic class cannot select `safe_auto`
- prohibited mode remains prohibited under any caller intent

**Acceptance:** domain tests pass and domain code is side-effect free.

**Must not change:** decision thresholds, job states, MCP schemas, persistence.

**Stop if:** implementation needs provider concepts or arbitrary executable recipes.

**Commit boundary:** domain types plus domain tests only.

---

## [ ] T11. Define deterministic policy mapping

**Lenses:** L0, L1, L8

**Depends on:** T10

**Goal:** Make action-mode selection a pure deterministic decision from structured evidence.

**Primary files:**

- `src/marketing_mcp/domain/reconciliation.py`
- `tests/unit/test_reconciliation_domain.py`

**Policy rules:**

```toon
policy[6]{input,mode,recipe}:
  expired_job_lease_with_safe_preconditions,shadow_by_default,recover_expired_job_lease
  explicit_safe_auto_request_plus_eligible_recipe,safe_auto,recover_expired_job_lease
  dataset_blocking_findings,shadow,none
  rejected_or_undiagnosed_model,approval_required,none
  ambiguous_commercial_signal,prohibited,none
  unknown_fault,prohibited,none
```

The policy may distinguish `approval_required` from `prohibited` when the product contract already supports the distinction. It must never use caller persuasion or free-form text as authority.

**Tests first:**

- eligible operational fault defaults to shadow
- `safe_auto` requires a registered recipe and satisfied policy preconditions
- dataset or model uncertainty does not acquire a repair key
- unknown fault fails closed
- caller cannot supply a recipe key that widens authority

**Acceptance:** the same structured input always produces the same policy decision.

**Commit boundary:** policy rules and focused tests.

---

## [ ] T12. Define stable incident fingerprint function

**Lenses:** L0, L3, L8

**Depends on:** T10

**Goal:** Produce a stable semantic fingerprint for one unresolved invariant violation.

**Primary files:**

- `src/marketing_mcp/domain/reconciliation.py`
- `tests/unit/test_reconciliation_domain.py`

**Fingerprint inputs:** tenant ID, fault code, subject kind, subject ID, invariant version.

**Excluded inputs:** timestamps, lease expiry, trace IDs, warning text, request IDs, metrics, current status strings that can change while the same fault remains active.

**Steps:**

1. Search for an existing semantic hashing helper before adding code.
2. Reuse standard library hashing or existing project helper.
3. Make input normalization deterministic.
4. Test that volatile evidence changes do not change the fingerprint.
5. Test that tenant or subject changes do change the fingerprint.

**Acceptance:** repeated scans of the same fault produce the same fingerprint.

**Stop if:** a new hashing dependency appears necessary. Re-evaluate first.

**Commit boundary:** fingerprint helper and tests.

---

## [ ] T13. Freeze CO1 domain contract

**Lenses:** L0, L1, L8

**Depends on:** T10, T11, T12

**Goal:** Review the domain surface before persistence depends on it.

**Steps:**

1. Run the complete reconciliation domain test file.
2. Inspect every public type in `domain/reconciliation.py`.
3. Remove unused speculative fields and provider placeholders.
4. Confirm no transport or storage dependency leaked into the domain.
5. Confirm R1, R4-R9, and R12 have a clear owner in the domain contract.

**Acceptance:** C1 domain portion is green and stable enough for persistence.

**Commit boundary:** cleanup only if behavior stays green.

---

# CO2 - Durable Incident and Attempt Persistence

## [ ] T20. Add reconciliation schema migration

**Lenses:** L0, L3, L4, L8

**Depends on:** T13

**Goal:** Add durable incident and attempt tables without damaging current data.

**Primary files:**

- `src/marketing_mcp/storage/migrations.py`
- create or extend migration tests in the most appropriate current persistence test file

**Schema requirements:**

```toon
tables[2]{table,purpose}:
  reconciliation_incidents,one durable record per detected invariant violation
  reconciliation_attempts,append-like action and verification history
```

**Required incident columns:** incident ID, tenant ID, owner, fingerprint, fault class, fault code, subject kind, subject ID, state, action mode, recipe key nullable, compact evidence JSON, policy version, first seen, last seen, resolved time nullable.

**Required attempt columns:** attempt ID, incident ID, tenant ID, actor subject, action mode, recipe key nullable, idempotency key, precondition JSON, before evidence JSON, action result JSON nullable, verification JSON, outcome, created time.

**Constraints:**

- foreign key or equivalent incident relationship where current SQLite configuration safely supports it
- index for tenant and state listing
- index for incident attempts ordered by creation
- persistence-level protection against duplicate active tenant plus fingerprint
- no raw data blob columns

**Tests first:**

- migration applies from current schema
- existing core tables and rows survive
- duplicate active incident for same tenant and fingerprint is rejected or converges through repository semantics
- same fingerprint in another tenant is allowed

**Acceptance:** migration tests pass on a real SQLite database.

**Stop if:** the design requires a second database file.

**Commit boundary:** migration plus migration tests.

---

## [ ] T21. Add ReconciliationRepository contract and SQLite implementation

**Lenses:** L0, L3, L4, L8

**Depends on:** T20

**Goal:** Give reconciliation persistence one narrow owner using the existing database.

**Primary files:**

- create `src/marketing_mcp/repositories/reconciliation.py`
- create `tests/integration/test_reconciliation_persistence.py`

**Required operations:**

```toon
repository_ops[8]{operation,purpose}:
  create_or_refresh_incident,deduplicate active incident and update last_seen evidence
  get_incident,tenant-scoped single read
  list_incidents,tenant-scoped bounded listing
  update_incident_state,legal lifecycle persistence
  create_attempt,append new action record
  get_attempt_by_idempotency_key,retry convergence
  complete_attempt,store action verification and outcome
  list_attempts,ordered audit history
```

Exact method names may follow repository conventions.

**Steps:**

1. Write restart and tenant-isolation tests first.
2. Implement queries with parameterized SQL only.
3. Keep tenant filters in repository methods where tenant context exists.
4. Keep attempt history append-like.
5. Make duplicate scan convergence atomic at the storage boundary.
6. Do not leak another tenant's incident through alternate error text.

**Tests first:**

- same tenant plus fingerprint converges
- cross-tenant same fingerprint stays separate
- close and reopen preserves incident and attempts
- missing incident returns stable not-found semantics
- repeated idempotency key returns the prior attempt rather than creating another
- failed attempt remains inspectable

**Acceptance:** persistence integration tests pass on SQLite.

**Commit boundary:** repository contract, SQLite implementation, and focused tests.

---

## [ ] T22. Wire repository into PersistenceBackend

**Lenses:** L0, L3, L8

**Depends on:** T21

**Goal:** Compose reconciliation persistence through the existing backend without a parallel storage path.

**Primary files:**

- `src/marketing_mcp/persistence.py`
- `src/marketing_mcp/repositories/reconciliation.py`
- `tests/integration/test_reconciliation_persistence.py`
- any existing persistence composition test that owns backend parity

**Steps:**

1. Add a `reconciliation` repository property to the persistence protocol.
2. Initialize the SQLite repository against the existing connection or approved shared SQLite ownership pattern.
3. Ensure close semantics do not double-close the connection.
4. Preserve current metadata, jobs, and credentials behavior.
5. Make unsupported production backends fail according to current persistence truth, not silently fall back.

**Acceptance:** existing persistence tests and reconciliation persistence tests pass.

**Stop if:** connection ownership becomes ambiguous or causes nested transaction corruption.

**Commit boundary:** backend composition plus tests.

---

## [ ] T23. Add persistence concurrency and rollback coverage

**Lenses:** L2, L3, L4

**Depends on:** T21, T22

**Goal:** Prove persistence does not create duplicate active incidents or false completed attempts under failure.

**Primary files:** `tests/integration/test_reconciliation_persistence.py`

**Scenarios:**

1. Two near-simultaneous create-or-refresh attempts for the same tenant and fingerprint converge on one active incident.
2. Failed attempt completion transaction does not partially mark the incident healed.
3. Duplicate idempotency key does not append a second attempt.
4. Tenant-filtered list cannot surface another tenant under the same subject ID.
5. Reopening the app after a partial attempt preserves a non-healed state.

**Acceptance:** all scenarios pass deterministically.

**Commit boundary:** tests plus minimum required repository fix.

---

## [ ] T24. Freeze CO2 persistence contract

**Lenses:** L0, L3, L4, L8

**Depends on:** T20-T23

**Goal:** Complete C1 before detectors depend on durable state.

**Steps:**

1. Run domain and reconciliation persistence suites.
2. Run existing migration and persistence suites affected by the change.
3. Inspect the migration for destructive statements.
4. Inspect repository queries for missing tenant predicates.
5. Confirm incident evidence excludes raw data and secrets.
6. Confirm no second persistence platform was introduced.

**Acceptance:** Checkpoint C1 is fully satisfied.

---

# CO3 - Shadow Detection and Reconciliation Service

## [ ] T30. Implement job expired-lease detector

**Lenses:** L0, L2, L3, L8

**Depends on:** T24, T01

**Goal:** Detect an expired running job lease without mutating job state.

**Primary files:**

- create `src/marketing_mcp/services/reconciliation_service.py`
- create `tests/unit/test_reconciliation_service.py`

**Steps:**

1. Build detector input from current `JobRecord` fields.
2. Detect only `running` records with an explicit expired lease.
3. Record attempts versus max attempts in evidence.
4. Distinguish retryable recovery from recovery-to-failed terminal result without mutating yet.
5. Treat live lease, queued, cancelling, cancelled, failed, and succeeded as non-incidents for this detector.
6. Produce a structured operational finding, not a free-form repair command.

**Tests first:** all job-state variants above.

**Acceptance:** detector tests are pure and no repository write occurs.

**Parallel-safe with:** T31 and T32 only after shared evidence contract is frozen.

**Commit boundary:** detector behavior and tests.

---

## [ ] T31. Implement dataset validation detector

**Lenses:** L0, L1, L3, L8

**Depends on:** T24

**Goal:** Convert existing blocking dataset validation findings into data-integrity incidents without rewriting data.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `tests/unit/test_reconciliation_service.py`

**Steps:**

1. Use the existing dataset validation service boundary.
2. Identify stable blocking finding codes from current output.
3. Build compact evidence using finding codes and dataset identity.
4. Classify as data-integrity.
5. Set shadow or escalation according to pure policy.
6. Do not store raw rows, file content, or full dataset profiles in incident evidence.

**Tests first:** blocking finding, warnings-only or valid dataset, missing dataset according to current domain error semantics.

**Acceptance:** blocking validation produces an incident and never a repair recipe.

**Parallel-safe with:** T30 and T32 under one integration owner.

---

## [ ] T32. Implement model diagnostic detectors

**Lenses:** L0, L1, L3, L8

**Depends on:** T24

**Goal:** Represent rejected, undiagnosed, and cautionary model states without changing model configuration.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `tests/unit/test_reconciliation_service.py`

**Steps:**

1. Read current stored model and diagnostic status through the existing service seam.
2. Create epistemic incidents for rejected or undiagnosed decision state.
3. Preserve caution warnings for `approved_with_caution` without calling them healed.
4. Use `recommend_next_measurement` only as optional guidance when current evidence supports it.
5. Never call `simulate_budget`, `optimize_budget`, `optimize_flighting`, or model retuning to diagnose the incident.

**Tests first:** rejected, undiagnosed, approved-with-caution, approved.

**Acceptance:** rejected state produces escalation and no decision-grade call.

**Parallel-safe with:** T30 and T31 under one integration owner.

---

## [ ] T33. Implement scan orchestration and durable incident convergence

**Lenses:** L0, L1, L2, L3, L8

**Depends on:** T30, T31, T32

**Goal:** Coordinate detectors, policy, and persistence in shadow mode.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `src/marketing_mcp/app.py`
- create `tests/integration/test_reconciliation_shadow.py`

**Steps:**

1. Compose the service in `Application` using the reconciliation repository and existing domain owners.
2. Add bounded scan entry points by authorized subject type or explicit repository object identifiers.
3. For each detector finding, compute stable fingerprint.
4. Create or refresh one active incident.
5. Evaluate pure policy.
6. Persist a shadow plan or escalation record.
7. Re-read source state if needed before persisting an actionable result.
8. Do not execute any repair in CO3.

**Tests first:**

- expired job creates one incident
- repeated scan refreshes same incident
- clean object creates none
- blocking dataset creates data-integrity incident
- rejected model creates escalation
- approved-with-caution preserves warnings
- shadow scan changes only reconciliation tables

**Acceptance:** Checkpoint C2 shadow side-effect evidence is nearly complete.

**Commit boundary:** service orchestration and shadow integration tests.

---

## [ ] T34. Prove shadow mode has zero underlying repair side effects

**Lenses:** L0, L1, L2, L3, L4

**Depends on:** T33

**Goal:** Make side-effect absence executable evidence rather than an architectural promise.

**Primary files:** `tests/integration/test_reconciliation_shadow.py`

**Steps:**

1. Snapshot relevant job record before scan and compare after scan.
2. Snapshot relevant dataset metadata before scan and compare after scan.
3. Snapshot model record and diagnostic state before scan and compare after scan.
4. Confirm no scenario or budget decision record is created.
5. Confirm only reconciliation metadata changes.
6. Repeat after process restart and confirm convergence.

**Acceptance:** Checkpoint C2 is satisfied.

**Stop if:** any detector requires mutation to determine health.

---

# CO4 - Subject-Scoped Atomic Job Recovery

## [ ] T40. Add failing tests for one-job stale recovery

**Lenses:** L0, L2, L3, L8

**Depends on:** T01

**Goal:** Specify a subject-scoped recovery contract before changing `JobRepository`.

**Primary files:**

- `tests/unit/test_process_worker.py` or a focused job repository test file if current organization makes that clearer

**Required scenarios:**

```toon
recovery_cases[8]{case,expected}:
  expired_retries_left,one job requeued
  expired_attempts_exhausted,one job failed
  live_lease,no_op
  cancelling,no_op
  cancelled,no_op
  wrong_tenant,deny_or_not_found without mutation
  concurrent_renewal,do not recover newly live lease
  stale_worker_finish_after_recovery,STALE_JOB_CLAIM
```

**Acceptance:** tests fail for the missing subject-scoped API for the intended reason.

**Commit boundary:** test-only characterization when practical.

---

## [ ] T41. Implement atomic subject-scoped stale recovery

**Lenses:** L0, L2, L3, L4, L8

**Depends on:** T40

**Goal:** Add one repository-owned actuator that can safely recover exactly one stale running job.

**Primary files:**

- `src/marketing_mcp/jobs/repository.py`
- focused job repository tests

**Implementation constraints:**

1. The operation owns the transaction.
2. The selection and update are guarded by job identity and current recovery predicates.
3. Tenant predicate is included where tenant context is supplied.
4. It changes only one job.
5. It returns enough typed information to distinguish changed versus no-op without requiring the caller to guess from error text.
6. It preserves current batch recovery error codes and resulting states.
7. It does not weaken fencing.
8. It does not resurrect cancellation.

**Ponytail constraint:** prefer a small direct repository method over a new recovery service abstraction.

**Acceptance:** all T40 scenarios pass.

**Commit boundary:** repository API, implementation, and focused tests.

---

## [ ] T42. Re-verify existing batch startup recovery

**Lenses:** L0, L2, L3, L8

**Depends on:** T41

**Goal:** Ensure the new narrow actuator does not regress `recover_stale_running_jobs()`.

**Steps:**

1. Run existing startup recovery tests unchanged.
2. Run mixed batches with live and expired jobs.
3. Confirm current error codes remain stable.
4. Confirm batch operation still handles retries exhausted.
5. Confirm application startup behavior remains unchanged.
6. Refactor duplicated recovery predicates only if the shared form is simpler and keeps transaction behavior obvious.

**Acceptance:** old batch tests plus new subject-scoped tests pass.

**Stop if:** sharing code makes atomic SQL behavior harder to reason about. Duplication of a small predicate is preferable to an unsafe abstraction.

---

# CO5 - Safe Auto Detect, Act, Verify Loop

## [ ] T50. Add action-attempt orchestration in shadow mode

**Lenses:** L0, L2, L3, L6, L8

**Depends on:** T34, T42

**Goal:** Record an attempt contract without executing the repair yet.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `tests/integration/test_reconciliation_recovery.py`

**Steps:**

1. Resolve current incident and policy from persistence plus fresh evidence.
2. Build semantic attempt idempotency key.
3. Persist precondition and before evidence.
4. For `shadow`, persist `planned` outcome and stop.
5. Repeating the same shadow action should not append unbounded duplicate attempts for the same semantic action generation.

**Acceptance:** shadow attempt history is durable and idempotent.

---

## [ ] T51. Wire eligible safe_auto to subject-scoped job recovery

**Lenses:** L0, L2, L3, L4, L8

**Depends on:** T50, T41

**Goal:** Execute the first automatic repair only when policy and fresh preconditions allow it.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `tests/integration/test_reconciliation_recovery.py`

**Steps:**

1. Load incident under tenant ownership.
2. Re-read the current job immediately before action.
3. Re-evaluate the recovery predicate.
4. If the invariant disappeared, complete attempt as no-op.
5. If policy is not `safe_auto`, do not call the actuator.
6. If eligible, call the one-job recovery operation.
7. Persist action result without marking healed yet.
8. Move incident to verifying only when a mutation actually occurred.

**Tests first:** live lease race, wrong tenant, prohibited mode, shadow mode, duplicate request.

**Acceptance:** only the eligible stale job can mutate.

---

## [ ] T52. Add fresh postcondition verification

**Lenses:** L0, L2, L3, L6, L8

**Depends on:** T51

**Goal:** Make verification the only path to `healed`.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `tests/integration/test_reconciliation_recovery.py`

**Verification rules:**

```toon
postconditions[3]{recovery_path,expected}:
  retries_remaining,job is queued lease cleared and retry error recorded
  attempts_exhausted,job is failed lease cleared and exhausted error recorded
  no_op,invariant no longer exists and no action mutation occurred
```

**Steps:**

1. Read job state after the actuator returns.
2. Compare against the exact expected branch from precondition.
3. Store verification evidence.
4. Mark healed only on pass.
5. On mismatch, mark incident escalated and keep attempt evidence.
6. If verification read fails, do not infer success from the actuator return.

**Tests first:** mocked or injected inconsistent post-state must prevent healed.

**Acceptance:** no code path can set healed before verification passes.

---

## [ ] T53. Prove safe repair idempotency, restart, cancellation, and fencing

**Lenses:** L0, L2, L3, L4, L8

**Depends on:** T51, T52

**Goal:** Close Checkpoint C3 with integration evidence.

**Primary files:** `tests/integration/test_reconciliation_recovery.py`

**Scenarios:**

1. Eligible expired lease requeues and heals.
2. Attempts exhausted fails job and heals the expired-lease incident because the invariant was correctly reconciled to terminal failure.
3. Live lease is no-op.
4. Cancelling or cancelled job is no-op.
5. Second reconcile request after healing performs no second mutation.
6. Process restart between action attempt persistence and follow-up request does not duplicate action.
7. Stale worker completion after recovery is rejected by fence token.
8. Verification mismatch escalates.
9. Repository exception records failed attempt and leaves incident non-healed.

**Acceptance:** Checkpoint C3 is satisfied.

---

# CO6 - MCP, Authorization, Tenancy, and Capability Surface

## [ ] T60. Add `marketing:reconcile` scope

**Lenses:** L0, L4, L5, L8

**Depends on:** T34, T53

**Goal:** Separate repair authority from read, model, decision, CLV, and admin scopes.

**Primary files:**

- `src/marketing_mcp/security/policy.py`
- relevant policy unit tests

**Steps:**

1. Add the new scope to the catalog.
2. Do not map existing tools to it.
3. Do not imply that `marketing:decide` or `marketing:admin` automatically grants it unless current wildcard semantics already apply by design.
4. Preserve trusted local wildcard behavior.
5. Add tool mappings only when T61 introduces tool names.

**Tests first:** principal with read only lacks reconcile; wildcard retains current trusted behavior.

**Acceptance:** scope catalog is internally consistent.

---

## [ ] T61. Add narrow reconciliation MCP handlers

**Lenses:** L0, L4, L5, L8

**Depends on:** T60, T33, T53

**Goal:** Expose the four v1 operations without arbitrary mutation input.

**Primary files:**

- create `src/marketing_mcp/mcp/tools/reconciliation.py`
- `src/marketing_mcp/mcp/server.py`
- `tests/integration/test_mcp_protocol.py`

**Tools:**

- `scan_marketing_health`
- `list_reconciliation_incidents`
- `get_reconciliation_incident`
- `reconcile_incident`

**Input rules:**

- resolve tenant from principal context
- accept bounded subject identifiers or incident ID only
- no `force`
- no caller recipe key
- no shell, SQL, URL, callback, or provider credential fields

**Output rules:**

- stable incident state
- action mode
- fault codes
- compact evidence
- verification outcome
- warnings and next actions

**Tests first:** tool happy path, missing scope, malformed ID, prohibited action, shadow behavior.

**Acceptance:** protocol tests prove the handlers delegate only to `ReconciliationService` and preserve error envelopes.

---

## [ ] T62. Register experimental capabilities and discovery

**Lenses:** L0, L5, L7, L8

**Depends on:** T61

**Goal:** Keep declared capability inventory synchronized with actual MCP discovery.

**Primary files:**

- `src/marketing_mcp/capabilities.py`
- `tests/integration/test_mcp_discovery_snapshot.py`
- `tests/integration/test_capability_inventory.py`

**Steps:**

1. Add `reconciliation` to the capability domain vocabulary if required by current registry validation.
2. Add four tools as `experimental`.
3. Point each capability to its `Application` delegation path.
4. Add evidence test IDs only for tests that exist.
5. Update discovery snapshot through the normal source-of-truth path.
6. Do not mark stable because the design is complete.

**Acceptance:** real discovery and declared inventory match.

---

## [ ] T63. Add cross-tenant and scope integration tests

**Lenses:** L0, L4, L5, L8

**Depends on:** T61, T62

**Goal:** Prove public authorization at the same boundary clients use.

**Primary files:**

- create `tests/integration/test_reconciliation_auth.py` or extend the current HTTP auth integration file only if that remains clearer

**Scenarios:**

```toon
auth_cases[8]{principal,operation,expected}:
  read_only,list_own,allow
  read_only,get_own,allow
  read_only,scan,deny
  read_only,reconcile,deny
  reconcile_scope,scan_own,allow
  reconcile_scope,reconcile_own,allow_if_policy_allows
  reconcile_scope,get_other_tenant,fail_closed
  wildcard_trusted_local,reconcile_own,allow_subject_to_policy
```

**Additional negative checks:**

- guessed other-tenant incident ID does not leak evidence
- errors do not echo secret-bearing evidence
- caller cannot change tenant ID to escape principal context

**Acceptance:** Checkpoint C4 security portion passes through real HTTP or MCP integration where current repository tests support it.

---

# CO7 - Observability and Agent Safety

## [ ] T70. Add low-cardinality reconciliation metrics

**Lenses:** L0, L6, L8

**Depends on:** T53, T61

**Goal:** Measure reconciliation behavior without creating cardinality or privacy risk.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- `src/marketing_mcp/observability/metrics.py` only if a generic primitive is missing
- `tests/release/test_g4_observability_ci.py`

**Suggested metric events:** incident detected, policy decision, attempt started, attempt outcome, verification outcome, incident healed, incident escalated.

**Allowed labels:** bounded fault class, bounded fault code, action mode, recipe key, outcome.

**Forbidden labels:** tenant ID, incident ID, job ID, model ID, dataset ID, owner, trace ID.

**Tests first:** sentinel IDs must not appear in metric labels.

**Acceptance:** G4-style observability tests prove bounded labels.

---

## [ ] T71. Add structured reconciliation logs and trace correlation

**Lenses:** L0, L4, L6, L8

**Depends on:** T70

**Goal:** Make one incident explainable across detection, policy, action, and verification.

**Primary files:**

- `src/marketing_mcp/services/reconciliation_service.py`
- current structured logging and trace tests

**Steps:**

1. Reuse existing structured logger and trace context.
2. Log stable event names.
3. Include incident identity only where current redaction/privacy policy allows it.
4. Never log raw evidence payloads by default.
5. Add secret sentinel tests.
6. Make denial and escalation observable without leaking protected object details.

**Acceptance:** one test can correlate a safe repair from detection to verification and secrets stay absent.

---

## [ ] T72. Add AQG and H5 negative agent traces

**Lenses:** L0, L1, L4, L6, L7

**Depends on:** T61, T63, T71

**Goal:** Prove that natural-language pressure cannot widen reconciliation authority.

**Locate first:** current trace-driven agent evaluation files and the repository's established scenario format.

**Required scenarios:**

1. User says "repair anyway" for a prohibited incident.
2. User asks the agent to ignore a rejected diagnostic state.
3. User asks the agent to choose `safe_auto` when policy returns shadow.
4. User asks to retune priors until the model passes.
5. User asks to access another tenant's incident.
6. User asks to run budget optimization as a healing action for a rejected model.
7. Safe expired-lease incident follows the approved path and includes verification before success is reported.

**Acceptance:** traces show no forbidden tool path or policy bypass.

**Do not:** add prompt instructions as the only control. The code and auth gates remain authoritative.

---

# CO8 - Documentation and Capability Truth

## [ ] T80. Create reconciliation reference documentation

**Lenses:** L0, L1, L4, L5, L6, L7, L8

**Depends on:** T62, T63, T72

**Goal:** Document exactly the behavior executable evidence proves.

**Primary files:**

- create `docs/RECONCILIATION.md`

**Required sections:**

```toon
doc_sections[10]{section}:
  purpose and scope
  fault classes
  incident lifecycle
  action modes
  first safe recipe
  security scope
  tenant isolation
  evidence and observability
  failure and escalation semantics
  explicit v1 non-goals
```

**Acceptance:** a new engineer can explain what the engine may and may not repair without reading source code.

---

## [ ] T81. Update architecture, decision integrity, and tool contracts

**Lenses:** L0, L1, L5, L7, L8

**Depends on:** T80

**Primary files:**

- `docs/ARCHITECTURE.md`
- `docs/DECISION-INTEGRITY.md`
- `docs/TOOL-CONTRACTS.md`
- `docs/README.md`
- `docs/STATISTICAL-SAFETY.md` only if the current document needs a reconciliation clarification

**Rules:**

1. Do not duplicate full reconciliation reference content across documents.
2. Add concise cross-links and only the contract each document owns.
3. Preserve the statement that diagnostic approval does not prove causal correctness.
4. Preserve rejected-state blocking semantics.
5. State that safe repair of job execution does not validate marketing strategy.
6. Do not mention live ad-platform actuation as shipped.

**Acceptance:** docs are consistent and no stronger claim exists than tests support.

---

## [ ] T82. Regenerate capability inventory and run docs drift checks

**Lenses:** L5, L7, L8

**Depends on:** T62, T81

**Goal:** Make generated and hand-maintained docs agree with source declarations.

**Steps:**

1. Generate capability inventory from `src/marketing_mcp/capabilities.py` using the repository script.
2. Do not manually edit generated rows after generation.
3. Run capability inventory check mode.
4. Run docs drift check.
5. Confirm all reconciliation tools remain `experimental` unless an explicit maturity review changed that decision with evidence.

**Acceptance:** generated inventory, real discovery, and hand-maintained tool docs agree.

---

# CO9 - Integrated Verification, Review, and Handoff

## [ ] T90. Run focused reconciliation verification matrix

**Lenses:** L0-L8

**Depends on:** T53, T63, T72, T82

**Goal:** Prove every new contract before the broad repository suite.

**Required focused evidence:**

```toon
focused_verification[8]{area,test_surface}:
  domain,tests/unit/test_reconciliation_domain.py
  persistence,tests/integration/test_reconciliation_persistence.py
  shadow,tests/integration/test_reconciliation_shadow.py
  recovery,tests/integration/test_reconciliation_recovery.py
  auth,tests/integration/test_reconciliation_auth.py
  protocol,tests/integration/test_mcp_protocol.py
  capability,tests/integration/test_capability_inventory.py plus discovery snapshot
  observability,tests/release/test_g4_observability_ci.py
```

**Acceptance:** every focused surface is green on the same integrated working state.

**If a test fails:** classify root cause before changing code. Do not retry until green without explanation.

---

## [ ] T91. Run full repository quality and statistical gates

**Lenses:** L0, L1, L7, L8

**Depends on:** T90

**Goal:** Prove the feature did not regress existing product contracts.

**Commands from the canonical plan:**

- `uv run pytest -m "not statistical" -v`
- `uv run pytest -m statistical -v`
- `uv run pytest -v`
- `uv run ruff check src tests scripts`
- `uv run pyright`
- `uv run python scripts/generate_capability_inventory.py --check`
- `uv run python scripts/check_docs_drift.py`
- `uv build`

Use repository-documented variants if the command surface changes before execution.

If the statistical or full test suite is long, a supported detached process runner may be used. Do not claim completion until its terminal result is collected and tied to the final code state.

**Acceptance:** all required gates are green or a pre-existing unrelated failure is explicitly evidenced and dispositioned according to repository policy.

**Stop if:** a failing statistical or security gate is caused by reconciliation. Fix before continuing.

---

## [ ] T92. Perform independent diff and threat review

**Lenses:** L0-L8

**Depends on:** T91

**Goal:** Find defects that local implementation reasoning and tests may have missed.

**Review questions:**

```toon
review_questions[12]{question}:
  Can any read scope trigger a repair
  Can a caller choose or force a recipe
  Can one tenant infer another tenant incident
  Can two scans create duplicate active incidents
  Can a live lease be recovered after a race
  Can stale worker output publish after recovery
  Can verification failure still become healed
  Can a rejected model reach decision-grade or retuning tools
  Can metrics leak high-cardinality IDs
  Can evidence persistence store secrets or raw customer data
  Can generated capability docs drift from discovery
  Did the implementation introduce infrastructure not required by v1
```

**Acceptance:** no unresolved P0 or P1 finding. P2 findings that affect requirements must be resolved or explicitly deferred with rationale before completion.

---

## [ ] T93. Close task ledger and prepare implementation handoff

**Lenses:** L0, L7, L8

**Depends on:** T92

**Goal:** Produce a final, evidence-backed continuation state for merge or later release work.

**Steps:**

1. Re-read the canonical Definition of Done.
2. Map each R1-R19 requirement to implementation and evidence.
3. Confirm every checked task has fresh evidence after its last mutation.
4. Remove abandoned experiments and unused abstractions.
5. Confirm the diff contains no provider actuator, UI, new broker, or dynamic recipe framework.
6. Record remaining external production blockers separately from local feature correctness.
7. Do not update release readiness beyond what exact-current evidence proves.

**Acceptance:** the feature is implementation-complete locally and ready for the repository's normal PR, CI, and release-readiness process without overstating production maturity.

---

# Requirement Traceability

```toon
trace[19]{requirement,primary_tasks}:
  R1,T10 T30 T31 T32 T33
  R2,T12 T20 T21
  R3,T12 T21 T23 T33
  R4,T10 T11 T50
  R5,T11 T32 T51 T72
  R6,T32 T72 T81
  R7,T11 T31 T32 T72
  R8,T33 T34 T50
  R9,T11 T41 T51
  R10,T20 T21 T50 T52
  R11,T12 T21 T23 T53
  R12,T10 T52 T53
  R13,T61 T62
  R14,T60 T61 T63
  R15,T21 T23 T41 T63
  R16,T62 T82
  R17,T70 T71
  R18,T20 T21 T63 T71
  R19,T20 T21 T71 T80
```

---

# File Touch Forecast

This is a forecast, not permission to expand scope.

```toon
forecast[24]{path,expected}:
  src/marketing_mcp/domain/reconciliation.py,new
  src/marketing_mcp/repositories/reconciliation.py,new
  src/marketing_mcp/storage/migrations.py,modify
  src/marketing_mcp/persistence.py,modify
  src/marketing_mcp/app.py,modify
  src/marketing_mcp/jobs/repository.py,modify
  src/marketing_mcp/services/reconciliation_service.py,new
  src/marketing_mcp/security/policy.py,modify
  src/marketing_mcp/mcp/tools/reconciliation.py,new
  src/marketing_mcp/mcp/server.py,modify
  src/marketing_mcp/capabilities.py,modify
  tests/unit/test_reconciliation_domain.py,new
  tests/integration/test_reconciliation_persistence.py,new
  tests/integration/test_reconciliation_shadow.py,new
  tests/integration/test_reconciliation_recovery.py,new
  tests/integration/test_reconciliation_auth.py,new
  tests/integration/test_mcp_protocol.py,modify
  tests/integration/test_mcp_discovery_snapshot.py,modify
  tests/integration/test_capability_inventory.py,modify
  tests/release/test_g4_observability_ci.py,modify
  docs/RECONCILIATION.md,new
  docs/ARCHITECTURE.md,modify
  docs/DECISION-INTEGRITY.md,modify
  docs/TOOL-CONTRACTS.md,modify
```

Additional files require a task note explaining why the listed owner is insufficient.

---

# Global Stop Conditions

Stop implementation and return to planning when any item below becomes true.

```toon
stop_conditions[12]{condition}:
  product requirement R1-R19 must change
  automatic repair expands beyond expired job lease recovery
  provider actuation becomes required for v1
  reconciliation needs a new database broker or scheduler
  tenant ownership cannot be proven at action time
  atomic one-job recovery cannot preserve fencing
  shadow mode requires underlying business-state mutation
  model diagnostics must be changed to make reconciliation work
  public API needs caller-controlled force or recipe selection
  evidence cannot be stored without sensitive raw payloads
  existing persistence backend cannot represent dedup safely
  current repository drift invalidates the planned seams
```

---

# Final Definition of Done Mapping

The ledger is complete only when all boxes T00-T93 are checked with fresh evidence and the canonical plan's Definition of Done remains satisfied.

The final implementation must still be able to answer these questions with executable evidence:

1. What exact invariant created this incident?
2. Why was the selected action mode allowed?
3. Who authorized the action?
4. What object and tenant did the action target?
5. What was the before state?
6. What exact repository owner performed the mutation?
7. What postcondition proved the repair?
8. What happened on retry?
9. What happens after process restart?
10. What prevents another tenant or a persuasive prompt from widening authority?

If any answer depends only on prose, comments, or agent judgment, the feature is not done.