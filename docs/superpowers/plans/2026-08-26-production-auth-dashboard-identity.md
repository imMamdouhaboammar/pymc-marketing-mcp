# Production Auth and Dashboard Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the production HTTP and dashboard identity path use one explicit trust model, with external issuer verification, scoped principals, secure API-key issuance, and no identity ambiguity between dashboard tokens and MCP tokens.

**Architecture:** Keep API-key authentication as a supported first-party credential path, but make production bearer-token verification issuer-driven through JWKS/issuer/audience rather than a local HS256-only shortcut. Normalize every successful credential into one `Principal`. The dashboard authenticates to the control plane using the configured external identity provider; issued MCP API keys remain verifier-backed and tenant/scoped.

**Tech Stack:** Starlette middleware, PyJWT/JWKS, MCP auth types, external OIDC/OAuth issuer, existing `RemoteJWTVerifier`, `CredentialService`, dashboard TypeScript client, Bun, Vitest, pytest/httpx/MCP ClientSession

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- Production HTTP must fail closed when issuer/audience configuration is missing or invalid
- Query-string credentials remain rejected
- Bearer tokens must validate signature, issuer, audience, expiry, subject, and scopes
- Unknown scopes must be rejected rather than silently promoted
- API-key scopes cannot exceed the issuer principal's scopes unless the actor has explicit admin scope
- Raw MCP API keys are returned once and are never persisted client-side after the creation screen is dismissed
- The dashboard authentication token and the generated MCP API key are different credentials with different purposes
- Error responses must not expose token bodies, signing details, tenant IDs of foreign objects, raw secrets, verifier hashes, or salts

---

## Task 1: Introduce one token-verifier abstraction in the active auth path

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Modify: `src/marketing_mcp/security/oauth.py`
- Modify: `src/marketing_mcp/config.py`
- Test: `tests/unit/test_auth_verifier_selection.py`

**Interfaces:**
- Consumes: security profile and auth configuration
- Produces: `BearerTokenVerifier.verify(token: str) -> AuthContext | None`

- [ ] **Step 1: Write verifier-selection tests**

Required cases:

```text
local/test HS256 profile -> local verifier
production OAuth profile -> remote JWKS verifier
production profile without issuer/audience -> CONFIG_INVALID
unknown profile -> CONFIG_INVALID
```

- [ ] **Step 2: Adapt `RemoteJWTVerifier` into the active auth manager**

Do not leave it as an isolated SDK utility. `AuthManager.authenticate()` must delegate bearer-token validation to the selected verifier.

- [ ] **Step 3: Preserve API-key verification as a separate branch**

API keys starting with the application credential prefix are verified by `CredentialService`; opaque bearer tokens go to the configured bearer-token verifier.

- [ ] **Step 4: Remove production dependence on local HS256 secret**

HS256 may remain for tests/private deployments, but production OAuth configuration must select JWKS-based verification.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_auth_verifier_selection.py tests/unit/test_oauth_verifier.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/auth.py src/marketing_mcp/security/oauth.py src/marketing_mcp/config.py tests/unit/test_auth_verifier_selection.py
git commit -m "feat: wire production bearer verifier into auth runtime"
```

## Task 2: Normalize issuer claims into the MCP Principal

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Modify: `src/marketing_mcp/security/principal.py`
- Test: `tests/unit/test_principal_claim_mapping.py`

**Interfaces:**
- Consumes: verified bearer claims
- Produces: `Principal(subject, auth_type, scopes, tenant_id)`

- [ ] **Step 1: Define exact claim mapping**

Canonical mapping:

```text
subject <- sub
scopes <- scope or scp
tenant_id <- tenant_id, or configured tenant claim name
auth_type <- oauth
```

Do not derive tenant identity from email, display name, or client-controlled request headers.

- [ ] **Step 2: Write missing-tenant behavior tests**

For production multi-tenant mode, a token missing the required tenant claim must fail authentication. For explicitly configured single-tenant beta mode, map to the configured fixed tenant ID.

- [ ] **Step 3: Ensure wildcard scope is admin-only**

External tokens may contain `*` only if the deployment explicitly allows wildcard/admin claims. Unknown scopes fail validation.

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/auth.py src/marketing_mcp/security/principal.py tests/unit/test_principal_claim_mapping.py
git commit -m "fix: normalize verified identity claims into principals"
```

