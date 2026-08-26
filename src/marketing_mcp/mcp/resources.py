"""MCP resource registration for datasets, models, diagnostics, lineage, plots, and CLV."""

from __future__ import annotations

import json
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.context import stdio_context_provider
from marketing_mcp.security.ownership import authorize_dataset, authorize_model, authorize_resource
from marketing_mcp.security.policy import require_scope


def register_resources(mcp, app: Application, context_provider: Any = None) -> None:
    resolve_context = context_provider or stdio_context_provider

    @mcp.resource("marketing://models/{model_id}/plots/{plot_type}")
    async def plot_resource(model_id: str, plot_type: str) -> bytes:
        """Serve a cached posterior plot as raw bytes (PNG)."""
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            model = app.metadata.get_model(model_id)
            if not model:
                return json.dumps(
                    DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found").to_dict()
                ).encode()
            authorize_model(principal, model, action="read")

            cached = app.plots.get_cached_plot(model_id, plot_type)
            if cached is not None:
                return cached
            return json.dumps(
                {
                    "error": {
                        "code": "PLOT_NOT_CACHED",
                        "message": f"Plot '{plot_type}' for model '{model_id}' has not been generated yet.",
                        "next_action": "Call get_posterior_plots first to generate the plot.",
                    }
                }
            ).encode()
        except DomainError as e:
            return json.dumps(e.to_dict()).encode()
        except (OSError, ValueError, KeyError) as e:
            return json.dumps({"error": {"code": "PLOT_RESOURCE_ERROR", "message": str(e)}}).encode()

    @mcp.resource("marketing://datasets/{dataset_id}")
    async def dataset_resource(dataset_id: str) -> str:
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            dataset = app.metadata.get_dataset(dataset_id)
            if not dataset:
                return json.dumps(
                    DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found").to_dict(),
                    indent=2,
                )
            authorize_dataset(principal, dataset, action="read")
            return json.dumps(dataset, indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}")
    async def model_resource(model_id: str) -> str:
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            model = app.metadata.get_model(model_id)
            if not model:
                return json.dumps(
                    DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found").to_dict(),
                    indent=2,
                )
            authorize_model(principal, model, action="read")
            return json.dumps(model, indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}/diagnostics")
    async def diagnostics_resource(model_id: str) -> str:
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            model = app.metadata.get_model(model_id)
            if not model:
                return json.dumps(
                    DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found").to_dict(),
                    indent=2,
                )
            authorize_model(principal, model, action="read")
            return json.dumps(model.get("diagnostics"), indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}/lineage")
    async def lineage_resource(model_id: str) -> str:
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            model = app.metadata.get_model(model_id)
            if not model:
                return json.dumps(
                    DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found").to_dict(),
                    indent=2,
                )
            authorize_model(principal, model, action="read")
            return json.dumps(
                {
                    "model_id": model.get("model_id"),
                    "parent_model_id": model.get("parent_model_id"),
                    "lineage_stage": model.get("lineage_stage"),
                    "dataset_id": model.get("dataset_id"),
                    "dataset_fingerprint": model.get("dataset_fingerprint"),
                    "semantic_config_hash": model.get("semantic_config_hash"),
                    "package_provenance": model.get("package_provenance"),
                    "created_at": model.get("created_at"),
                },
                indent=2,
            )
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://clv/{model_id}")
    async def clv_model_resource(model_id: str) -> str:
        try:
            principal = resolve_context().principal
            require_scope(principal, "marketing:read")
            clv_model = app.metadata.get_clv_model(model_id)
            if not clv_model:
                return json.dumps(
                    DomainError("MODEL_NOT_FOUND", f"CLV Model '{model_id}' was not found").to_dict(),
                    indent=2,
                )
            authorize_resource(principal, clv_model, resource_type="clv_model", action="read")
            return json.dumps(clv_model, indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)
