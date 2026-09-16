# Post-Mortem 01: Fail-Closed Anonymous HTTP Binding on Cloud Run

## 1. Executive Summary & Context
During initial deployment of `pymc-marketing-mcp` to Google Cloud Run in unauthenticated public beta mode (`AUTH_ENABLED=false`), the container immediately crashed upon startup with exit code `2` during application bootstrap.

- **Component**: `src/marketing_mcp/config.py` (`SecurityProfile` and `Settings.validate_http_posture`)
- **Severity**: Critical (Deployment Blocker)
- **Time to Detect**: Immediate upon Cloud Run service revision deployment
- **Status**: Resolved & Verified in Production

---

## 2. Symptom & Error Signature
Cloud Run revision logs reported:
```text
Container called exit(2).
Traceback (most recent call last):
  File ".../marketing_mcp/cli.py", line 120, in run_server
    app = create_http_app(settings=settings)
  File ".../marketing_mcp/config.py", line 151, in validate
    raise DomainError(
marketing_mcp.errors.DomainError: [AUTH_REQUIRED] Refusing to serve HTTP on a public interface without authentication
```
The health check probe returned `HTTP 503 Service Unavailable` because the container never reached the listening state on port `8080`.

---

## 3. Root Cause Analysis
The server codebase implemented an intentional, defense-in-depth "fail-closed" posture check in `config.py`:
1. `SecurityProfile.validate_http_posture(host, auth_enabled)`:
   If `host` was bound to `0.0.0.0` (mandatory for container environments like Cloud Run, Docker, and Kubernetes) and `auth_enabled` was set to `False`, the method raised a `SecurityConfigError` or `DomainError("AUTH_REQUIRED")`.
2. This guard prevented accidental public exposure on bare internet servers when authentication was mistakenly disabled.
3. However, for a managed cloud environment where an unauthenticated beta endpoint is deliberately configured, this safety check prevented the server from starting without an explicit, auditable bypass override.

---

## 4. Resolution & Architecture Diff
We introduced an explicit environment override `MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true`. This ensures:
- By default, the system remains strictly fail-closed against accidental insecure bindings.
- When an operator deliberately provisions an unauthenticated public beta instance, setting `MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true` allows binding to `0.0.0.0` while logging the operational posture.

### Diff in `src/marketing_mcp/config.py`:
```python
class SecurityProfile(str, Enum):
    ...
    def validate_http_posture(self, host: str, auth_enabled: bool) -> None:
        """Refuse insecure HTTP deployments before Uvicorn starts."""
+       if os.getenv("MARKETING_MCP_ALLOW_ANONYMOUS_HTTP", "").lower() in ("true", "1", "yes"):
+           return
        if self is self.STDIO_LOCAL:
            public_bind = host not in ("127.0.0.1", "localhost", "::1")
            if public_bind and not auth_enabled:
...
class Settings(BaseModel):
    ...
    def model_post_init(self, __context: Any) -> None:
        public_bind = self.host not in ("127.0.0.1", "localhost", "::1")
        http_transport = self.transport != "stdio"
-       if public_bind and http_transport and self.enforce_transport_security and not self.auth_enabled:
+       allow_anonymous = os.getenv("MARKETING_MCP_ALLOW_ANONYMOUS_HTTP", "").lower() in ("true", "1", "yes")
+       if public_bind and http_transport and self.enforce_transport_security and not self.auth_enabled and not allow_anonymous:
            raise DomainError(
                "AUTH_REQUIRED",
                "Refusing to serve HTTP on a public interface without authentication",
            )
```

---

## 5. Verification & Evidence
- **Container Startup**: Container started cleanly on port 8080 with `Uvicorn running on http://0.0.0.0:8080`.
- **Health Check**:
  ```bash
  curl -sS https://<service-url>/health
  # {"status":"healthy","auth_enabled":false,"transport":"http"}
  ```
- **Security Invariant**: When `MARKETING_MCP_ALLOW_ANONYMOUS_HTTP` is unset or false, `pytest tests/security/` confirms unauthorized public bindings continue to fail-closed immediately.
