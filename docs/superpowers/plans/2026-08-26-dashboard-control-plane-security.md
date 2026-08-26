# Dashboard Control Plane Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current browser-generated, plaintext-persisted API-key workflow with a backend-controlled credential control plane that issues secrets once, stores only verifiers, supports revocation/audit, and is the same credential source used by the MCP server.

**Architecture:** Treat the dashboard as a UI client, never as the authority for credentials. Add a backend credential service/repository, authenticated control-plane endpoints, verifier-only storage, one-time secret return, revocation and audit records, then remove raw-key persistence from Firestore/localStorage and wire MCP authentication to the same repository.

**Tech Stack:** Python service boundary, Starlette HTTP endpoints or a focused control API, PostgreSQL/SQLite credential repository contracts, React dashboard, Firebase Auth only for dashboard user authentication where retained.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Browser code must never persist a raw MCP API key.
- Firestore must never contain a raw MCP API key or reversible verifier.
- Raw keys are shown exactly once at creation and cannot be retrieved later.
- Key revocation must affect the same repository consulted by MCP authentication.
- Key lookup uses constant-time verifier comparison or keyed hash lookup appropriate to the selected design.
- Dashboard auth identity and MCP credential identity must have an explicit ownership mapping.
- Existing prototype Firestore key documents must be treated as compromised and rotated, not migrated as trusted secrets.

---

### Task 1: Freeze and characterize the current unsafe key flow

**Files:**
- Modify: `dashboard/src/components/ApiKeyManager.tsx`
- Create: `dashboard/src/components/ApiKeyManager.test.tsx`
- Create: `tests/security/test_dashboard_credential_static_policy.py`
- Modify: `docs/SECURITY.md`

- [ ] Add a visible development-only warning/freeze that key creation is disabled until the backend flow lands
- [ ] Add static tests rejecting these patterns outside tests/archive:

```text
keyHash: fullSecret
keySecret persisted to localStorage
addDoc(api_keys, raw secret)
```

- [ ] Run:

```bash
uv run pytest tests/security/test_dashboard_credential_static_policy.py -v
cd dashboard && bun test
```

- [ ] Commit:

```bash
git add dashboard tests/security docs/SECURITY.md
git commit -m "security(dashboard): freeze unsafe browser key issuance"
```

---

### Task 2: Define credential domain contracts

**Files:**
- Create: `src/marketing_mcp/credentials/models.py`
- Create: `src/marketing_mcp/credentials/repository.py`
- Create: `src/marketing_mcp/credentials/service.py`
- Test: `tests/unit/test_credential_service.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class CredentialRecord:
    credential_id: str
    tenant_id: str
    owner_subject: str
    name: str
    prefix: str
    verifier: str
    scopes: frozenset[str]
    status: Literal["active", "revoked"]
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None

@dataclass(frozen=True)
class IssuedCredential:
    record: CredentialRecord
    secret: str

class CredentialRepository(Protocol):
    def create(self, record: CredentialRecord) -> None: ...
    def get_by_id(self, credential_id: str) -> CredentialRecord: ...
    def find_active_candidates(self, prefix: str) -> Sequence[CredentialRecord]: ...
    def revoke(self, credential_id: str, *, revoked_at: datetime) -> CredentialRecord: ...
```

- [ ] Write tests proving issued secret is absent from persisted record
- [ ] Write tests for scoped credentials and revocation
- [ ] Implement `CredentialService.issue()`, `verify()`, `revoke()`, `list_for_owner()`
- [ ] Use a cryptographic random 256-bit secret and a non-reversible verifier strategy
- [ ] Run:

```bash
uv run pytest tests/unit/test_credential_service.py -v
```

- [ ] Commit

---

### Task 3: Implement local and production credential repositories

**Files:**
- Create: `src/marketing_mcp/credentials/sqlite_repository.py`
- Create: `src/marketing_mcp/credentials/postgres_repository.py`
- Modify: storage migrations
- Create: `tests/contract/test_credential_repository_contract.py`

- [ ] Add typed columns for credential identity, ownership, prefix, verifier, scopes, status and timestamps
- [ ] Never place verifier/secret inside generic JSON payloads returned to dashboard clients
- [ ] Test identical repository behavior for SQLite/Postgres
- [ ] Add uniqueness constraints for credential IDs and active prefix/verifier lookup strategy
- [ ] Run repository contract tests against both implementations
- [ ] Commit

