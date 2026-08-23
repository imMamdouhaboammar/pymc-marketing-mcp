from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.mcp.resources import register_resources
from marketing_mcp.mcp.tools.datasets import register_datasets_tools
from marketing_mcp.mcp.tools.mmm import register_mmm_tools
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    CompareModelsInput,
    EstimateCLVInput,
    FitCLVInput,
    FitPurchaseModelInput,
    FitValueModelInput,
    FlightingOptimizationInput,
    ModelComparisonInput,
    PredictCLVInput,
    PredictExpectedPurchasesInput,
    PredictExpectedSpendInput,
    PredictProbabilityAliveInput,
)


def create_server(app: Application | None = None):
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as e:
        raise RuntimeError("Install project dependencies to run the MCP server") from e

    app = app or Application()
    mcp = MCPServer(
        "PyMC Marketing MCP",
        instructions=(
            "Use this server for statistical marketing calculations with PyMC-Marketing. "
            "Never invent or hallucinate posterior estimates. Always diagnose fitted MMMs "
            "before using budget simulation or optimization tools."
        ),
    )

    register_resources(mcp, app)
    register_mmm_tools(mcp, app)
    register_datasets_tools(mcp, app)







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
        name="fit_purchase_model",
        description=(
            "Fit a Bayesian purchase/transaction frequency model (BG/NBD or Shifted Beta-Geometric). "
            "Normalizes user column names to canonical RFM attributes."
        ),
    )
    async def fit_purchase_model(config: FitPurchaseModelInput):
        try:
            r = app.clv.fit_purchase_model(config)
            return env(
                summary=r.model_dump(),
                provenance=r.package_provenance,
                next_actions=["predict_expected_purchases", "predict_probability_alive"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="fit_value_model",
        description=(
            "Fit a Bayesian monetary value transaction model (Gamma-Gamma) on repeat customer spending. "
            "Requires frequency and average monetary value columns."
        ),
    )
    async def fit_value_model(config: FitValueModelInput):
        try:
            r = app.clv.fit_value_model(config)
            return env(
                summary=r.model_dump(),
                provenance=r.package_provenance,
                next_actions=["predict_expected_spend", "estimate_customer_lifetime_value"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="predict_expected_purchases",
        description="Predict expected future purchase counts per customer from a fitted purchase model (BG/NBD).",
    )
    async def predict_expected_purchases(config: PredictExpectedPurchasesInput):
        try:
            r = app.clv.predict_expected_purchases(config)
            return env(
                summary={
                    "model_id": config.model_id,
                    "future_t": config.future_t,
                    "total_customers": r.get("total_customers"),
                    "returned_customers": r.get("returned_customers"),
                    "summary_stats": r.get("summary"),
                },
                evidence=r,
                next_actions=["predict_probability_alive", "estimate_customer_lifetime_value"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="predict_probability_alive",
        description="Estimate probability of customer retention/alive from a fitted purchase or churn model.",
    )
    async def predict_probability_alive(config: PredictProbabilityAliveInput):
        try:
            r = app.clv.predict_probability_alive(config)
            return env(
                summary={
                    "model_id": config.model_id,
                    "total_customers": r.get("total_customers"),
                    "returned_customers": r.get("returned_customers"),
                    "summary_stats": r.get("summary"),
                },
                evidence=r,
                next_actions=["get_churn_risk_cohorts", "estimate_customer_lifetime_value"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="predict_expected_spend",
        description="Predict average transaction monetary spend per customer from a fitted Gamma-Gamma value model.",
    )
    async def predict_expected_spend(config: PredictExpectedSpendInput):
        try:
            r = app.clv.predict_expected_spend(config)
            return env(
                summary={
                    "model_id": config.model_id,
                    "total_customers": r.get("total_customers"),
                    "returned_customers": r.get("returned_customers"),
                    "summary_stats": r.get("summary"),
                },
                evidence=r,
                next_actions=["estimate_customer_lifetime_value"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="estimate_customer_lifetime_value",
        description=(
            "Estimate discounted net present Customer Lifetime Value (CLV) by combining a fitted "
            "purchase model (e.g. BG/NBD) and monetary value model (e.g. Gamma-Gamma)."
        ),
    )
    async def estimate_customer_lifetime_value(config: EstimateCLVInput):
        try:
            r = app.clv.estimate_customer_lifetime_value(config)
            return env(
                summary={
                    "purchase_model_id": config.purchase_model_id,
                    "value_model_id": config.value_model_id,
                    "future_t": config.future_t,
                    "discount_rate": config.discount_rate,
                    "total_customers": r.get("total_customers"),
                    "returned_customers": r.get("returned_customers"),
                    "summary_stats": r.get("summary"),
                },
                evidence=r,
                next_actions=["get_churn_risk_cohorts"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="fit_clv_model",
        description=(
            "Fit a Bayesian Customer Lifetime Value (CLV) model on RFM transaction data. "
            "(Deprecated: prefer fit_purchase_model or fit_value_model)."
        ),
    )
    async def fit_clv_model(config: FitCLVInput):
        try:
            r = app.clv.fit_clv(config)
            return env(
                summary=r.model_dump(),
                provenance=r.package_provenance,
                warnings=["fit_clv_model is deprecated; use fit_purchase_model or fit_value_model"],
                next_actions=["predict_customer_clv", "get_churn_risk_cohorts"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="predict_customer_clv",
        description=(
            "Generate per-customer CLV predictions from a fitted BG/NBD model. "
            "(Deprecated: prefer predict_expected_purchases or estimate_customer_lifetime_value)."
        ),
    )
    async def predict_customer_clv(config: PredictCLVInput):
        try:
            r = app.clv.predict_clv(config)
            return env(
                summary={
                    "model_id": config.model_id,
                    "future_t": config.future_t,
                    "total_customers": r.get("total_customers"),
                },
                evidence=r,
                warnings=["predict_customer_clv is deprecated; use predict_expected_purchases"],
                next_actions=["get_churn_risk_cohorts"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="get_churn_risk_cohorts",
        description=(
            "Identify customers at churn risk from a fitted CLV model. "
            "Returns customers whose Bayesian P(alive) is below the specified threshold. "
            "Lower threshold = higher confidence of churn. Default threshold: 0.3."
        ),
    )
    async def get_churn_risk_cohorts(model_id: str, threshold_p_alive: float = 0.3):
        try:
            r = app.clv.get_churn_risk_cohorts(model_id, threshold=threshold_p_alive)
            return env(
                summary={
                    "model_id": model_id,
                    "threshold": threshold_p_alive,
                    "at_risk_count": r.get("at_risk_count"),
                    "at_risk_pct": r.get("at_risk_pct"),
                },
                evidence=r,
                next_actions=["predict_customer_clv"],
            )
        except DomainError as e:
            return e.to_dict()

    # -----------------------------------------------------------------------
    # Phase 4 — Dynamic Multi-Period Flighting Optimization
    # -----------------------------------------------------------------------

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

    return mcp