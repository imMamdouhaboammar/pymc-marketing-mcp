# Security

## Security position

An MCP client is untrusted input

The current codebase contains meaningful security controls, but remote production security is still **partial** because identity propagation, resource authorization and credential/control-plane integration are not yet proven end to end

Do not use the existence of `tests/release/test_g3_remote_security.py` alone as proof that the complete remote MCP path is secure

## Current controls

### Input and execution boundary

The server does not expose arbitrary Python, shell or SQL execution

Dataset ingestion is restricted to controlled CSV/Parquet paths with identifier and size validation. Caller-selected arbitrary artifact paths are not part of the public MCP contract. Pickle/joblib deserialization is not accepted as a model import path

### Transport profiles

`Settings.security_profile` defines three deployment postures

- `stdio-local`: trusted local execution
- `http-private-api-key`: private remote HTTP with configured API key material
- `http-production-oauth`: remote profile requiring configured OAuth issuer and audience

Production-oriented HTTP profiles fail closed when their required authentication configuration is missing

### Credential transport

Remote credentials are accepted through headers

- `Authorization: Bearer <token>`
- `X-API-Key: <key>`

Query-string credentials such as `?token=` and `?api_key=` are rejected because URLs leak into logs, history and intermediaries

### Scope policy

The current scope catalog is

- `marketing:read`
- `marketing:model`
- `marketing:decide`
- `marketing:clv`
- `marketing:admin`

Tool handlers call scope policy before doing work when they receive a real request execution context

### Ownership helpers

`src/marketing_mcp/security/ownership.py` provides owner/tenant attachment and authorization helpers for datasets, models and jobs

These helpers are part of the target authorization model, but their existence does not prove that every resource lifecycle path currently calls them

### Request safety and redaction

The HTTP stack includes request-safety middleware and secret-redaction helpers. Error/evidence paths have tests for masking credential-shaped values

### Trusted local stdio

Stdio intentionally maps to a trusted local principal and is not a multi-tenant remote security boundary

## Known remote-security gaps

### 1. HTTP principal propagation is not proven end to end

`create_http_app()` authenticates the request at middleware level, but the MCP server is currently created without a request-scoped `context_provider`

The release security tests separately prove authentication primitives, scope rejection and ownership helpers. They do not yet prove this full path

```text
HTTP token
  -> middleware authentication
  -> request identity
  -> MCP invocation
  -> ExecutionContext.principal
  -> tool scope check
```

H1 remains open until a real Streamable HTTP MCP session with a limited-scope token proves the expected allow/deny behavior at tool execution

### 2. MCP resources are not yet request-authorized

Current MCP resource handlers read model/dataset/diagnostic/lineage/plot/CLV data directly from application storage and do not receive the same request execution context as tools

H2 requires resource reads to enforce principal, scope and tenant/object ownership before returning content

### 3. Ownership lifecycle needs full wiring

Ownership helpers and tenant-aware job records exist, but production isolation requires proof that newly created datasets/models/scenarios/CLV artifacts/jobs receive ownership consistently and that derived resources inherit it

Legacy local records require an explicit migration policy rather than silently becoming shared remote resources

### 4. OAuth verifier must be wired into the production path

`RemoteJWTVerifier` exists and has unit coverage. Production readiness requires proof that the configured production HTTP path actually uses the verifier and maps verified claims into `Principal`

### 5. Dashboard credentials are a separate unsafe authority today

The current dashboard prototype generates keys in the browser, persists raw secret material in Firestore under a misleading `keyHash` field and may retain full secrets in localStorage

The Python MCP server does not use that Firestore collection as its canonical credential repository

Until H3 is complete, the dashboard API-key manager must not be described as a production credential-management surface

## Target remote authorization flow

```text
HTTP request
  -> API-key/OAuth verification
  -> Principal(subject, tenant_id, scopes, auth_type)
  -> request-scoped ExecutionContext
  -> MCP tool/resource
  -> required scope
  -> object/tenant authorization
  -> service operation
  -> audit/correlation metadata
```

Every protected resource path must fail closed when the principal is absent or does not own/belong to the target tenant

## Target credential model

For API keys

```text
Create credential request
  -> trusted backend generates high-entropy secret
  -> store verifier/hash + prefix + owner/tenant + status
  -> return raw secret once
  -> never persist or retrieve raw secret again
```

Revocation must affect the same verifier used by MCP authentication

For production OAuth, issuer/audience/signature/scope validation must happen through the configured resource-server verifier with no symmetric test secret enabled by default

## Secrets and logs

Never log or place in release evidence

- Authorization headers
- raw API keys
- JWTs
- private keys
- passwords or database credentials
- raw customer/dataset rows

Model IDs, job IDs and dataset IDs may be used in logs/traces when they are not raw customer identifiers. Metrics must avoid high-cardinality resource IDs

## Release security evidence

G3/H1/H2/H3 may be marked green only after executable current-head evidence includes at minimum

- unauthenticated remote tool call rejected
- query credential rejected
- read-only principal allowed to call read tool
- read-only principal rejected on modeling/decision tool
- decision principal can act only on an authorized model
- cross-tenant tool access rejected
- cross-tenant MCP resource read rejected
- OAuth wrong issuer/audience/expiry/scope rejected through the real HTTP path
- revoked API key rejected through the real HTTP path
- secrets absent from logs/errors/evidence
- stdio trusted-local behavior remains unchanged

See `docs/superpowers/plans/2026-08-26-auth-context-resource-isolation.md` and `docs/superpowers/plans/2026-08-26-dashboard-control-plane-security.md`
