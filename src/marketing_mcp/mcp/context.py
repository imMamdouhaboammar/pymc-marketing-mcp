"""Execution context propagated into tool handlers."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any, Literal

from marketing_mcp.errors import DomainError
from marketing_mcp.security.policy import all_scopes
from marketing_mcp.security.principal import Principal

_current_execution_context: contextvars.ContextVar[ExecutionContext | None] = (
    contextvars.ContextVar("current_execution_context", default=None)
)


@dataclass(frozen=True)
class ExecutionContext:
    """Principal and authorization data for one tool invocation."""

    principal: Principal | None = None
    request_id: str = ""
    transport: Literal["stdio", "http"] = "stdio"


def set_current_execution_context(ctx: ExecutionContext) -> contextvars.Token[Any]:
    """Set the execution context for the current async task / thread."""
    return _current_execution_context.set(ctx)


def reset_current_execution_context(token: contextvars.Token[Any]) -> None:
    """Reset the execution context token."""
    _current_execution_context.reset(token)


def get_current_execution_context() -> ExecutionContext | None:
    """Get the active execution context for the current request."""
    return _current_execution_context.get()


class RequestScopedContextProvider:
    """Resolves execution context from the active request context variable.

    Fails closed if no execution context or authenticated principal is present.
    """

    def __call__(self) -> ExecutionContext:
        ctx = get_current_execution_context()
        if ctx is None or ctx.principal is None:
            raise DomainError(
                "AUTH_REQUIRED",
                "Authentication required for request execution",
                next_action="Provide a valid Authorization Bearer token or X-API-Key header",
            )
        return ctx


def stdio_context_provider() -> ExecutionContext:
    """Trusted local transport: every scope granted."""
    return ExecutionContext(
        principal=Principal(
            subject="local-stdio",
            auth_type="stdio",
            scopes=all_scopes(),
            tenant_id="default",
        ),
        request_id="stdio",
        transport="stdio",
    )


__all__ = [
    "ExecutionContext",
    "RequestScopedContextProvider",
    "get_current_execution_context",
    "reset_current_execution_context",
    "set_current_execution_context",
    "stdio_context_provider",
]
