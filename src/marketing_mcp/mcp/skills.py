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

    @mcp.resource(
        "marketing://skills/references/agent-operating-protocol",
        name="agent_operating_protocol",
        description="How an agent operates this server: bootstrap, envelopes, IDs, jobs, polling, error recovery.",
        mime_type="text/markdown",
    )
    async def agent_operating_protocol() -> str:
        try:
            _authorize()
            return registry.get_reference("agent-operating-protocol")
        except DomainError as exc:
            return _json_error(exc)

    @mcp.resource(
        "marketing://skills/references/marketing-decision-playbook",
        name="marketing_decision_playbook",
        description="Translate marketing questions into server workflows and results into decision-ready language.",
        mime_type="text/markdown",
    )
    async def marketing_decision_playbook() -> str:
        try:
            _authorize()
            return registry.get_reference("marketing-decision-playbook")
        except DomainError as exc:
            return _json_error(exc)

    def _session_references(record) -> list[str]:
        return [
            source
            for source in record.manifest.authoritative_sources
            if source.startswith("marketing://skills/references/")
        ]

    @mcp.tool(
        name="get_skill_guidance",
        description=(
            "Start here. Route a marketing-science task to one workflow skill and receive its full "
            "operating guidance inline (tool order, argument templates, gates, error recovery, and "
            "marketing interpretation). Pass task for routing, skill_name to fetch a named skill, or "
            "reference_name to fetch a shared reference such as 'agent-operating-protocol' or "
            "'marketing-decision-playbook' when the client cannot read MCP resources."
        ),
    )
    async def get_skill_guidance(
        task: str | None = None,
        skill_name: str | None = None,
        reference_name: str | None = None,
    ):
        try:
            _authorize()
            if reference_name and not (task or skill_name):
                content = registry.get_reference(reference_name)
                return env(
                    summary={"reference_name": reference_name},
                    evidence={
                        "reference": content,
                        "resource_uri": f"marketing://skills/references/{reference_name}",
                    },
                    next_actions=["get_skill_guidance(task=...) to route the user's request"],
                )
            mode, record, alternatives = app.skillpack.resolve_guidance(task, skill_name)
            references = _session_references(record)
            if mode == "fetch":
                return env(
                    summary={"skill_name": record.manifest.name, "version": record.manifest.version},
                    evidence={
                        "manifest": record.manifest.model_dump(mode="json"),
                        "guidance": record.markdown,
                        "content_hash": record.content_hash,
                        "references": references,
                    },
                    next_actions=[f"marketing://skills/{record.manifest.name}"],
                )
            return env(
                summary={
                    "recommended_skill": record.manifest.name,
                    "purpose": record.manifest.summary,
                    "maturity": record.manifest.maturity,
                    "first_tools": record.manifest.primary_tools[:3],
                },
                evidence={
                    "guidance": record.markdown,
                    "content_hash": record.content_hash,
                    "resource_uri": f"marketing://skills/{record.manifest.name}",
                    "manifest_uri": f"marketing://skills/{record.manifest.name}/manifest",
                    "prerequisites": record.manifest.prerequisites,
                    "gates": record.manifest.gates,
                    "continuations": record.manifest.continuations,
                    "references": references,
                    "alternatives": [
                        {"skill": name, "routing_score": score}
                        for name, score in alternatives
                        if name != record.manifest.name and score > 0
                    ],
                },
                next_actions=[
                    f"Follow the {record.manifest.name} guidance in evidence.guidance",
                    "Read marketing://skills/references/agent-operating-protocol once per session",
                ],
            )
        except DomainError as exc:
            return exc.to_dict()

    @mcp.tool(
        name="list_agentic_skills",
        description=(
            "List all registered agentic skills with summaries, maturity, triggers, and primary tools."
        ),
    )
    async def list_agentic_skills():
        try:
            _authorize()
            catalog = app.skillpack.catalog()
            return env(
                summary={
                    "total_skills": len(catalog["skills"]),
                    "catalog_hash": catalog["catalog_hash"],
                },
                evidence={
                    "skills": [
                        {
                            "name": s["name"],
                            "version": s["version"],
                            "summary": s["summary"],
                            "triggers": s["triggers"],
                            "primary_tools": s["primary_tools"],
                            "maturity": s["maturity"],
                        }
                        for s in catalog["skills"]
                    ],
                    "shared_references": catalog["shared_references"],
                },
                next_actions=[
                    "Use get_skill_guidance(skill_name=...) to fetch operational instructions for a skill",
                    "Use get_skill_guidance(task=...) to route an analytical task to the appropriate skill",
                ],
            )
        except DomainError as exc:
            return exc.to_dict()

    @mcp.tool(
        name="get_skill_workflow_map",
        description=(
            "Retrieve the dependency graph, prerequisites, decision gates, and continuations for all scientific skills."
        ),
    )
    async def get_skill_workflow_map():
        try:
            _authorize()
            return env(
                summary={
                    "total_workflows": len(registry.names()),
                    "rule": "Decision-gated tools cannot be called on models that failed diagnostic gates.",
                },
                evidence=app.skillpack.workflow_map(),
                next_actions=[
                    "Ensure diagnostic gate passes before calling gated tools",
                ],
            )
        except DomainError as exc:
            return exc.to_dict()

