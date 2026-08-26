"""Resource ownership and multi-tenant authorization hooks.

Enforces resource-level tenant and owner isolation without forcing multi-tenancy
on local stdio mode.
"""

from __future__ import annotations

from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.security.principal import Principal

LOCAL_OWNER = "local"


def attach_ownership(principal: Principal | None, record: dict[str, Any]) -> dict[str, Any]:
    """Attach owner and tenant identity to a newly created resource record."""
    owner = principal.subject if principal is not None else LOCAL_OWNER
    tenant_id = principal.tenant_id if principal is not None else None
    record["owner"] = record.get("owner") or owner
    if tenant_id is not None and "tenant_id" not in record:
        record["tenant_id"] = tenant_id
    return record


def inherit_ownership(
    parent_record: dict[str, Any], child_record: dict[str, Any]
) -> dict[str, Any]:
    """Propagate owner and tenant ID from a parent resource to a derived resource."""
    if "owner" in parent_record and "owner" not in child_record:
        child_record["owner"] = parent_record["owner"]
    if "tenant_id" in parent_record and "tenant_id" not in child_record:
        child_record["tenant_id"] = parent_record["tenant_id"]
    return child_record


def authorize_resource(
    principal: Principal | None,
    record: dict[str, Any],
    resource_type: str = "resource",
    action: str = "read",
) -> None:
    """Authorize caller access to a specific resource record.

    Rules:
    - Trusted local stdio (auth_type == 'stdio') is always granted access.
    - If principal is None in a protected context, fail closed (AUTH_REQUIRED).
    - If resource has a tenant_id, principal.tenant_id must match.
    - If resource has an owner (and caller is not an admin with 'marketing:admin' or wildcard),
      caller's subject must match for write/delete/archive actions.
    """
    if principal is not None and principal.auth_type == "stdio":
        return

    # If the resource is local and has no tenant_id, permit unauthenticated local caller
    if record.get("owner") == LOCAL_OWNER and record.get("tenant_id") is None:
        return

    if principal is None:
        raise DomainError(
            "AUTH_REQUIRED",
            f"Authentication required to access {resource_type}",
            next_action="Provide a valid Authorization header",
        )

    # 1. Multi-tenant isolation: strict tenant_id match
    record_tenant = record.get("tenant_id")
    if record_tenant is not None and (
        principal.tenant_id is None or principal.tenant_id != record_tenant
    ):
        raise DomainError(
            "AUTH_FORBIDDEN",
            f"Access denied to {resource_type} belonging to tenant '{record_tenant}'",
            evidence={
                "resource_type": resource_type,
                "record_tenant": record_tenant,
                "caller_tenant": principal.tenant_id,
            },
            next_action="Ensure the authentication token matches the target tenant",
        )

    # 2. Owner isolation for mutation/archive actions unless admin
    record_owner = record.get("owner")
    is_admin = "*" in principal.scopes or "marketing:admin" in principal.scopes
    if (
        record_owner
        and record_owner != LOCAL_OWNER
        and action in ("write", "delete", "archive", "calibrate")
        and not is_admin
        and principal.subject != record_owner
    ):
        raise DomainError(
            "AUTH_FORBIDDEN",
            f"Principal '{principal.subject}' is not authorized to {action} {resource_type} owned by '{record_owner}'",
            evidence={
                "resource_type": resource_type,
                "record_owner": record_owner,
                "caller_subject": principal.subject,
                "action": action,
            },
            next_action="Request ownership transfer or perform the action with admin privileges",
        )


def authorize_dataset(
    principal: Principal | None, dataset_record: dict[str, Any], action: str = "read"
) -> None:
    """Authorize access to a dataset."""
    authorize_resource(principal, dataset_record, resource_type="dataset", action=action)


def authorize_model(
    principal: Principal | None, model_record: dict[str, Any], action: str = "read"
) -> None:
    """Authorize access to a model."""
    authorize_resource(principal, model_record, resource_type="model", action=action)


def authorize_job(
    principal: Principal | None, job_record: dict[str, Any], action: str = "read"
) -> None:
    """Authorize access to an asynchronous job."""
    authorize_resource(principal, job_record, resource_type="job", action=action)
