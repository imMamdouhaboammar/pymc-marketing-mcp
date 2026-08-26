# Auth Context and Resource Isolation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that every remote MCP tool/resource executes under the authenticated caller identity and can access only resources authorized by scope plus ownership/tenant policy.

**Architecture:** Replace the implicit trusted-context fallback with an explicit request-scoped principal provider for HTTP. Centralize tool/resource authorization behind one policy service, add ownership fields to durable records through versioned migrations, and test the complete HTTP credential -> principal -> tool/resource -> repository path.

**Tech Stack:** MCP Python SDK v2, Starlette/Uvicorn, Pydantic, SQLite migration path for local mode, PostgreSQL-compatible repository contracts, pytest/httpx MCP client.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Trusted local identity is valid only for stdio-local transport.
- Remote HTTP must fail closed if no authenticated principal reaches execution.
- Tool scope and object ownership are separate checks; both must pass.
- MCP resources are protected by the same policy model as tools.
- Existing local records must migrate deterministically to an explicit local owner/tenant.
- Error envelopes may identify the missing scope/resource class, but must not leak another tenant's metadata.
- Admin scope does not imply cross-tenant access unless the policy explicitly grants it.

---

### Task 1: Characterize the HTTP principal propagation gap

**Files:**
- Create: `tests/integration/test_http_scope_propagation.py`
- Read: `src/marketing_mcp/cli.py`
- Read: `src/marketing_mcp/auth.py`
- Read: `src/marketing_mcp/mcp/context.py`
- Read: `src/marketing_mcp/mcp/server.py`

**Interfaces:**
- Consumes: current `AuthManager`, `MCPAuthMiddleware`, `ExecutionContext`, `create_server()`
- Produces: failing end-to-end security tests that cannot pass through `stdio_context_provider()`

- [ ] **Step 1: Write a read-only-token decision-tool test**

```python
async def test_http_read_scope_cannot_call_decision_tool(http_server, read_token):
    result = await call_mcp_tool(
        http_server,
        token=read_token,
        tool="simulate_budget",
        arguments={"config": valid_budget_fixture("owned-model")},
    )
    assert result["error"]["code"] == "AUTH_FORBIDDEN"
```

- [ ] **Step 2: Write an anonymous-principal execution test**

```python
async def test_http_missing_execution_principal_never_falls_back_to_stdio(http_server):
    result = await call_mcp_tool_with_auth_middleware_bypassed_for_test(
        http_server,
        tool="get_model_status",
        arguments={"model_id": "x"},
    )
    assert result["error"]["code"] == "AUTH_REQUIRED"
```

- [ ] **Step 3: Run the tests and prove current behavior is unsafe or unproven**

Run:

```bash
uv run pytest tests/integration/test_http_scope_propagation.py -v
```

Expected: at least the read-only decision-tool assertion fails until principal propagation is implemented.

- [ ] **Step 4: Commit characterization tests only**

```bash
git add tests/integration/test_http_scope_propagation.py
git commit -m "test(security): characterize HTTP principal propagation"
```

---

### Task 2: Define one execution identity model

**Files:**
- Modify: `src/marketing_mcp/security/principal.py`
- Modify: `src/marketing_mcp/mcp/context.py`
- Create: `src/marketing_mcp/security/context.py`
- Test: `tests/unit/test_execution_identity.py`

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class Principal:
    subject: str
    auth_type: str
    scopes: frozenset[str]
    tenant_id: str
    client_id: str | None = None

@dataclass(frozen=True)
class ExecutionContext:
    principal: Principal
    request_id: str
    transport: Literal["stdio", "http"]
```

```python
class ExecutionContextProvider(Protocol):
    def current(self) -> ExecutionContext: ...
```

- [ ] **Step 1: Add tests for local and remote identity invariants**

```python
def test_remote_context_requires_principal(): ...
def test_stdio_context_uses_explicit_local_tenant(): ...
def test_principal_scopes_are_immutable(): ...
```

- [ ] **Step 2: Run focused tests and verify failure**

```bash
uv run pytest tests/unit/test_execution_identity.py -v
```

- [ ] **Step 3: Implement immutable identity/context types and a request-local provider abstraction**

Use a request-scoped context mechanism supported by the pinned SDK/runtime. Do not store current principal in a process-global mutable variable.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest tests/unit/test_execution_identity.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/security src/marketing_mcp/mcp/context.py tests/unit/test_execution_identity.py
git commit -m "refactor(security): define request-scoped execution identity"
```

---

### Task 3: Bridge authenticated HTTP requests into MCP execution context

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Modify: `src/marketing_mcp/cli.py`
- Modify: `src/marketing_mcp/mcp/server.py`
- Modify: `src/marketing_mcp/mcp/context.py`
- Test: `tests/integration/test_http_scope_propagation.py`

