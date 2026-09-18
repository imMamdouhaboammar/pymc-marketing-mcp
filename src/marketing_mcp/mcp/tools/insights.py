"""Agent Insights & interaction logging MCP tools."""

from __future__ import annotations

from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import QueryInsightsInput, RecordInsightInput
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_insights_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="record_agent_insight",
        description=(
            "Record structured findings, hypotheses, diagnostic warnings, anomalies, or budget "
            "decisions to persistent institutional memory for subsequent coding agents and runs."
        ),
    )
    @mcp_error_boundary("record_agent_insight", "insights", "mutation")
    async def record_agent_insight(
        category: str,
        summary: str,
        details: str | None = None,
        model_id: str | None = None,
        dataset_id: str | None = None,
        agent_id: str | None = None,
        severity: str = "info",
        tags: list[str] | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("record_agent_insight")[0])

        try:
            inp = RecordInsightInput(
                category=category,  # type: ignore[arg-type]
                summary=summary,
                details=details,
                model_id=model_id,
                dataset_id=dataset_id,
                agent_id=agent_id,
                severity=severity,  # type: ignore[arg-type]
                tags=tags or [],
            )
        except Exception as err:
            raise DomainError(
                "INPUT_INVALID",
                f"Invalid insight payload: {err}",
                evidence={"error": str(err)},
                next_action="Verify category, summary length, and severity values",
            ) from err

        rec = app.insights.record_insight(inp, principal=principal)
        return env(
            summary=rec,
            next_actions=["get_agent_insights"],
        )

    @mcp.tool(
        name="get_agent_insights",
        description=(
            "Retrieve previously recorded agent insights, hypotheses, diagnostic notes, or decisions, "
            "filter by model, dataset, category, or tag."
        ),
    )
    @mcp_error_boundary("get_agent_insights", "insights", "query")
    async def get_agent_insights(
        model_id: str | None = None,
        dataset_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("get_agent_insights")[0])

        try:
            q = QueryInsightsInput(
                model_id=model_id,
                dataset_id=dataset_id,
                category=category,  # type: ignore[arg-type]
                tag=tag,
                limit=limit,
            )
        except Exception as err:
            raise DomainError(
                "INPUT_INVALID",
                f"Invalid query parameters: {err}",
                evidence={"error": str(err)},
                next_action="Provide valid query filters or limit between 1 and 100",
            ) from err

        insights = app.insights.list_insights(q, principal=principal)
        return env(
            summary={"insights": insights, "count": len(insights)},
            next_actions=["record_agent_insight"],
        )
