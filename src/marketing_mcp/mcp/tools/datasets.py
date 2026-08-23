"""Datasets MCP tools."""

from __future__ import annotations

from pathlib import Path

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.security import safe_ingest_path


def register_datasets_tools(mcp, app: Application) -> None:
    @mcp.tool(
        name="register_dataset",
        description="Register a local CSV or Parquet marketing dataset and return a stable dataset reference.",
    )
    async def register_dataset(path: str):
        try:
            source = safe_ingest_path(
                Path(path), app.settings.ingest_dir, app.settings.max_dataset_mb * 1024 * 1024
            )
            r = app.datasets.register_file(source)
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
