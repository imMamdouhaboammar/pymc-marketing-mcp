"""Model_selection MCP tools."""

from __future__ import annotations

from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    CompareModelsInput,
    ModelComparisonInput,
)
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_model_selection_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="compare_models",
        description="Compare diagnostics, predictive metrics, and lineage across multiple fitted MMMs.",
    )
    @mcp_error_boundary("compare_models", "model_selection", "comparison")
    async def compare_models(input: CompareModelsInput):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("compare_models")[0])
        missing = []
        for mid in input.model_ids:
            try:
                model_rec = app.metadata.get_model(mid)
                authorize_model(principal, model_rec, action="read")
            except DomainError:
                missing.append(mid)
        if missing:
            raise DomainError(
                "MODEL_NOT_FOUND",
                f"Model(s) not found: {', '.join(missing)}",
                evidence={"missing_model_ids": missing, "provided_model_ids": input.model_ids},
                next_action="Verify model IDs using get_model_status or fit models first using fit_mmm",
            )

        r = app.models.compare_models(input.model_ids)
        return env(summary=r)

    @mcp.tool(
        name="select_best_model",
        description=(
            "Compare multiple fitted MMMs using PSIS-LOO, WAIC, or Bayesian stacking weights "
            "via ArviZ. All models must be fitted on the same dataset. "
            "Returns ranked specifications, LOO/WAIC scores, and recommended model ID. "
            "Methods: loo (PSIS-LOO), waic (WAIC), stacking (BMA weights), all (run all three)."
        ),
    )
    @mcp_error_boundary("select_best_model", "model_selection", "selection")
    async def select_best_model(config: ModelComparisonInput):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("select_best_model")[0])
        missing = []
        for mid in config.model_ids:
            try:
                model_rec = app.metadata.get_model(mid)
                authorize_model(principal, model_rec, action="read")
            except DomainError:
                missing.append(mid)
        if missing:
            raise DomainError(
                "MODEL_NOT_FOUND",
                f"Model(s) not found: {', '.join(missing)}",
                evidence={"missing_model_ids": missing, "provided_model_ids": config.model_ids},
                next_action="Verify model IDs using get_model_status or fit models first using fit_mmm",
            )

        r = app.models.select_best_model(config)
        return env(
            summary={
                "method": config.method,
                "model_ids": config.model_ids,
                "best_model_id": r.get("best_model_id"),
            },
            evidence=r,
            warnings=r.get("pareto_k_warnings", []),
            next_actions=["get_channel_contributions", "simulate_budget"],
        )