---

### Task 4: Make MCP authentication consume the credential service

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Modify: `src/marketing_mcp/security/oauth.py`
- Modify: `src/marketing_mcp/app.py`
- Test: `tests/integration/test_api_key_repository_auth.py`

**Target flow:**

```text
X-API-Key / Bearer API key
 -> CredentialService.verify(secret)
 -> CredentialRecord
 -> Principal(subject, tenant_id, scopes)
 -> ExecutionContext
```

- [ ] Remove production dependence on in-memory/env key lists except explicit local bootstrap mode
- [ ] Preserve OAuth as a separate verifier path producing the same `Principal` model
- [ ] Test active key accepted, revoked key rejected, wrong key rejected, owner/tenant/scopes propagated
- [ ] Test revocation takes effect without process restart
- [ ] Commit

---

### Task 5: Add authenticated credential-management endpoints

**Files:**
- Create: `src/marketing_mcp/http/credentials.py`
- Modify: HTTP app composition
- Test: `tests/integration/test_credential_control_api.py`

**Endpoints:**

```text
GET    /control/credentials
POST   /control/credentials
DELETE /control/credentials/{credential_id}
```

Creation response may contain raw `secret` once; list responses never contain it

- [ ] Require dashboard user authentication and map it to principal/tenant
- [ ] Validate requested scopes against allowed delegation policy
- [ ] Prevent a user from granting scopes they do not possess
- [ ] Prevent listing/revoking another tenant's credentials
- [ ] Add CSRF/origin policy appropriate to the chosen dashboard auth model
- [ ] Commit

---

### Task 6: Refactor dashboard to backend-issued credentials

**Files:**
- Modify: `dashboard/src/components/ApiKeyManager.tsx`
- Create: `dashboard/src/api/credentials.ts`
- Modify: `dashboard/src/types/index.ts`
- Remove key-specific Firestore write logic
- Test: dashboard component/API tests

- [ ] Delete browser-side `generateRandomKey()`
- [ ] Delete `keySecret` from persistent client types
- [ ] Delete raw-key localStorage fallback
- [ ] POST creation request to backend and display returned secret once in component state only
- [ ] List only prefix/name/status/scopes/timestamps
- [ ] Revoke through backend and refresh list
- [ ] Add copy-once UX without re-fetch capability
- [ ] Run dashboard lint/tests/build
- [ ] Commit

---

### Task 7: Remove Firestore credential authority and rotate prototype secrets

**Files:**
- Modify: `dashboard/firestore.rules`
- Modify: dashboard Firebase data access
- Create: `docs/runbooks/credential-rotation.md`
- Create: `scripts/audit_legacy_dashboard_keys.py`

- [ ] Make `/api_keys` read/write impossible from the production dashboard or remove the collection path entirely
- [ ] Provide an audit script that reports legacy key document IDs/owners without printing raw secret values
- [ ] Document that all legacy dashboard-created keys must be revoked and reissued
- [ ] Ensure no migration copies `keyHash` plaintext into the new repository
- [ ] Commit

---

### Task 8: Add credential audit events and usage metadata

**Files:**
- Create/extend: audit repository from decision-governance plan
- Modify: credential service/auth path
- Test: `tests/integration/test_credential_audit.py`

**Events:**

```text
credential.created
credential.used
credential.revoked
credential.authentication_failed
```

- [ ] Store credential ID/prefix and safe subject identifiers only
- [ ] Never log raw credential or verifier
- [ ] Rate-limit/update `last_used_at` without writing on every request if that causes contention
- [ ] Commit

---

### Task 9: Establish H3 Credential Control Plane gate

**Files:**
- Create: `tests/release/test_h3_credential_control_plane.py`
- Modify: `docs/PRODUCTION-READINESS.md`

**Assertions:**

- no dashboard raw-secret persistence patterns exist
- credential creation is backend-only
- persisted credential records contain verifier but no raw secret
- list endpoint never returns secret/verifier
- revoke invalidates real MCP authentication
- scope/tenant identity propagates from issued key
- legacy Firestore key authority is disabled
- credential audit events redact secrets

- [ ] Run full credential/security suite
- [ ] Mark H3 green only from CI evidence
- [ ] Commit

## Acceptance Criteria

This plan is complete when the dashboard is only a client of a backend credential authority, raw keys are one-time values, revocation affects real MCP access, and no parallel Firestore/localStorage credential system remains
