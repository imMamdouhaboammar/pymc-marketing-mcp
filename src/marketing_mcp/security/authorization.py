"""Authorization service centralizing scope and object ownership policies."""

from __future__ import annotations

from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.security.ownership import (
    authorize_dataset,
    authorize_job,
    authorize_model,
    authorize_resource,
)
from marketing_mcp.security.policy import require_scope
from marketing_mcp.security.principal import Principal


class AuthorizationService:
    """Enforces scope and resource ownership policies."""

    @staticmethod
    def require_scope(principal: Principal | None, scope: str) -> None:
        require_scope(principal, scope)

    @staticmethod
    def authorize_model(
        principal: Principal | None, model_record: dict[str, Any] | None, action: str = "read"
    ) -> None:
        if model_record is None:
            raise DomainError("MODEL_NOT_FOUND", "Model was not found")
        authorize_model(principal, model_record, action=action)

    @staticmethod
    def authorize_dataset(
        principal: Principal | None, dataset_record: dict[str, Any] | None, action: str = "read"
    ) -> None:
        if dataset_record is None:
            raise DomainError("DATASET_NOT_FOUND", "Dataset was not found")
        authorize_dataset(principal, dataset_record, action=action)

    @staticmethod
    def authorize_job(
        principal: Principal | None, job_record: dict[str, Any] | None, action: str = "read"
    ) -> None:
        if job_record is None:
            raise DomainError("JOB_NOT_FOUND", "Job was not found")
        authorize_job(principal, job_record, action=action)

    @staticmethod
    def authorize_resource(
        principal: Principal | None,
        record: dict[str, Any] | None,
        resource_type: str = "resource",
        action: str = "read",
    ) -> None:
        if record is None:
            raise DomainError("RESOURCE_NOT_FOUND", f"{resource_type.capitalize()} was not found")
        authorize_resource(principal, record, resource_type=resource_type, action=action)


__all__ = ["AuthorizationService"]
