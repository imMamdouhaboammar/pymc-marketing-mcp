"""MCP resource registration for datasets, models, diagnostics, lineage, plots, and CLV."""

from __future__ import annotations

import json

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError


def register_resources(mcp, app: Application) -> None:
    @mcp.resource("marketing://models/{model_id}/plots/{plot_type}")
    async def plot_resource(model_id: str, plot_type: str) -> bytes:
        """Serve a cached posterior plot as raw bytes (PNG)."""
        try:
            cached = app.plots.get_cached_plot(model_id, plot_type)
            if cached is not None:
                return cached
            # Not yet generated — return JSON error
            import json as _json

            return _json.dumps(
                {
                    "error": {
                        "code": "PLOT_NOT_CACHED",
                        "message": f"Plot '{plot_type}' for model '{model_id}' has not been generated yet.",
                        "next_action": "Call get_posterior_plots first to generate the plot.",
                    }
                }
            ).encode()
        except (DomainError, OSError, ValueError, KeyError) as e:
            import json as _json

            return _json.dumps(
                {"error": {"code": "PLOT_RESOURCE_ERROR", "message": str(e)}}
            ).encode()

    @mcp.resource("marketing://datasets/{dataset_id}")
    async def dataset_resource(dataset_id: str) -> str:
        try:
            return json.dumps(app.metadata.get_dataset(dataset_id), indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}")
    async def model_resource(model_id: str) -> str:
        try:
            return json.dumps(app.metadata.get_model(model_id), indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}/diagnostics")
    async def diagnostics_resource(model_id: str) -> str:
        try:
            model = app.metadata.get_model(model_id)
            return json.dumps(model.get("diagnostics"), indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)

    @mcp.resource("marketing://models/{model_id}/lineage")
    async def lineage_resource(model_id: str) -> str:
        try:
            model = app.metadata.get_model(model_id)
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
            return json.dumps(app.metadata.get_clv_model(model_id), indent=2)
        except DomainError as e:
            return json.dumps(e.to_dict(), indent=2)
