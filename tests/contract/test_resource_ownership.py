"""Resource ownership and multi-tenant authorization contract tests (Wave 4 Task 6)."""

from __future__ import annotations

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.security.ownership import (
    attach_ownership,
    authorize_dataset,
    authorize_job,
    authorize_model,
    inherit_ownership,
)
from marketing_mcp.security.principal import Principal


def _principal(subject="u1", auth_type="oauth", scopes=("marketing:read",), tenant_id="tenant-a"):
    return Principal(
        subject=subject,
        auth_type=auth_type,  # type: ignore[arg-type]
        scopes=frozenset(scopes),
        tenant_id=tenant_id,
    )


class TestResourceOwnership:
    def test_attach_ownership_assigns_principal_identity(self):
        p = _principal(subject="user_123", tenant_id="t_alpha")
        record = attach_ownership(p, {"model_id": "m1"})
        assert record["owner"] == "user_123"
        assert record["tenant_id"] == "t_alpha"

    def test_stdio_local_principal_gets_local_owner(self):
        record = attach_ownership(None, {"model_id": "m1"})
        assert record["owner"] == "local"
        assert "tenant_id" not in record

    def test_inherit_ownership_propagates_tenant_and_owner(self):
        parent = {"owner": "user_123", "tenant_id": "t_alpha"}
        child = {"child_id": "c1"}
        inherit_ownership(parent, child)
        assert child["owner"] == "user_123"
        assert child["tenant_id"] == "t_alpha"

    def test_same_tenant_read_access_granted(self):
        p = _principal(tenant_id="t_alpha")
        record = {"model_id": "m1", "tenant_id": "t_alpha", "owner": "user_other"}
        authorize_model(p, record, action="read")

    def test_cross_tenant_access_strictly_forbidden(self):
        p = _principal(tenant_id="t_alpha")
        record = {"model_id": "m1", "tenant_id": "t_beta", "owner": "user_beta"}
        with pytest.raises(DomainError) as exc_info:
            authorize_model(p, record, action="read")
        assert exc_info.value.code == "AUTH_FORBIDDEN"
        assert "t_beta" in exc_info.value.message

    def test_cross_tenant_access_rejected_for_datasets_and_jobs(self):
        p = _principal(tenant_id="t_alpha")
        with pytest.raises(DomainError) as exc:
            authorize_dataset(p, {"dataset_id": "d1", "tenant_id": "t_beta"})
        assert exc.value.code == "AUTH_FORBIDDEN"

        with pytest.raises(DomainError) as exc:
            authorize_job(p, {"job_id": "j1", "tenant_id": "t_beta"})
        assert exc.value.code == "AUTH_FORBIDDEN"

    def test_owner_mutation_allowed_for_resource_owner(self):
        p = _principal(subject="user_123", tenant_id="t_alpha")
        record = {"model_id": "m1", "tenant_id": "t_alpha", "owner": "user_123"}
        authorize_model(p, record, action="archive")

    def test_owner_mutation_forbidden_for_different_user_without_admin(self):
        p = _principal(subject="user_attacker", tenant_id="t_alpha", scopes=("marketing:model",))
        record = {"model_id": "m1", "tenant_id": "t_alpha", "owner": "user_123"}
        with pytest.raises(DomainError) as exc_info:
            authorize_model(p, record, action="archive")
        assert exc_info.value.code == "AUTH_FORBIDDEN"
        assert "not authorized to archive" in exc_info.value.message

    def test_admin_can_mutate_any_resource_in_their_tenant(self):
        p = _principal(subject="admin_user", tenant_id="t_alpha", scopes=("marketing:admin",))
        record = {"model_id": "m1", "tenant_id": "t_alpha", "owner": "user_123"}
        authorize_model(p, record, action="archive")

    def test_stdio_principal_bypasses_tenant_checks(self):
        stdio_p = Principal(subject="stdio-local", auth_type="stdio")
        record = {"model_id": "m1", "tenant_id": "t_other", "owner": "other_user"}
        authorize_model(stdio_p, record, action="archive")