**Interfaces:**
- Consumes: `AuthContext`/OAuth verifier result
- Produces: `Principal` bound to the actual MCP request lifecycle

- [ ] **Step 1: Extend the HTTP test matrix**

```python
@pytest.mark.parametrize(
    ("scopes", "tool", "expected"),
    [
        (["marketing:read"], "get_model_status", "DOMAIN_ALLOWED"),
        (["marketing:read"], "simulate_budget", "AUTH_FORBIDDEN"),
        (["marketing:model"], "fit_mmm", "DOMAIN_ALLOWED"),
        (["marketing:model"], "optimize_budget", "AUTH_FORBIDDEN"),
        (["marketing:decide"], "simulate_budget", "DOMAIN_ALLOWED"),
    ],
)
async def test_http_scope_matrix(...): ...
```

- [ ] **Step 2: Make `create_server()` require an explicit context provider for remote mode**

Target contract:

```python
def create_server(
    app: Application | None = None,
    *,
    context_provider: ExecutionContextProvider,
): ...
```

Provide a separate helper for local stdio:

```python
def create_stdio_server(app: Application | None = None):
    return create_server(app, context_provider=TrustedStdioContextProvider())
```

- [ ] **Step 3: Bind middleware-authenticated identity to MCP request execution**

The HTTP adapter must map `request.state.auth` / SDK authorization context into `Principal` and `ExecutionContext` before tool/resource dispatch.

- [ ] **Step 4: Run HTTP auth and scope tests**

```bash
uv run pytest tests/integration/test_mcp_auth_http.py tests/integration/test_http_scope_propagation.py -v
```

Expected: all pass and no remote test depends on stdio trusted identity.

- [ ] **Step 5: Add a static guard**

Create a test that fails if HTTP application construction calls `create_server()` without the explicit remote provider.

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp tests/integration/test_http_scope_propagation.py
git commit -m "fix(security): propagate HTTP principal into MCP execution"
```

---

### Task 4: Replace scope-only checks with an authorization service

**Files:**
- Create: `src/marketing_mcp/security/authorization.py`
- Modify: `src/marketing_mcp/security/policy.py`
- Modify: tool modules under `src/marketing_mcp/mcp/tools/`
- Test: `tests/unit/test_authorization_service.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ResourceIdentity:
    resource_type: str
    resource_id: str
    tenant_id: str
    owner_subject: str

class AuthorizationService:
    def require_scope(self, principal: Principal, scope: str) -> None: ...
    def require_resource_access(
        self,
        principal: Principal,
        resource: ResourceIdentity,
        action: Literal["read", "write", "decide", "admin"],
    ) -> None: ...