## Task 3: Remove contradictory query-token guidance

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Test: `tests/unit/test_auth_error_contract.py`

**Interfaces:**
- Consumes: unauthenticated HTTP request
- Produces: safe supported-schemes error contract

- [ ] **Step 1: Write the failing contract test**

Assert a 401 response includes only:

```text
Authorization: Bearer <TOKEN>
X-API-Key: <API_KEY>
```

and does not contain `?token=`, `?api_key=`, the submitted token, JWT payload fragments, or verifier details.

- [ ] **Step 2: Update `supported_schemes`**

Delete the query-parameter option from the response entirely.

- [ ] **Step 3: Run focused tests**

Run: `uv run pytest tests/unit/test_auth_error_contract.py tests/release/test_g3_remote_security.py -q`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/auth.py tests/unit/test_auth_error_contract.py
git commit -m "fix: remove query credential guidance"
```

## Task 4: Make the dashboard identity provider explicit

**Files:**
- Modify: `dashboard/src/contexts/AuthContext.tsx`
- Modify: `dashboard/src/contexts/authContextDef.ts`
- Modify: `dashboard/src/contexts/useAuth.ts`
- Modify: `dashboard/src/api/credentials.ts`
- Modify: `dashboard/src/components/ApiKeyManager.tsx`
- Create: `dashboard/src/config/auth.ts`
- Create: `dashboard/src/api/credentials.test.ts`
- Modify: `dashboard/package.json`
- Modify: `dashboard/bun.lock`

**Interfaces:**
- Consumes: external dashboard login token
- Produces: `getControlPlaneToken(): Promise<string>` and Authorization bearer token accepted by production control plane

- [ ] **Step 1: Add an explicit control-plane token method to auth context**

Add this interface to `authContextDef.ts`:

```ts
getControlPlaneToken: () => Promise<string>
```

`AuthContext.tsx` is the only place that translates the configured identity provider session into this token. `ApiKeyManager` must not call Firebase-specific `getIdToken()` directly.

- [ ] **Step 2: Define dashboard auth configuration**

Create `dashboard/src/config/auth.ts` with public issuer/audience/client configuration sourced from Vite environment variables. Do not put client secrets or signing keys in browser configuration.

- [ ] **Step 3: Add a real dashboard test runner**

Add `vitest` to `devDependencies` and add:

```json
"test": "vitest run"
```

to `dashboard/package.json`, then update `dashboard/bun.lock` with Bun.

- [ ] **Step 4: Write API client tests**

In `dashboard/src/api/credentials.test.ts`, mock `fetch` and assert `fetchCredentials`, `createCredential`, and `revokeCredential` send only the provided control-plane token as `Authorization: Bearer ...`. Assert no selected MCP key prefix is used as a control-plane credential.

- [ ] **Step 5: Remove provider assumptions from `ApiKeyManager`**

Use `const { user, getControlPlaneToken } = useAuth()` and obtain the token only through `getControlPlaneToken()` for credential API calls.

- [ ] **Step 6: Keep newly issued MCP secret in ephemeral component state only**

The full `response.secret` may exist only in React state for the one-time display. Do not write it to localStorage, sessionStorage, IndexedDB, Firestore, URL/query state, or a persisted context. After dismiss/navigation/reload, only public credential DTO data and prefixes may be loaded again.

- [ ] **Step 7: Run dashboard verification**

Run:

```bash
cd dashboard
bun install --frozen-lockfile
bun run test
bun run lint
bun run build
```

Expected: all commands exit `0`

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/config/auth.ts dashboard/src/api/credentials.ts dashboard/src/api/credentials.test.ts dashboard/src/components/ApiKeyManager.tsx dashboard/src/contexts/AuthContext.tsx dashboard/src/contexts/authContextDef.ts dashboard/src/contexts/useAuth.ts dashboard/package.json dashboard/bun.lock
git commit -m "fix: align dashboard control-plane identity with production auth"
```

## Task 5: Add full external-issuer MCP E2E tests

