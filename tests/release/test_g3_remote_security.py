"""Gate G3 Release Security Tests (Wave 4 Task 10).

Verifies:
- Production HTTP without auth config refuses startup (fail-closed)
- Query credentials (?token=, ?api_key=) fail
- Missing required scope fails (AUTH_FORBIDDEN)
- Cross-tenant access is rejected (AUTH_FORBIDDEN)
- Secrets/tokens never appear in error envelopes
- Health endpoint is public and non-sensitive
- Stdio transport remains frictionless
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from marketing_mcp import __version__
from marketing_mcp.auth import AuthManager
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.policy import require_scope
from marketing_mcp.security.principal import Principal


class TestGateG3RemoteSecurity:
    def test_production_http_without_auth_fails_startup_validation(self):
        with pytest.raises(DomainError) as exc_info:
            Settings(
                security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
                oauth_issuer=None,
                oauth_audience=None,
            )
        assert exc_info.value.code == "CONFIG_INVALID"
        assert "oauth_issuer and oauth_audience" in exc_info.value.message

    def test_query_credentials_ignored_and_rejected_when_headers_missing(self):
        auth_mgr = AuthManager()
        auth_mgr.api_key_validator.add_key("valid-key-12345")
        auth_mgr.enabled = True

        app = create_http_app(auth_manager=auth_mgr)
        client = TestClient(app)

        # Query param auth must fail with 401
        res = client.post("/mcp?api_key=valid-key-12345")
        assert res.status_code == 401
        data = res.json()
        assert "valid-key-12345" not in str(data)

    def test_missing_required_scope_fails(self):
        principal = Principal(
            subject="analyst_readonly",
            auth_type="oauth",
            scopes=frozenset(["marketing:read"]),
        )
        with pytest.raises(DomainError) as exc_info:
            require_scope(principal, "marketing:decide")
        assert exc_info.value.code == "AUTH_FORBIDDEN"

    def test_cross_tenant_access_fails(self):
        principal = Principal(
            subject="user1",
            auth_type="oauth",
            tenant_id="tenant_a",
            scopes=frozenset(["marketing:read", "marketing:model"]),
        )
        foreign_model = {"model_id": "m1", "tenant_id": "tenant_b", "owner": "user2"}
        with pytest.raises(DomainError) as exc_info:
            authorize_model(principal, foreign_model, action="read")
        assert exc_info.value.code == "AUTH_FORBIDDEN"

    def test_secrets_never_appear_in_error_envelopes(self):
        err = DomainError(
            "AUTH_FAILED",
            "Authentication failed for user",
            evidence={
                "attempted_key": "sk-secret-key-1234567890",
                "authorization_header": "Bearer eyJhbGciOiJIUzI1NiJ9.test",
            },
        )
        payload = err.to_dict()
        assert payload["error"]["evidence"]["attempted_key"] == "[REDACTED]"
        assert payload["error"]["evidence"]["authorization_header"] == "[REDACTED]"

    def test_health_endpoint_public_and_non_sensitive(self):
        app = create_http_app()
        client = TestClient(app)
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["service"] == "pymc-marketing-mcp"
        assert data["version"] == __version__
        # Ensure no sensitive storage paths or secrets in health payload
        assert "storage_path" not in data
        assert "database_url" not in data

    def test_stdio_mode_frictionless(self):
        stdio_principal = Principal(
            subject="local-stdio",
            auth_type="stdio",
            scopes=frozenset(["*"]),
        )
        # Any scope succeeds
        require_scope(stdio_principal, "marketing:read")
        require_scope(stdio_principal, "marketing:model")
        require_scope(stdio_principal, "marketing:decide")
        require_scope(stdio_principal, "marketing:admin")
