"""Datasets MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.security import safe_ingest_path
from marketing_mcp.security.ownership import authorize_dataset
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_datasets_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="register_dataset",
        description="Register a local CSV or Parquet marketing dataset and return a stable dataset reference.",
    )
    async def register_dataset(path: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("register_dataset")[0])
            source = safe_ingest_path(
                Path(path), app.settings.ingest_dir, app.settings.max_dataset_mb * 1024 * 1024
            )
            r = app.datasets.register_file(source, principal=principal)
            return env(
                summary=r.model_dump(),
                provenance={"fingerprint": r.fingerprint},
                next_actions=["inspect_dataset", "validate_dataset"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="inspect_dataset",
        description=(
            "Inspect a registered dataset before MMM configuration. "
            "Returns candidate targets, channels, controls, frequency, and data issues."
        ),
    )
    async def inspect_dataset(dataset_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("inspect_dataset")[0])
            dataset = app.metadata.get_dataset(dataset_id)
            if not dataset:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
            authorize_dataset(principal, dataset, action="read")

            r = app.datasets.inspect(dataset_id)
            return env(
                summary=r.model_dump(),
                warnings=[x.model_dump() for x in r.issues],
                next_actions=["validate_dataset"] if r.mmm_candidate else ["repair_dataset"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="validate_dataset",
        description=(
            "Run MMM-specific data quality, panel-shape, and identifiability checks. "
            "This must pass before fitting."
        ),
    )
    async def validate_dataset(
        dataset_id: str,
        date_column: str,
        target_column: str,
        channel_columns: list[str],
        control_columns: list[str] | None = None,
        dims: list[str] | None = None,
    ):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("validate_dataset")[0])
            dataset = app.metadata.get_dataset(dataset_id)
            if not dataset:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
            authorize_dataset(principal, dataset, action="read")

            r = app.datasets.validate(
                dataset_id,
                date_column,
                target_column,
                channel_columns,
                control_columns or [],
                dims or [],
            )
            return env(
                summary={"dataset_id": dataset_id, "valid_for_modeling": r.valid_for_modeling},
                evidence={"findings": [f.model_dump() for f in r.findings]},
                next_actions=["fit_mmm"] if r.valid_for_modeling else ["repair_dataset"],
            )
        except DomainError as e:
            return e.to_dict()
