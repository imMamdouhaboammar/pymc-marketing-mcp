"""Unit tests for AuthorizationService."""

from __future__ import annotations

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.security.authorization import AuthorizationService
from marketing_mcp.security.principal import Principal


def test_auth_service_scope_enforcement():
    auth = AuthorizationService()
    p_read = Principal(subject="analyst", auth_type="oauth", scopes=frozenset(["marketing:read"]))

    # Read scope allowed for read
    auth.require_scope(p_read, "marketing:read")

    # Read scope forbidden for decide
    with pytest.raises(DomainError) as exc_info:
        auth.require_scope(p_read, "marketing:decide")
    assert exc_info.value.code == "AUTH_FORBIDDEN"


def test_auth_service_model_ownership_enforcement():
    auth = AuthorizationService()
    p_tenant_a = Principal(subject="u1", auth_type="oauth", tenant_id="tenant_a", scopes=frozenset(["marketing:read"]))
    p_tenant_b = Principal(subject="u2", auth_type="oauth", tenant_id="tenant_b", scopes=frozenset(["marketing:read"]))

    model_a = {"model_id": "m_a", "tenant_id": "tenant_a", "owner": "u1"}

    # Tenant A access own model
    auth.authorize_model(p_tenant_a, model_a, action="read")

    # Tenant B denied access to Tenant A model
    with pytest.raises(DomainError) as exc_info:
        auth.authorize_model(p_tenant_b, model_a, action="read")
    assert exc_info.value.code == "AUTH_FORBIDDEN"


def test_auth_service_stdio_trusted():
    auth = AuthorizationService()
    p_stdio = Principal(subject="local-stdio", auth_type="stdio", scopes=frozenset(["*"]))

    model_any = {"model_id": "m1", "tenant_id": "other_tenant", "owner": "other_owner"}
    auth.authorize_model(p_stdio, model_any, action="read")
