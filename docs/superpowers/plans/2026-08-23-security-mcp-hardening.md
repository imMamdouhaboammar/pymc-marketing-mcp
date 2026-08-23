# MCP Boundary and Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the MCP boundary into focused modules and make remote HTTP mode authenticated, scoped, fail-closed, secret-safe, and suitable for production deployment.

**Architecture:** Keep MCP protocol registration thin. Tool modules call existing services and receive an `ExecutionContext` containing principal and authorization data. Local stdio remains simple. Production Streamable HTTP uses an OAuth 2.1 resource-server verifier through the supported MCP SDK surface, with API-key support retained only for explicitly configured private/local deployments.

**Tech Stack:** MCP Python SDK 2.x, Starlette/Uvicorn, Pydantic, PyJWT only for legacy/private mode if still required, OAuth 2.1 resource server support, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Never accept credentials from URL query parameters.
- Never log access tokens, API keys, raw authorization headers, or JWT bodies.
- Production HTTP must fail startup if no verifier/auth provider is configured.
- Authorization must be checked at tool execution, not only at the HTTP middleware boundary.
- Public health endpoints may disclose service status and version but no secrets or sensitive storage details.
- Browser dashboard assets must not create an auth bypass for MCP endpoints.

---

### Task 1: Split the monolithic MCP server by capability domain

**Files:**
- Modify: `src/marketing_mcp/mcp/server.py`
- Create: `src/marketing_mcp/mcp/context.py`
- Create: `src/marketing_mcp/mcp/envelope.py`
- Create: `src/marketing_mcp/mcp/tools/datasets.py`
- Create: `src/marketing_mcp/mcp/tools/mmm.py`
- Create: `src/marketing_mcp/mcp/tools/decisions.py`
- Create: `src/marketing_mcp/mcp/tools/clv.py`
- Create: `src/marketing_mcp/mcp/tools/model_selection.py`
- Create: `src/marketing_mcp/mcp/tools/jobs.py` after the jobs plan lands
- Create: `src/marketing_mcp/mcp/resources.py`
- Test: `tests/integration/test_mcp_protocol.py`

**Interfaces:**
- `register_dataset_tools(mcp, app, context_provider) -> None`
- `register_mmm_tools(...) -> None`
- `register_decision_tools(...) -> None`
- `register_clv_tools(...) -> None`
- `register_model_selection_tools(...) -> None`
- `register_resources(...) -> None`

- [ ] Add a discovery snapshot test for current tool and resource names before refactoring.
- [ ] Move `_env()` into `mcp/envelope.py` unchanged first.
- [ ] Move resource handlers into `mcp/resources.py`.
- [ ] Move tool registrations one domain at a time with no behavior change.
- [ ] Keep `create_server()` responsible only for server creation, instructions, and module registration.
- [ ] Run MCP stdio and HTTP discovery tests after each move.
- [ ] Commit the refactor before auth behavior changes.

### Task 2: Introduce execution principals and scope policy

**Files:**
- Create: `src/marketing_mcp/security/principal.py`
- Create: `src/marketing_mcp/security/policy.py`
- Modify or replace: `src/marketing_mcp/auth.py`
- Test: `tests/unit/test_scope_policy.py`

**Interfaces:**

```python
class Principal(BaseModel):
    subject: str
    auth_type: Literal["stdio", "api_key", "oauth"]
    scopes: frozenset[str]
    tenant_id: str | None = None
```

```python
def require_scope(principal: Principal, scope: str) -> None
```

**Initial scope map:**
- `marketing:read` for inspect/status/resources
- `marketing:model` for fit/diagnose/calibrate/model comparison
- `marketing:decide` for simulation/optimization/flighting
- `marketing:clv` for CLV fit/predict
- `marketing:admin` for archive and future administrative actions

- [ ] Write tests for wildcard/private mode and explicit OAuth scopes.
- [ ] Write tests that `marketing:read` cannot call decision tools.
- [ ] Write tests that no principal or anonymous HTTP caller is rejected in protected production mode.
- [ ] Do not derive tenant identity from user-controlled tool arguments.
- [ ] Commit.

### Task 3: Remove query-string credential support

**Files:**
- Modify: `src/marketing_mcp/auth.py`
- Modify: `tests/unit/test_auth.py`
- Modify: `tests/integration/test_mcp_auth_http.py`
- Modify: `.env.example`
- Modify: docs referencing query-token access

- [ ] Add failing tests for `?token=` and `?api_key=` being ignored/rejected.
- [ ] Support `Authorization: Bearer` for OAuth and optional `X-API-Key` only in private API-key mode.
- [ ] Ensure error responses do not echo the supplied token.
- [ ] Search the repository for `?token`, `api_key=`, and credential examples and remove unsafe guidance.
- [ ] Commit.

### Task 4: Add production authentication profiles

**Files:**
- Modify: `src/marketing_mcp/config.py`
- Create: `src/marketing_mcp/security/oauth.py`
- Modify: `src/marketing_mcp/cli.py`
- Test: `tests/unit/test_security_profiles.py`
- Test: `tests/integration/test_mcp_oauth_http.py`

**Profiles:**

```text
stdio-local
http-private-api-key
http-production-oauth
```

**Required configuration fields for production OAuth:**
- issuer / authorization server metadata as required by the chosen verifier
- resource/audience identifier
- token verifier configuration
- required base scope

