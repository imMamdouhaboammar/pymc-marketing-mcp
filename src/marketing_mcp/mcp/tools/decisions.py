"""Decisions MCP tools."""

from __future__ import annotations

import asyncio
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.operation_guard import ConcurrencyCancellationGuard
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FlightingOptimizationInput,
)
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_decisions_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="get_channel_contributions",
        description=(
            "Return posterior channel contribution summaries from the fitted PyMC-Marketing model. "
            "Does not fabricate estimates."
        ),
    )
    @mcp_error_boundary("get_channel_contributions", "decisions", "inference")
    async def get_channel_contributions(model_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("get_channel_contributions")[0])
        model_rec = app.metadata.get_model(model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        r = app.decisions.contributions(model_id)
        return env(
            summary={"model_id": model_id, "channels": r["channels"]},
            evidence={"variable": r["variable"]},
            provenance=r["provenance"],
            next_actions=["get_incremental_roas", "simulate_budget"],
        )

    @mcp.tool(
        name="get_incremental_roas",
        description=(
            "Return total and marginal iROAS from PyMC-Marketing's official incrementality API, "
            "including posterior uncertainty. No ad-hoc LLM ROAS calculation."
        ),
    )
    @mcp_error_boundary("get_incremental_roas", "decisions", "inference")
    async def get_incremental_roas(model_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("get_incremental_roas")[0])
        model_rec = app.metadata.get_model(model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        r = app.decisions.iroas(model_id)
        return env(
            summary=r,
            provenance=r.get("provenance", {}),
            next_actions=["simulate_budget", "optimize_budget"],
        )

    @mcp.tool(
        name="get_response_curves",
        description="Return response/saturation information sampled by PyMC-Marketing rather than raw posterior arrays.",
    )
    @mcp_error_boundary("get_response_curves", "decisions", "inference")
    async def get_response_curves(model_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("get_response_curves")[0])
        model_rec = app.metadata.get_model(model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        r = app.decisions.response_curves(model_id)
        return env(summary=r, provenance=r.get("provenance", {}))

    @mcp.tool(
        name="simulate_budget",
        description=(
            "Evaluate the exact requested channel or dimension-cell scenario with posterior "
            "response sampling. Rejected models are blocked."
        ),
    )
    @mcp_error_boundary("simulate_budget", "decisions", "inference")
    async def simulate_budget(config: BudgetSimulationInput):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("simulate_budget")[0])
        model_rec = app.metadata.get_model(config.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{config.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        r = app.decisions.simulate(config)
        return env(
            summary=r,
            warnings=r.get("warnings", []),
            evidence={"caveats": r.get("caveats", [])},
            provenance=r.get("provenance", {}),
        )

    @mcp.tool(
        name="optimize_budget",
        description=(
            "Use PyMC-Marketing budget optimization under channel or dimension-cell constraints, "
            "then compare baseline and recommended posterior responses. Requires a diagnosed model."
        ),
    )
    @mcp_error_boundary("optimize_budget", "decisions", "optimization")
    async def optimize_budget(config: BudgetOptimizationInput):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("optimize_budget")[0])
        model_rec = app.metadata.get_model(config.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{config.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        guard = getattr(app, "operation_guard", None)
        if isinstance(guard, ConcurrencyCancellationGuard):
            r = await guard.run_tracked_executor(
                "optimize_budget",
                lambda cancel_ev: app.decisions.optimize(config, cancel_event=cancel_ev),
                principal=principal,
                details={"model_id": config.model_id},
                identity_key=f"opt_{config.model_id}",
            )
        else:
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(None, lambda: app.decisions.optimize(config))
        return env(
            summary=r,
            warnings=r.get("warnings", []),
            evidence={
                "identifiability_risks": r.get("identifiability_risks", []),
                "channel_confidence": r.get("channel_confidence", {}),
            },
            provenance=r.get("provenance", {}),
        )

    @mcp.tool(
        name="recommend_next_measurement",
        description=(
            "Recommend evidence-gathering options when model/data signals imply material uncertainty. "
            "It can explicitly return that no single experiment is implied."
        ),
    )
    @mcp_error_boundary("recommend_next_measurement", "decisions", "inference")
    async def recommend_next_measurement(model_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("recommend_next_measurement")[0])
        model_rec = app.metadata.get_model(model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        return env(summary=app.decisions.recommend_measurement(model_id))

    @mcp.tool(
        name="optimize_flighting",
        description=(
            "Optimize a dynamic weekly media flighting schedule over a planning horizon, "
            "accounting for adstock carryover dynamics, channel spend constraints, "
            "target iROAS floors, and profit-maximization objectives. "
            "The model must be approved or approved_with_caution before optimization. "
            "Returns a week-by-week spend table per channel, posterior response distribution, "
            "and net-profit estimates."
        ),
    )
    @mcp_error_boundary("optimize_flighting", "decisions", "optimization")
    async def optimize_flighting(config: FlightingOptimizationInput):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("optimize_flighting")[0])
        model_rec = app.metadata.get_model(config.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{config.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        guard = getattr(app, "operation_guard", None)
        if isinstance(guard, ConcurrencyCancellationGuard):
            r = await guard.run_tracked_executor(
                "optimize_flighting",
                lambda cancel_ev: app.decisions.optimize_flighting(config, cancel_event=cancel_ev),
                principal=principal,
                details={"model_id": config.model_id},
                identity_key=f"flighting_{config.model_id}",
            )
        else:
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(None, lambda: app.decisions.optimize_flighting(config))
        return env(
            summary={
                "model_id": config.model_id,
                "total_budget": config.total_budget,
                "planning_weeks": config.planning_weeks,
                "objective": config.objective,
            },
            evidence=r,
            next_actions=["simulate_budget", "get_channel_contributions"],
        )
