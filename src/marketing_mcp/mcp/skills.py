"""MCP-native delivery for the canonical scientific Skill Pack."""

from __future__ import annotations

import json
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.context import stdio_context_provider
from marketing_mcp.mcp.envelope import env
from marketing_mcp.security.policy import require_scope


def register_skill_delivery(mcp, app, context_provider: Any = None) -> None:
    """Expose progressive-disclosure Skill guidance through standard MCP primitives."""
    resolve_context = context_provider or stdio_context_provider
    registry = app.skillpack

    def _authorize() -> None:
        require_scope(resolve_context().principal, "marketing:read")

    def _json_error(error: DomainError) -> str:
        return json.dumps(error.to_dict(), indent=2, ensure_ascii=False)

    @mcp.resource(
        "marketing://skills",
        name="skill_catalog",
        description="Compact scientific workflow skill catalog. Load one selected skill lazily.",
        mime_type="application/json",
    )
    async def skill_catalog() -> str:
        try:
            _authorize()
            return registry.catalog_json()
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/{skill_name}/manifest",
        name="skill_manifest_resource",
        description="Machine-readable manifest for one explicitly registered scientific skill.",
        mime_type="application/json",
    )
    async def skill_manifest_resource(skill_name: str) -> str:
        try:
            _authorize()
            return registry.manifest_json(skill_name)
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/{skill_name}",
        name="skill_resource",
        description="Canonical operational SKILL.md content for one explicitly registered skill.",
        mime_type="text/markdown",
    )
    async def skill_resource(skill_name: str) -> str:
        try:
            _authorize()
            return registry.get(skill_name).markdown
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/tool-map",
        name="skill_tool_map",
        description="Coverage classification for every public MCP tool.",
        mime_type="application/json",
    )
    async def skill_tool_map() -> str:
        try:
            _authorize()
            return json.dumps(registry.tool_map(), indent=2, ensure_ascii=False)
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/workflow-map",
        name="skill_workflow_map",
        description="Prerequisites, gates, fallbacks, and continuations for scientific skills.",
        mime_type="application/json",
    )
    async def skill_workflow_map() -> str:
        try:
            _authorize()
            return json.dumps(registry.workflow_map(), indent=2, ensure_ascii=False)
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/decision-gates",
        name="skill_decision_gates",
        description="Decision-gated operations derived from the capability registry.",
        mime_type="application/json",
    )
    async def skill_decision_gates() -> str:
        try:
            _authorize()
            return json.dumps(registry.decision_gates(), indent=2, ensure_ascii=False)
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/references/scientific-answer-contract",
        name="scientific_answer_contract",
        description="Shared analytical answer and uncertainty communication contract.",
        mime_type="text/markdown",
    )
    async def scientific_answer_contract() -> str:
        try:
            _authorize()
            return registry.get_reference("scientific-answer-contract")
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/references/scientific-source-ledger",
        name="scientific_source_ledger",
        description="Authoritative-source ledger for Skill Pack scientific rules.",
        mime_type="text/markdown",
    )
    async def scientific_source_ledger() -> str:
        try:
            _authorize()
            return registry.get_reference("scientific-source-ledger")
        except DomainError as exc:
            return _json_error(exc)

    @mcp.tool(
        name="get_skill_guidance",
        description=(
            "Route a marketing-science task to one workflow skill, or fetch one named skill. "
            "Use this when the client has not already loaded marketing://skills guidance."
        ),
    )
    async def get_skill_guidance(task: str | None = None, skill_name: str | None = None):
        try:
            _authorize()
            mode, record, alternatives = app.skillpack.resolve_guidance(task, skill_name)
            if mode == "fetch":
                return env(
                    summary={"skill_name": record.manifest.name, "version": record.manifest.version},
                    evidence={
                        "manifest": record.manifest.model_dump(mode="json"),
                        "guidance": record.markdown,
                        "content_hash": record.content_hash,
                    },
                    next_actions=[f"marketing://skills/{record.manifest.name}"],
                )
            return env(
                summary={
                    "recommended_skill": record.manifest.name,
                    "purpose": record.manifest.summary,
                    "maturity": record.manifest.maturity,
                },
                evidence={
                    "resource_uri": f"marketing://skills/{record.manifest.name}",
                    "manifest_uri": f"marketing://skills/{record.manifest.name}/manifest",
                    "alternatives": [
                        {"skill": name, "routing_score": score}
                        for name, score in alternatives
                        if name != record.manifest.name and score > 0
                    ],
                },
                next_actions=[f"marketing://skills/{record.manifest.name}"],
            )
        except DomainError as exc:
            return exc.to_dict()
