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


def env_json(
    summary: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    warnings: list[Any] | None = None,
    provenance: dict[str, Any] | None = None,
    next_actions: list[str] | None = None,
) -> str:
    """Fast JSON-serialized envelope using native Rust serde when available."""
    from marketing_mcp.accelerators import fast_serialize_json

    payload = env(
        summary=summary,
        evidence=evidence,
        warnings=warnings,
        provenance=provenance,
        next_actions=next_actions,
    )
    return fast_serialize_json(payload)

