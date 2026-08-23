"""Execution principal: the authenticated caller identity for a request."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AuthType = Literal["stdio", "api_key", "oauth"]


class Principal(BaseModel):
    """Identity and authorization data attached to tool execution.

    Constructed by the transport layer (stdio bootstrap, API-key verifier, or
    OAuth token verifier) and enforced at tool execution via
    :func:`marketing_mcp.security.policy.require_scope`.
    """

    subject: str = Field(min_length=1, description="Stable caller identifier")
    auth_type: AuthType
    scopes: frozenset[str] = Field(default_factory=frozenset)
    tenant_id: str | None = None
