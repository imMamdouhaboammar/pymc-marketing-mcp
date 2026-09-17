"""Typed boundary contracts between the interaction engine and application services.

Represents the structured interaction boundary:
  AI Client -> Inbound Bytes -> Rust Framing/Admission -> BoundaryRequest -> Python App
  Python App -> BoundaryResponse -> Rust LTTB / Serde -> Outbound Response
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from marketing_mcp.accelerators import _IS_RUST_AVAILABLE, _rust_core


@dataclass(frozen=True)
class BoundaryRequest:
    """Canonical typed inbound interaction request at the Rust/Python boundary."""

    request_id: str | None = None
    correlation_id: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None
    deadline_ms: int | None = None
    cancellation_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "tenant_id": self.tenant_id,
            "deadline_ms": self.deadline_ms,
            "cancellation_token": self.cancellation_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoundaryRequest:
        args = data.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        return cls(
            request_id=data.get("request_id"),
            correlation_id=data.get("correlation_id"),
            tool_name=data.get("tool_name"),
            arguments=args,
            tenant_id=data.get("tenant_id"),
            deadline_ms=data.get("deadline_ms"),
            cancellation_token=data.get("cancellation_token"),
        )


@dataclass(frozen=True)
class BoundaryResponse:
    """Canonical typed outbound interaction response at the Rust/Python boundary."""

    correlation_id: str | None = None
    status: str = "ok"
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    execution_time_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.status in ("ok", "accepted") and self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "status": self.status,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BoundaryResponse:
        return cls(
            correlation_id=data.get("correlation_id"),
            status=data.get("status", "ok"),
            data=data.get("data"),
            error=data.get("error"),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
        )


def create_boundary_request(
    request_id: str | None = None,
    correlation_id: str | None = None,
    tool_name: str | None = None,
    arguments: dict[str, Any] | None = None,
    tenant_id: str | None = None,
    deadline_ms: int | None = None,
    cancellation_token: str | None = None,
) -> BoundaryRequest:
    """Create a typed BoundaryRequest, using Rust fast constructors if available."""
    args = arguments or {}
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_create_interaction_request"):
        args_json = json.dumps(args)
        raw = _rust_core.fast_create_interaction_request(
            request_id,
            correlation_id,
            tool_name,
            args_json,
            tenant_id,
            deadline_ms,
            cancellation_token,
        )
        return BoundaryRequest(
            request_id=raw.get("request_id"),
            correlation_id=raw.get("correlation_id"),
            tool_name=raw.get("tool_name"),
            arguments=args,
            tenant_id=raw.get("tenant_id"),
            deadline_ms=raw.get("deadline_ms"),
            cancellation_token=raw.get("cancellation_token"),
        )
    return BoundaryRequest(
        request_id=request_id,
        correlation_id=correlation_id,
        tool_name=tool_name,
        arguments=args,
        tenant_id=tenant_id,
        deadline_ms=deadline_ms,
        cancellation_token=cancellation_token,
    )


def create_boundary_response(
    correlation_id: str | None = None,
    status: str = "ok",
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    execution_time_ms: float = 0.0,
) -> BoundaryResponse:
    """Create a typed BoundaryResponse, using Rust fast constructors if available."""
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_create_interaction_response"):
        payload_json = json.dumps(data) if data is not None else None
        raw = _rust_core.fast_create_interaction_response(
            correlation_id,
            status,
            payload_json,
            execution_time_ms,
        )
        return BoundaryResponse(
            correlation_id=raw.get("correlation_id"),
            status=raw.get("status", status),
            data=data,
            error=error,
            execution_time_ms=raw.get("execution_time_ms", execution_time_ms),
        )
    return BoundaryResponse(
        correlation_id=correlation_id,
        status=status,
        data=data,
        error=error,
        execution_time_ms=execution_time_ms,
    )