- [ ] Add a Pydantic security profile enum and startup validation.
- [ ] Make `0.0.0.0` production HTTP with no auth fail before Uvicorn starts.
- [ ] Configure MCP SDK resource-server auth using the pinned SDK's supported verifier/auth settings.
- [ ] Add integration fixtures issuing signed test tokens from a local test verifier or test authorization fixture.
- [ ] Verify expired, wrong-audience, wrong-issuer, missing-scope, and malformed tokens.
- [ ] Keep private API-key mode explicit rather than inferred silently from environment accidents.
- [ ] Commit.

### Task 5: Enforce scope at tool registration/execution

**Files:**
- Modify: each `src/marketing_mcp/mcp/tools/*.py`
- Modify: `src/marketing_mcp/mcp/context.py`
- Test: `tests/contract/test_tool_authorization.py`

- [ ] Define one required scope beside each tool registration.
- [ ] Obtain `Principal` from request/session context for HTTP and a local trusted principal for stdio.
- [ ] Call policy enforcement before service execution.
- [ ] Return stable `AUTH_FORBIDDEN` envelopes for authenticated callers lacking scope.
- [ ] Parameterize every tool in a contract test that checks the declared scope.
- [ ] Commit.

### Task 6: Add ownership/tenant hooks without forcing multi-tenancy on local mode

**Files:**
- Modify: metadata record schemas after persistence plan interface exists
- Create: `src/marketing_mcp/security/ownership.py`
- Test: `tests/contract/test_resource_ownership.py`

**Interfaces:**
- `authorize_dataset(principal, dataset_record, action)`
- `authorize_model(principal, model_record, action)`
- `authorize_job(principal, job_record, action)`

- [ ] Store owner subject and optional tenant ID for production-created resources.
- [ ] Local stdio records may use owner `local`.
- [ ] Reject cross-tenant model IDs even when the caller knows the identifier.
- [ ] Ensure lineage children inherit the same owner/tenant unless an explicit administrative migration occurs.
- [ ] Commit.

### Task 7: Add request safety controls

**Files:**
- Create: `src/marketing_mcp/http/safety.py`
- Modify: `src/marketing_mcp/cli.py`
- Test: `tests/integration/test_http_safety.py`

**Controls:**
- maximum request body size
- allowed host/origin policy appropriate to MCP clients
- server timeouts
- bounded JSON parsing
- rate-limit adapter hook keyed by principal
- correlation ID generation

- [ ] Reject oversized payloads before tool execution.
- [ ] Ensure public static asset routes do not broaden MCP CORS/origin policy.
- [ ] Add a no-op local limiter and production limiter interface so implementation can use Redis or gateway quotas later without changing tools.
- [ ] Emit safe `RESOURCE_LIMIT_EXCEEDED` errors.
- [ ] Commit.

### Task 8: Redact secrets and sensitive data

**Files:**
- Create: `src/marketing_mcp/security/redaction.py`
- Modify: error/log plumbing
- Test: `tests/unit/test_redaction.py`

**Redaction keys/patterns:**
- authorization
- bearer tokens
- api keys
- jwt
- secrets
- passwords
- raw customer rows

- [ ] Write tests with nested dict/list payloads and headers.
- [ ] Redact before structured logging and before attaching unexpected exception evidence.
- [ ] Keep statistical identifiers and non-sensitive provenance visible.
- [ ] Commit.

### Task 9: Harden deployment defaults

**Files:**
- Modify: `Dockerfile`
- Modify: `scripts/deploy_cloud_run.sh`
- Modify: `cloudbuild.yaml`
- Modify: `docs/DEPLOYMENT-GCP.md`
- Test: `tests/unit/test_deployment_config_contract.py`

- [ ] Remove secret generation and secret printing from deployment scripts.
- [ ] Load production credentials/verifier configuration from Secret Manager or workload identity compatible configuration.
- [ ] Remove contradictory concurrency values and define compute-safe defaults for statistical workers.
- [ ] Keep Cloud Run ingress/auth strategy explicit. If application OAuth is used with `--allow-unauthenticated`, document that Cloud Run accepts the network request while the application still requires OAuth. Otherwise use IAM ingress and document the MCP client implications.
- [ ] Ensure container runs as a non-root user where PyTensor build/runtime requirements allow it.
- [ ] Add a container healthcheck or platform health endpoint contract.
- [ ] Commit.

### Task 10: Establish Gate G3 security checks

**Files:**
- Create: `tests/release/test_g3_remote_security.py`
- Modify: `docs/PRODUCTION-READINESS.md`

Required assertions:
- production HTTP without auth config refuses startup
- query credentials fail
- missing scope fails
- wrong tenant fails
- secrets never appear in error body or captured logs
- health remains public but non-sensitive
- stdio mode remains functional

- [ ] Run unit, contract, and HTTP integration security suites.
- [ ] Add the gate to CI in the CI plan.
- [ ] Mark G3 green only from CI evidence.

## Acceptance Criteria

This plan is complete when:

- MCP server registration is modular and discovery-compatible
- every HTTP execution has an explicit principal
- every protected tool has an explicit scope
- production HTTP fails closed
- OAuth resource-server verification is tested
- query credentials are gone
- resource ownership hooks block cross-tenant access
- secrets are redacted
- deployment scripts contain no generated or printed production secrets
- Gate G3 security tests are green