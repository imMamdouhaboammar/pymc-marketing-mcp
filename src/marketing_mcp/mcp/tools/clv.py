"""Clv MCP tools."""

from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    EstimateCLVInput,
    FitCLVInput,
    FitPurchaseModelInput,
    FitValueModelInput,
    PredictCLVInput,
    PredictExpectedPurchasesInput,
    PredictExpectedSpendInput,
    PredictProbabilityAliveInput,
)


def register_clv_tools(mcp, app: Application) -> None:
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
