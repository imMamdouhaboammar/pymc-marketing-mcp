"""Mmm MCP tools."""

from __future__ import annotations

from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    ArchiveModelInput,
    CalibrateMMMInput,
    CrossValidateMMMInput,
    FitMMMInput,
    GetPosteriorPlotsInput,
    PriorSensitivityInput,
)
from marketing_mcp.security.ownership import authorize_dataset, authorize_model
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_mmm_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="fit_mmm",
        description=(
            "Fit a real Bayesian Marketing Mix Model with PyMC-Marketing using typed, "
            "controlled configuration. No arbitrary Python is accepted. "
            "Supports adstock types: geometric (default), delayed, weibull_cdf, weibull_pdf, binomial, none. "
            "Supports saturation types: logistic (default), tanh, tanh_baselined, michaelis_menten, "
            "hill, hill_sigmoid, inverse_scaled_logistic, log, root, none. "
            "Per-channel adstock/saturation overrides can be set via channel_priors."
        ),
    )
    async def fit_mmm(config: FitMMMInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("fit_mmm")[0])
            dataset = app.metadata.get_dataset(config.dataset_id)
            if not dataset:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{config.dataset_id}' was not found")
            authorize_dataset(principal, dataset, action="read")

            r = app.models.fit(config, principal=principal)
            return env(
                summary=r.model_dump(),
                provenance=r.config.get("provenance", {}),
                next_actions=["diagnose_mmm"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="get_model_status",
        description="Get persisted model fit state, lineage, and safe failure information.",
    )
    async def get_model_status(model_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("get_model_status")[0])
            model_rec = app.metadata.get_model(model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
            authorize_model(principal, model_rec, action="read")

            return env(summary=app.models.status(model_id).model_dump())
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="diagnose_mmm",
        description=(
            "Mandatory diagnostic gate. Checks sampler health plus posterior predictive "
            "coverage, predictive error, and residual behavior before decision tools may run."
        ),
    )
    async def diagnose_mmm(model_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("diagnose_mmm")[0])
            model_rec = app.metadata.get_model(model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
            authorize_model(principal, model_rec, action="read")

            r = app.diagnostics.diagnose(model_id)
            next_acts = ["get_channel_contributions", "get_incremental_roas", "get_response_curves"]
            if r.decision_tools_enabled:
                next_acts.extend(["simulate_budget", "optimize_budget", "cross_validate_mmm"])
            else:
                next_acts.append("refit_model")
            return env(
                summary={
                    "model_id": model_id,
                    "decision_status": r.decision_status,
                    "decision_tools_enabled": r.decision_tools_enabled,
                },
                evidence=r.diagnostics,
                warnings=[w.model_dump() for w in r.warnings],
                next_actions=next_acts,
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="cross_validate_mmm",
        description=(
            "Run rolling Time-Slice Cross-Validation with PyMC-Marketing. "
            "Evaluates out-of-sample predictive RMSE/NRMSE across multiple temporal folds."
        ),
    )
    async def cross_validate_mmm(input: CrossValidateMMMInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("cross_validate_mmm")[0])
            model_rec = app.metadata.get_model(input.model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
            authorize_model(principal, model_rec, action="read")

            r = app.diagnostics.cross_validate(input)
            return env(
                summary=r,
                warnings=r.get("stability_findings", []),
                next_actions=["diagnose_mmm", "optimize_budget"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="evaluate_prior_sensitivity",
        description=(
            "Evaluate sensitivity of commercial conclusions (channel rank order and iROAS) "
            "under alternative adstock and saturation priors."
        ),
    )
    async def evaluate_prior_sensitivity(input: PriorSensitivityInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("evaluate_prior_sensitivity")[0])
            model_rec = app.metadata.get_model(input.model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
            authorize_model(principal, model_rec, action="read")

            r = app.diagnostics.prior_sensitivity(input)
            return env(
                summary=r,
                warnings=r.get("findings", []),
                next_actions=["calibrate_mmm", "recommend_next_measurement"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="calibrate_mmm",
        description=(
            "Calibrate an existing MMM using experimental lift test measurements. "
            "Produces a new calibrated model artifact linked via lineage."
        ),
    )
    async def calibrate_mmm(input: CalibrateMMMInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("calibrate_mmm")[0])
            model_rec = app.metadata.get_model(input.model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
            authorize_model(principal, model_rec, action="calibrate")

            r = app.models.calibrate(input, principal=principal)
            return env(
                summary=r.model_dump(),
                provenance={"parent_model_id": input.model_id, **r.package_provenance},
                next_actions=["diagnose_mmm", "compare_models"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="archive_model",
        description="Archive a model record and update its lifecycle state.",
    )
    async def archive_model(input: ArchiveModelInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("archive_model")[0])
            model_rec = app.metadata.get_model(input.model_id)
            if not model_rec:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
            authorize_model(principal, model_rec, action="archive")

            r = app.models.archive_model(input.model_id)
            return env(summary=r)
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="get_posterior_plots",
        description=(
            "Generate posterior visualization plots from a fitted and approved MMM. "
            "Returns base64-encoded PNG/SVG images in the evidence envelope and caches "
            "them as MCP resources at marketing://models/{model_id}/plots/{plot_type}. "
            "Supported plot types: saturation_curves, waterfall_decomposition, "
            "actual_vs_predicted, channel_contribution_share."
        ),
    )
    async def get_posterior_plots(config: GetPosteriorPlotsInput):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("get_posterior_plots")[0])
            record = app.metadata.get_model(config.model_id)
            if not record:
                return DomainError("MODEL_NOT_FOUND", f"Model {config.model_id} was not found").to_dict()
            authorize_model(principal, record, action="read")

            artifact_path = record.get("artifact_path")
            if not artifact_path:
                return DomainError(
                    "ARTIFACT_NOT_FOUND",
                    f"No artifact found for model {config.model_id}",
                    next_action="Ensure the model was fitted successfully",
                ).to_dict()
            model, _ = app.models.load_model(config.model_id)
            plot_types: list[str] = [str(pt) for pt in config.plot_types]
            plots = app.plots.generate_all(
                model,
                config.model_id,
                plot_types,
                config.format,
            )
            generated = [pt for pt, v in plots.items() if v.get("success")]
            failed = [pt for pt, v in plots.items() if not v.get("success")]
            warnings = [
                {"code": "PLOT_FAILED", "plot_type": pt, "detail": plots[pt].get("error")}
                for pt in failed
            ]
            return env(
                summary={"model_id": config.model_id, "generated": generated, "failed": failed},
                evidence={"plots": plots},
                warnings=warnings,
                next_actions=["get_channel_contributions", "simulate_budget"],
            )
        except DomainError as e:
            return e.to_dict()
