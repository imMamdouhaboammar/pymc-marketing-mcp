# Security

## Security position

An MCP client is untrusted input

The codebase enforces strict remote production security across authentication, request-scoped identity propagation, resource authorization, and credential control-plane integration, backed by machine-verified release tests (Gates G3, H1, H2, and H3).

## Current controls

### Input and execution boundary

The server does not expose arbitrary Python, shell or SQL execution

Dataset ingestion is restricted to controlled CSV/Parquet paths with identifier and size validation. Caller-selected arbitrary artifact paths are not part of the public MCP contract. Pickle/joblib deserialization is not accepted as a model import path

### Transport profiles

`Settings.security_profile` defines three deployment postures

- `stdio-local`: trusted local execution
- `http-private-api-key`: private remote HTTP with configured API key material or backend credential repository
- `http-production-oauth`: remote profile requiring configured OAuth issuer and audience

Production-oriented HTTP profiles fail closed when their required authentication configuration is missing

### Credential transport

Remote credentials are accepted exclusively through HTTP headers

- `Authorization: Bearer <token>`
- `X-API-Key: <key>`

Query-string credentials such as `?token=` and `?api_key=` are rejected because URLs leak into logs, history and intermediaries

### Request-scoped identity propagation (Gate H1)

In remote HTTP transport, `MCPAuthMiddleware` authenticates the incoming token/key, creates an immutable `Principal`, and sets it in an execution-isolated `ContextVar[ExecutionContext]`.

`RequestScopedContextProvider` resolves this context during MCP tool/resource dispatch and strictly fails closed (`AUTH_REQUIRED`) if unauthenticated

### Scope policy and tool authorization

The scope catalog is

- `marketing:read`
- `marketing:model`
- `marketing:decide`
- `marketing:clv`
- `marketing:admin`

Every MCP tool and resource handler verifies required scopes via `AuthorizationService` before executing domain operations

### Object and tenant authorization (Gate H2)

`AuthorizationService` and `src/marketing_mcp/security/ownership.py` enforce multi-tenant boundaries:

- Datasets, models, and jobs store `owner` and `tenant_id`
- Cross-tenant tool calls and resource queries (`marketing://models/{model_id}`, `marketing://datasets/{dataset_id}`, diagnostics, lineage, plots, CLV) are strictly denied with `AUTH_FORBIDDEN`
- Mutating operations require resource ownership or `marketing:admin` scope within the same tenant

### Credential control plane and verifier-only storage (Gate H3)

API key issuance and verification are managed exclusively by the backend `CredentialService`:

- High-entropy cryptographic 256-bit secrets (`mcp_live_...`) are generated on the server and returned **exactly once** upon creation
- Database storage (`SQLiteCredentialRepository`) stores only salted SHA-256 verifiers and prefixes, never raw secret keys
- Key revocation through `/control/credentials/{credential_id}` takes effect immediately in MCP authentication without server restart
- The dashboard is a pure UI client of `/control/credentials`, with zero browser-side key generation and no raw key persistence in `localStorage` or Firestore

### Request safety and secret redaction

The HTTP stack includes `RequestSafetyMiddleware`, structured logging with automatic secret scrubbing (`StructuredJSONFormatter`), and redaction helpers masking tokens and API keys across all error and logging paths

### Trusted local stdio

Stdio intentionally maps to a trusted local principal (`stdio_context_provider`) with all scopes and is not a multi-tenant remote security boundary

## Remote authorization flow

```text
HTTP request
  -> Header authentication (API-key / JWT)
  -> Principal(subject, tenant_id, scopes, auth_type)
  -> ContextVar[ExecutionContext]
  -> MCP tool/resource dispatch
  -> RequestScopedContextProvider.resolve_context()
  -> AuthorizationService.require_scope()
  -> AuthorizationService.authorize_model / authorize_dataset / authorize_job
  -> Domain service operation
  -> Sanitized response / audit log
```

Every protected resource path fails closed when the principal is absent or does not belong to the target tenant

## Credential lifecycle

```text
POST /control/credentials
  -> Backend generates 256-bit random secret
  -> Compute salt + verifier hash (SHA-256)
  -> Persist verifier, prefix, tenant_id, owner, scopes
  -> Return raw secret once to client
  -> Never store or return raw secret again

Authentication
  -> Client presents secret in Authorization header
  -> APIKeyValidator queries candidate by prefix
  -> Constant-time hash verification (hmac.compare_digest)
  -> Active key -> Principal resolved; Revoked/invalid key -> 401 Unauthorized
```

## Secrets and logs

Never log or place in release evidence

- Authorization headers
- raw API keys
- JWTs
- private keys
- passwords or database credentials
- raw customer/dataset rows

Model IDs, job IDs and dataset IDs may be used in logs/traces when they are not raw customer identifiers. Metrics must avoid high-cardinality resource IDs

## Release security verification

Gates G3, H1, H2, and H3 are verified by executable test suites:

- `tests/release/test_g3_remote_security.py`
- `tests/release/test_h1_identity_propagation.py`
- `tests/release/test_h2_object_isolation.py`
- `tests/release/test_h3_credential_control_plane.py`
- `tests/integration/test_http_scope_propagation.py`
- `tests/integration/test_mcp_resource_authorization.py`
- `tests/integration/test_credential_control_api.py`
- `tests/security/test_dashboard_credential_static_policy.py`
