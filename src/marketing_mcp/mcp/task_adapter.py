"""Adapter contract for future MCP Tasks protocol extension (io.modelcontextprotocol/tasks)."""

from __future__ import annotations

from typing import Any, Protocol

from marketing_mcp.jobs.models import JobRecord
from marketing_mcp.security.principal import Principal


class ProtocolTaskAdapter(Protocol):
    """Protocol boundary for MCP Tasks extension adapters."""

    supported: bool

    def advertise_if_supported(self, server: Any) -> None: ...

    def to_protocol_handle(self, job: JobRecord) -> dict[str, Any]: ...

    def apply_protocol_update(
        self,
        job_id: str,
        update: dict[str, Any],
        principal: Principal,
    ) -> JobRecord: ...


class UnsupportedTasksExtensionAdapter:
    """Default adapter signaling that Python MCP SDK v2 does not yet implement Tasks extension.

    This ensures domain compute remains durable and accessible via compatibility tools today,
    while cleanly migrating when official Tasks SDK support lands.
    """

    supported: bool = False

    def advertise_if_supported(self, server: Any) -> None:
        """Do not advertise tasks extension capability on server."""
        return

    def to_protocol_handle(self, job: JobRecord) -> dict[str, Any]:
        return {
            "taskId": job.job_id,
            "status": job.status.value,
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
        }

    def apply_protocol_update(
        self,
        job_id: str,
        update: dict[str, Any],
        principal: Principal,
    ) -> JobRecord:
        raise NotImplementedError("MCP Tasks protocol extension is not yet implemented by Python SDK")


__all__ = ["ProtocolTaskAdapter", "UnsupportedTasksExtensionAdapter"]
