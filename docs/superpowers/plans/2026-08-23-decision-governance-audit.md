# Decision Governance and Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the decision history, auditability, model lifecycle, refresh policy, and evidence governance required for a decision-grade v1.0 release after the v0.5 production service foundations are stable.

**Architecture:** Record append-only audit events around resource access and decision actions, and persist first-class decision records that reference immutable model/dataset/artifact identities. Add lifecycle policy services for champion/challenger, refresh recommendations, and archival without mutating historical evidence.

**Tech Stack:** PostgreSQL production metadata, object storage, job system, security principals/scopes, structured observability, Pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Audit events are append-only in application behavior.
- Decision history never stores fabricated LLM calculations as statistical evidence.
- Historical decisions retain the exact model, dataset, configuration, and package provenance used at decision time.
- Archiving a model never deletes or rewrites past decision records.
- User-facing explanations may be regenerated, but the underlying statistical evidence reference remains immutable.

---

### Task 1: Define audit event contract

**Files:**
- Create: `src/marketing_mcp/audit/models.py`
- Create: `src/marketing_mcp/audit/repository.py`
- Test: `tests/unit/test_audit_models.py`

**Audit event fields:**
- event_id
- occurred_at
- request_id
- principal subject hash/safe ID
- tenant_id
- action
- resource_type
- resource_id
- tool_name
- outcome
- error_code
- evidence_refs
- client metadata limited to safe values

- [ ] Define stable action names for dataset, model, job, decision, admin, and security events.
- [ ] Prohibit raw tokens, raw datasets, and unbounded request payloads in audit records.
- [ ] Add schema validation and redaction tests.
- [ ] Commit.

### Task 2: Implement append-only audit repository

**Files:**
- Create: `src/marketing_mcp/audit/postgres.py`
- Add migration for `audit_events`
- Test: `tests/integration/test_audit_repository.py`

- [ ] Use insert-only application API.
- [ ] Index tenant/principal, action, resource, and timestamp.
- [ ] Restrict administrative deletion to explicit retention tooling outside normal request paths.
- [ ] Test transaction behavior when the primary operation succeeds but audit insertion fails according to chosen policy.
- [ ] Document which actions are fail-closed if audit persistence is unavailable.
- [ ] Commit.

### Task 3: Instrument decision-grade tool actions

**Files:**
- Modify: MCP execution wrapper or service boundary
- Test: `tests/contract/test_decision_audit_events.py`

**Audit at minimum:**
- fit submission/result
- diagnose result
- calibration
- budget simulation
- budget optimization
- flighting
- CLV model fit/predict where customer data is involved
- model comparison
- archive
- auth/authorization denials

- [ ] Write parameterized tests proving successful and rejected decision calls emit the expected event family.
- [ ] Store only safe result summaries and immutable evidence references.
- [ ] Commit.

### Task 4: Define first-class decision records

**Files:**
- Create: `src/marketing_mcp/decisions/records.py`
- Create: `src/marketing_mcp/decisions/repository.py`
- Add migration for `decision_records`
- Test: `tests/unit/test_decision_records.py`

**Decision record fields:**
- decision_id
- decision_type
- principal/tenant
- model_id
- model artifact checksum
- dataset_id/fingerprint
- config hash
- diagnostic state at decision time
- scenario/job IDs
- recommendation summary
- posterior evidence refs
- warnings
- created_at
- supersedes decision ID if applicable

- [ ] Make decision records immutable after creation except for administrative annotation fields kept separate from evidence.
- [ ] Do not store only natural-language recommendation text without structured evidence references.
- [ ] Commit.

### Task 5: Add decision history tools/resources

**Files:**
- Create or modify: `src/marketing_mcp/mcp/tools/decision_history.py`
- Modify: MCP resources registry
- Test: `tests/integration/test_decision_history_mcp.py`

**Tools/resources:**
- list decisions for authorized principal/tenant
- get decision record
- compare two decisions
- get evidence/provenance chain

- [ ] Require `marketing:read` for own-tenant read and stronger scope for administrative cross-tenant access.
- [ ] Prevent history tools from recalculating outcomes when the job is simply retrieval.
- [ ] Commit.

### Task 6: Add model lifecycle states

