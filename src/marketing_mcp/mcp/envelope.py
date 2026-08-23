"""Tool result envelope construction for MCP tool handlers."""

from __future__ import annotations

from typing import Any

from marketing_mcp.schemas.models import ToolEnvelope


def env(
    summary: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    warnings: list[Any] | None = None,
    provenance: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    return ToolEnvelope(
        summary=summary or {},
        evidence=evidence or {},
        warnings=warnings or [],
        provenance=provenance or {},
        next_actions=next_actions or [],
    ).model_dump()
