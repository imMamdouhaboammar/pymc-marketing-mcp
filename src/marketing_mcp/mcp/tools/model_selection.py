"""Model_selection MCP tools."""

from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    CompareModelsInput,
    ModelComparisonInput,
)


def register_model_selection_tools(mcp, app: Application) -> None:
    @mcp.tool(
        name="compare_models",
        description="Compare diagnostics, predictive metrics, and lineage across multiple fitted MMMs.",
    )
    async def compare_models(input: CompareModelsInput):
        try:
            r = app.models.compare_models(input.model_ids)
            return env(summary=r)
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="select_best_model",
        description=(
            "Compare multiple fitted MMMs using PSIS-LOO, WAIC, or Bayesian stacking weights "
            "via ArviZ. All models must be fitted on the same dataset. "
            "Returns ranked specifications, LOO/WAIC scores, and recommended model ID. "
            "Methods: loo (PSIS-LOO), waic (WAIC), stacking (BMA weights), all (run all three)."
        ),
    )
    async def select_best_model(config: ModelComparisonInput):
        try:
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
        except DomainError as e:
            return e.to_dict()