```

- [ ] **Step 1: Test same-owner, same-tenant delegated, other-tenant, and admin cases**

```python
def test_owner_can_read_own_model(): ...
def test_other_tenant_is_denied_without_existence_leak(): ...
def test_scope_without_ownership_is_denied(): ...
def test_admin_cross_tenant_requires_explicit_policy(): ...
```

- [ ] **Step 2: Run tests to fail**

```bash
uv run pytest tests/unit/test_authorization_service.py -v
```

- [ ] **Step 3: Implement explicit authorization decisions and stable error codes**

Use:

```text
AUTH_REQUIRED
AUTH_FORBIDDEN
RESOURCE_NOT_FOUND_OR_FORBIDDEN
```

for remote object lookups where existence must not leak.

- [ ] **Step 4: Refactor tool handlers to call the service rather than direct policy helpers**

- [ ] **Step 5: Run unit + existing tool scope tests**

```bash
uv run pytest tests/unit/test_authorization_service.py tests/unit/test_tool_scope_enforcement.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/security src/marketing_mcp/mcp/tools tests/unit
git commit -m "refactor(security): centralize scope and object authorization"
```

---

### Task 5: Add ownership/tenant identity to local metadata with migrations

**Files:**
- Create: `src/marketing_mcp/storage/migrations.py`
- Modify: `src/marketing_mcp/storage/metadata.py`
- Modify: repository interfaces from `2026-08-23-jobs-storage-recovery.md`
- Create: `tests/integration/test_sqlite_ownership_migration.py`

**Interfaces:**

Every record returned by repositories must expose:

```python
{
    "tenant_id": str,
    "owner_subject": str,
    "created_by": str,
    ...
}
```

Legacy local v0.4 records migrate to:

```text
tenant_id = local
author/owner_subject = local-stdio
```

- [ ] **Step 1: Build a v0.4 SQLite fixture before migration**
- [ ] **Step 2: Test deterministic migration and idempotent reopen**
- [ ] **Step 3: Test startup refusal for a newer unsupported schema version**
- [ ] **Step 4: Implement ordered migrations**
- [ ] **Step 5: Run migration + persistence lifecycle tests**

```bash
uv run pytest tests/integration/test_sqlite_ownership_migration.py tests/integration/test_persistence_lifecycle.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/storage tests/integration
git commit -m "feat(storage): migrate resources to explicit ownership"
```

---

### Task 6: Enforce ownership at the repository/service boundary

**Files:**
- Modify: `src/marketing_mcp/services/dataset_service.py`
- Modify: `src/marketing_mcp/services/modeling_service.py`
- Modify: `src/marketing_mcp/services/decision_service.py`
- Modify: `src/marketing_mcp/services/clv_service.py`
- Modify: repository contracts
- Test: `tests/contract/test_resource_ownership.py`

**Interfaces:**

Prefer explicit caller context:

```python
def get_model(self, model_id: str, *, principal: Principal) -> ModelRecord: ...
```

or a policy-aware repository facade. Do not rely on handlers remembering to filter after reading another tenant's object.

- [ ] **Step 1: Write cross-principal contract tests for datasets, models, scenarios and CLV models**
- [ ] **Step 2: Add ownership to resource creation paths**
- [ ] **Step 3: Add authorization before returning/loading protected records**
- [ ] **Step 4: Verify model artifact paths cannot be reached by guessing another model ID**
- [ ] **Step 5: Run contract + statistical workflow tests**

```bash
uv run pytest tests/contract/test_resource_ownership.py tests/statistical/test_decision_invariants.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/services src/marketing_mcp/storage tests/contract
git commit -m "feat(security): enforce ownership at service boundaries"
```

---

### Task 7: Protect all MCP resources

**Files:**
- Modify: `src/marketing_mcp/mcp/resources.py`
- Modify: `src/marketing_mcp/mcp/server.py`
- Test: `tests/integration/test_mcp_resource_authorization.py`

**Interfaces:**
- Resources consume the same `ExecutionContextProvider` and `AuthorizationService` as tools.

- [ ] **Step 1: Write a resource matrix covering all resource templates**

```text
marketing://datasets/{dataset_id}
marketing://models/{model_id}
marketing://models/{model_id}/diagnostics
marketing://models/{model_id}/lineage
marketing://models/{model_id}/plots/{plot_type}
marketing://clv/{model_id}
```

- [ ] **Step 2: Test read scope + ownership success**
- [ ] **Step 3: Test same-scope foreign object denial**
- [ ] **Step 4: Refactor resource registration to receive context/policy explicitly**
- [ ] **Step 5: Run MCP discovery + resource auth tests**

```bash
uv run pytest tests/integration/test_mcp_discovery_snapshot.py tests/integration/test_mcp_resource_authorization.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/marketing_mcp/mcp/resources.py tests/integration
git commit -m "fix(security): authorize MCP resources by scope and ownership"
```

---

### Task 8: Add complete G3/H1/H2 security release tests

**Files:**
- Create: `tests/release/test_g3_remote_security.py`
- Create: `tests/release/test_h1_identity_propagation.py`
- Create: `tests/release/test_h2_object_isolation.py`
- Modify: `docs/PRODUCTION-READINESS.md`

**Required assertions:**

- production HTTP fails closed without configured auth
- query-string credentials are rejected
- expired/wrong-audience/wrong-issuer tokens are rejected
- per-tool scopes are enforced through real HTTP sessions
- no HTTP request receives trusted stdio scopes
- every MCP resource requires authorized identity
- every durable resource has explicit owner/tenant fields
- cross-principal access is denied for tools and resources
- denial responses do not leak foreign object metadata

- [ ] **Step 1: Implement release tests as executable assertions, not documentation checks**
- [ ] **Step 2: Run the complete security suite**

```bash
uv run pytest tests/unit/test_auth.py tests/unit/test_oauth_verifier.py tests/unit/test_security_profiles.py tests/unit/test_tool_scope_enforcement.py tests/integration/test_mcp_auth_http.py tests/integration/test_http_scope_propagation.py tests/integration/test_mcp_resource_authorization.py tests/contract/test_resource_ownership.py tests/release/test_g3_remote_security.py tests/release/test_h1_identity_propagation.py tests/release/test_h2_object_isolation.py -v
```

- [ ] **Step 3: Update readiness only from generated test evidence**
- [ ] **Step 4: Commit**

```bash
git add tests/release docs/PRODUCTION-READINESS.md
git commit -m "test(release): establish remote identity and isolation gates"
```

## Acceptance Criteria

This plan is complete when:

- authenticated HTTP identity reaches every tool/resource execution
- remote execution has no trusted stdio fallback
- scope and ownership are independently enforced
- all persistent objects are owner/tenant aware
- resources and tools share one authorization model
- cross-principal access is denied end-to-end
- G3, H1 and H2 can be evaluated from executable release tests
