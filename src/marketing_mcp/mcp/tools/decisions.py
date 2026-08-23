"""Decisions MCP tools."""

from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FlightingOptimizationInput,
)


def register_decisions_tools(mcp, app: Application) -> None:
    @mcp.tool(
        name="get_channel_contributions",
        description=(
            "Return posterior channel contribution summaries from the fitted PyMC-Marketing model. "
            "Does not fabricate estimates."
        ),
    )
    async def get_channel_contributions(model_id: str):
        try:
            r = app.decisions.contributions(model_id)
            return env(
                summary={"model_id": model_id, "channels": r["channels"]},
                evidence={"variable": r["variable"]},
                provenance=r["provenance"],
                next_actions=["get_incremental_roas", "simulate_budget"],
            )
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="get_incremental_roas",
        description=(
            "Return total and marginal iROAS from PyMC-Marketing's official incrementality API, "
            "including posterior uncertainty. No ad-hoc LLM ROAS calculation."
        ),
    )
    async def get_incremental_roas(model_id: str):
        try:
            r = app.decisions.iroas(model_id)
            return env(
                summary=r,
                provenance=r.get("provenance", {}),
                next_actions=["simulate_budget", "optimize_budget"],
            )
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="get_response_curves",
        description="Return response/saturation information sampled by PyMC-Marketing rather than raw posterior arrays.",
    )
    async def get_response_curves(model_id: str):
        try:
            r = app.decisions.response_curves(model_id)
            return env(summary=r, provenance=r.get("provenance", {}))
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="simulate_budget",
        description=(
            "Evaluate the exact requested channel or dimension-cell scenario with posterior "
            "response sampling. Rejected models are blocked."
        ),
    )
    async def simulate_budget(config: BudgetSimulationInput):
        try:
            r = app.decisions.simulate(config)
            return env(
                summary=r,
                warnings=r.get("warnings", []),
                evidence={"caveats": r.get("caveats", [])},
                provenance=r.get("provenance", {}),
            )
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="optimize_budget",
        description=(
            "Use PyMC-Marketing budget optimization under channel or dimension-cell constraints, "
            "then compare baseline and recommended posterior responses. Requires a diagnosed model."
        ),
    )
    async def optimize_budget(config: BudgetOptimizationInput):
        try:
            r = app.decisions.optimize(config)
            return env(
                summary=r,
                warnings=r.get("warnings", []),
                provenance=r.get("provenance", {}),
            )
        except DomainError as e:
            return e.to_dict()


    @mcp.tool(
        name="recommend_next_measurement",
        description=(
            "Recommend evidence-gathering options when model/data signals imply material uncertainty. "
            "It can explicitly return that no single experiment is implied."
        ),
    )
    async def recommend_next_measurement(model_id: str):
        try:
            return env(summary=app.decisions.recommend_measurement(model_id))
        except DomainError as e:
            return e.to_dict()


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
    async def optimize_flighting(config: FlightingOptimizationInput):
        try:
            r = app.decisions.optimize_flighting(config)
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
        except DomainError as e:
            return e.to_dict()

    # -----------------------------------------------------------------------
    # Phase 5 — Bayesian Model Comparison (LOO/WAIC/Stacking)
    # -----------------------------------------------------------------------