**Files:**
- Create: `tests/integration/test_production_oidc_mcp.py`
- Modify: `tests/release/test_h1_identity_propagation.py`
- Modify: `tests/release/test_h3_credential_control_plane.py`

**Interfaces:**
- Consumes: test JWKS issuer, signed bearer tokens, MCP HTTP session
- Produces: production-like identity propagation evidence

- [ ] **Step 1: Create deterministic test signing keys/JWKS at test runtime**

Generate test-only RSA keys in memory or test fixtures. Do not commit a reusable production-like private key.

- [ ] **Step 2: Test valid issuer token through real MCP session**

Verify initialize succeeds, a read tool succeeds, and the tool sees the expected tenant/scopes.

- [ ] **Step 3: Test invalid token families**

Required failures:

```text
wrong issuer
wrong audience
expired token
unknown signing key
missing subject
missing required tenant claim
unknown scope
```

All must produce authentication failure without leaking the reason beyond the safe public error contract.

- [ ] **Step 4: Test issuer principal issuing an API key**

Issue a read-only API key through `/control/credentials`, use it with MCP, verify decision tool denial, revoke it, then verify 401 on the next request.

- [ ] **Step 5: Test cross-tenant denial via external tokens**

Tenant B must not read Tenant A model through either a tool or MCP resource.

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_production_oidc_mcp.py tests/release/test_h1_identity_propagation.py tests/release/test_h3_credential_control_plane.py
git commit -m "test: prove production issuer identity through MCP"
```

## Task 6: Harden credential enumeration and foreign-object errors

**Files:**
- Modify: `src/marketing_mcp/security/ownership.py`
- Modify: `src/marketing_mcp/credentials/service.py`
- Test: `tests/unit/test_authorization_non_enumeration.py`

**Interfaces:**
- Consumes: foreign tenant/resource access attempt
- Produces: non-enumerating safe error envelope

- [ ] **Step 1: Write leakage tests**

Foreign access errors must not include:

```text
foreign tenant ID
foreign owner subject
credential verifier
credential salt
raw secret
```

- [ ] **Step 2: Standardize caller-safe foreign-object errors**

Use `AUTH_FORBIDDEN` for authenticated cross-tenant/owner denials. Public evidence may include only `resource_type` and attempted `action`; it must not include foreign owner/tenant identity. Preserve detailed identifiers only in access-controlled, redacted operational logs.

- [ ] **Step 3: Commit**

```bash
git add src/marketing_mcp/security/ownership.py src/marketing_mcp/credentials/service.py tests/unit/test_authorization_non_enumeration.py
git commit -m "fix: prevent authorization object enumeration"
```

## Task 7: Add production startup posture tests

**Files:**
- Modify: `tests/release/test_g3_remote_security.py`
- Create: `tests/release/test_production_auth_posture.py`

**Interfaces:**
- Consumes: security profile configuration
- Produces: startup fail-closed proof

- [ ] **Step 1: Test every invalid production posture**

Reject:

```text
production HTTP with auth disabled
production OAuth without issuer
production OAuth without audience
production multi-tenant mode without tenant claim mapping
production mode using query credentials
production mode with an explicitly insecure local-only profile
```

- [ ] **Step 2: Test one valid production posture**

Application construction must succeed with issuer, audience, tenant-claim mapping, and external persistence configuration supplied.

- [ ] **Step 3: Commit**

```bash
git add tests/release/test_g3_remote_security.py tests/release/test_production_auth_posture.py
git commit -m "test: enforce production auth startup posture"
```

## Acceptance criteria

This plan is complete when:

- active production HTTP bearer auth uses issuer/JWKS verification
- wrong issuer/audience/expiry/signature claims fail E2E
- verified claims become the actual MCP `Principal`
- production multi-tenant mode rejects tokens without tenant identity
- query-string credential guidance is completely removed
- dashboard control-plane authentication uses the configured external identity abstraction
- dashboard never persists the raw issued MCP secret
- issuer principals cannot mint API-key scopes they do not possess
- revoked API keys fail immediately across subsequent MCP requests
- foreign tenant/owner details are not exposed in public authorization errors
