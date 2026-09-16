"""Tests verifying multi-tenant authorization matrix and scope enforcement (UP-006)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.security.ownership import authorize_resource
from marketing_mcp.security.policy import require_scope
from marketing_mcp.security.principal import Principal

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


def test_tenant_auth_matrix_fixtures():
    with open(BASELINES_DIR / "tenant_auth_matrix.json", encoding="utf-8") as f:
        data = json.load(f)

    for item in data["matrix"]:
        p_data = item["principal"]
        principal = (
            Principal(
                subject=p_data["subject"],
                tenant_id=p_data["tenant_id"],
                scopes=p_data["scopes"],
                auth_type="api_key",
            )
            if p_data is not None
            else None
        )
        resource = item["resource"]
        action = item["action"]
        expected_allow = item["expected_allow"]

        if expected_allow:
            authorize_resource(principal, resource, resource_type="dataset", action=action)
        else:
            with pytest.raises(DomainError) as exc:
                authorize_resource(principal, resource, resource_type="dataset", action=action)
            assert exc.value.code == item["expected_error"]


def test_scope_enforcement_rules():
    read_principal = Principal(subject="reader", scopes=["marketing:read"], auth_type="api_key")
    model_principal = Principal(subject="modeler", scopes=["marketing:model"], auth_type="api_key")
    admin_principal = Principal(subject="admin", scopes=["marketing:admin"], auth_type="api_key")
    wildcard_principal = Principal(subject="root", scopes=["*"], auth_type="api_key")

    # Read principal can read, but cannot model or decide
    require_scope(read_principal, "marketing:read")
    with pytest.raises(DomainError) as exc:
        require_scope(read_principal, "marketing:model")
    assert exc.value.code == "AUTH_FORBIDDEN"

    # Model principal can model, but cannot admin
    require_scope(model_principal, "marketing:model")
    with pytest.raises(DomainError) as exc:
        require_scope(model_principal, "marketing:admin")
    assert exc.value.code == "AUTH_FORBIDDEN"

    # Admin and wildcard can access everything
    require_scope(admin_principal, "marketing:admin")
    require_scope(wildcard_principal, "marketing:model")
    require_scope(wildcard_principal, "marketing:admin")