**Files:**
- Modify: `src/marketing_mcp/schemas/models.py`
- Create: `src/marketing_mcp/models/lifecycle.py`
- Test: `tests/unit/test_model_lifecycle.py`

**Lifecycle states:**

```text
candidate
validated
champion
challenger
stale
retired
archived
```

Keep fit execution status separate from lifecycle state.

- [ ] Add legal transition matrix.
- [ ] Prevent a rejected diagnostics model from becoming champion.
- [ ] Require evidence for champion promotion.
- [ ] Preserve parent/child lineage.
- [ ] Commit.

### Task 7: Add champion/challenger policy

**Files:**
- Create: `src/marketing_mcp/models/champion.py`
- Test: `tests/statistical/test_champion_challenger_policy.py`

**Inputs:**
- predictive diagnostics
- time-slice CV
- information criteria reliability
- calibration evidence
- decision stability

- [ ] Never select champion from one metric alone.
- [ ] Refuse promotion when reliability diagnostics are unsafe.
- [ ] Return structured reasons and evidence references.
- [ ] Add real statistical fixtures for promotion/no-promotion examples.
- [ ] Commit.

### Task 8: Add model freshness and refresh policy

**Files:**
- Create: `src/marketing_mcp/models/freshness.py`
- Test: `tests/unit/test_model_freshness.py`

**Signals:**
- new data periods since fit
- material spend distribution shift
- target distribution shift
- repeated extrapolation warnings
- elapsed business cadence
- new lift evidence
- upstream dependency/model definition change

- [ ] Produce `fresh`, `review`, or `refresh_recommended`, not an automatic refit command.
- [ ] Keep thresholds configurable and documented.
- [ ] Commit.

### Task 9: Add decision sensitivity report

**Files:**
- Create: `src/marketing_mcp/decisions/sensitivity.py`
- Test: `tests/statistical/test_decision_sensitivity.py`

**Questions answered:**
- does channel rank change across posterior draws?
- does recommendation change under plausible prior variants?
- does recommendation change under budget +/- range?
- does recommendation change across validated model candidates?

- [ ] Return probability/stability summaries rather than categorical certainty only.
- [ ] Include exact models/scenarios used in the report.
- [ ] Commit.

### Task 10: Add "what would change the decision" evidence policy

**Files:**
- Modify or extend: measurement recommendation domain
- Create: `src/marketing_mcp/decisions/value_of_information.py`
- Test: `tests/unit/test_value_of_information_policy.py`

- [ ] Rank evidence gaps only when a decision is materially sensitive to them.
- [ ] Distinguish more history, model revision, lift experiment, geo experiment, and business constraint clarification.
- [ ] Explicitly return no single recommended experiment when evidence does not support one.
- [ ] Commit.

### Task 11: Add retention and deletion policy

**Files:**
- Create: `docs/operations/DATA-RETENTION.md`
- Create: `src/marketing_mcp/governance/retention.py`
- Test: `tests/unit/test_retention_policy.py`

**Resource classes:**
- raw datasets
- model artifacts
- plots
- jobs
- audit events
- decision records

- [ ] Make retention profile configurable.
- [ ] Preserve decision evidence references for the required governance period or mark records unavailable with an explicit tombstone if policy requires deletion.
- [ ] Require administrative scope for destructive retention actions.
- [ ] Commit.

### Task 12: Add v1.0 Decision-Grade Gate

**Files:**
- Create: `tests/release/test_m5_decision_grade.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- decision actions create immutable decision records
- audit events exist for protected actions
- historical decisions retain exact provenance
- champion promotion follows validated policy
- stale model detection works
- decision sensitivity has statistical evidence
- agent evals surface material sensitivity/warnings

- [ ] Add the M5 gate to the v1.0 release workflow.
- [ ] Do not block the earlier v0.5 production candidate on unfinished M5 features if G0-G5 are otherwise green and release wording remains accurate.

## Acceptance Criteria

This plan is complete when:

- protected actions produce safe append-only audit events
- decision outputs have immutable evidence-backed records
- model lifecycle is separate from fit status
- champion/challenger promotion is evidence-governed
- stale models can be identified without autonomous refitting
- decision sensitivity and evidence-gap recommendations are reproducible
- v1.0 has an explicit M5 Decision-Grade release gate