"""Execution context propagated into tool handlers."""

from __future__ import annotations

from dataclasses import dataclass

from marketing_mcp.security.policy import all_scopes
from marketing_mcp.security.principal import Principal


@dataclass
class ExecutionContext:
    """Principal and authorization data for one tool invocation."""

    principal: Principal | None = None


def stdio_context_provider() -> ExecutionContext:
    """Trusted local transport: every scope granted."""
    return ExecutionContext(
        principal=Principal(
            subject="local-stdio",
            auth_type="stdio",
            scopes=all_scopes(),
        )
    )
