"""CLI entrypoint for standalone background worker process."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.jobs.models import JobRecord
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    CrossValidateMMMInput,
    FitMMMInput,
    FlightingOptimizationInput,
    PriorSensitivityInput,
)
from marketing_mcp.security.principal import Principal
from marketing_mcp.storage.metadata import SQLiteMetadataStore


def build_fit_mmm_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone fit handler using persisted job ownership."""

    def fit_mmm(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        config = FitMMMInput.model_validate(job.payload)
        principal = Principal(
            subject=job.owner,
            auth_type="oauth" if job.tenant_id else "stdio",
            tenant_id=job.tenant_id,
        )
        return app.models.fit(config, principal, cancel_event=cancel_event).model_dump()

    return fit_mmm


def build_transform_ad_export_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone transform handler using persisted job ownership."""

    def transform_ad_export(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        from dataclasses import asdict

        principal = Principal(
            subject=job.owner,
            auth_type="oauth" if job.tenant_id else "stdio",
            tenant_id=job.tenant_id,
        )
        registered, provenance, plan = app.datasets.transform_long_form(
            dataset_id=job.payload["dataset_id"],
            date_column=job.payload["date_column"],
            channel_column=job.payload["channel_column"],
            spend_column=job.payload["spend_column"],
            target_columns=job.payload["target_columns"],
            dimension_columns=job.payload.get("dimension_columns"),
            frequency=job.payload.get("frequency", "D"),
            principal=principal,
            cancel_event=cancel_event,
        )
        return {
            "transformed_dataset_id": registered.dataset_id,
            "input_dataset_id": job.payload["dataset_id"],
            "rows": registered.rows,
            "format": registered.format,
            "spend_reconciled": provenance.spend_reconciled,
            "spend_delta": provenance.spend_delta,
            "calendar_frequency": plan.frequency,
            "inserted_periods": provenance.inserted_periods,
            "provenance": asdict(provenance),
            "transformation_plan": asdict(plan),
        }

    return transform_ad_export


def build_budget_optimization_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone budget optimization handler."""

    def budget_optimize(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        config = BudgetOptimizationInput.model_validate(job.payload)
        return app.decisions.optimize(config, cancel_event=cancel_event)

    return budget_optimize


def build_flighting_optimization_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone flighting optimization handler."""

    def flighting_optimize(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        config = FlightingOptimizationInput.model_validate(job.payload)
        return app.decisions.optimize_flighting(config, cancel_event=cancel_event)

    return flighting_optimize


def build_cross_validate_mmm_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone cross validation handler."""

    def cross_validate_mmm(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        config = CrossValidateMMMInput.model_validate(job.payload)
        return app.diagnostics.cross_validate(config, cancel_event=cancel_event)

    return cross_validate_mmm


def build_prior_sensitivity_handler(app: Application) -> Callable[..., dict[str, Any]]:
    """Build the standalone prior sensitivity handler."""

    def prior_sensitivity(job: JobRecord, cancel_event: Any = None) -> dict[str, Any]:
        config = PriorSensitivityInput.model_validate(job.payload)
        return app.diagnostics.prior_sensitivity(config, cancel_event=cancel_event)

    return prior_sensitivity


def build_default_handlers(app: Application) -> dict[str, Callable[..., dict[str, Any]]]:
    """Build default handlers for all asynchronous background job types."""
    return {
        "fit_mmm": build_fit_mmm_handler(app),
        "transform_ad_export": build_transform_ad_export_handler(app),
        "budget_optimize": build_budget_optimization_handler(app),
        "flighting_optimize": build_flighting_optimization_handler(app),
        "cross_validate_mmm": build_cross_validate_mmm_handler(app),
        "prior_sensitivity": build_prior_sensitivity_handler(app),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="marketing-mcp-worker", description="Background compute worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Interval in seconds to poll for queued jobs")
    parser.add_argument("--metadata-db", "--db", dest="metadata_db", type=str, help="Path to SQLite metadata database")
    parser.add_argument("--data-dir", type=str, help="Path to data directory")
    parser.add_argument("--artifact-dir", type=str, help="Path to artifact directory")
    args = parser.parse_args(argv)

    from pathlib import Path

    from marketing_mcp.config import Settings

    settings_kwargs = {}
    if args.metadata_db:
        settings_kwargs["metadata_db"] = Path(args.metadata_db)
    if args.data_dir:
        settings_kwargs["data_dir"] = Path(args.data_dir)
    if args.artifact_dir:
        settings_kwargs["artifact_dir"] = Path(args.artifact_dir)

    # Always start from environment configuration; CLI flags are selective overrides.
    base_settings = Settings.from_env()
    if settings_kwargs:
        settings = base_settings.model_copy(update=settings_kwargs)
    else:
        settings = base_settings
    app = Application(settings)
    heartbeat_store = SQLiteMetadataStore(app.settings.metadata_db)
    heartbeat_repo = SQLiteJobRepository(heartbeat_store.conn)
    worker = ProcessJobWorker(
        app.job_repo,
        handlers=build_default_handlers(app),
        heartbeat_repository=heartbeat_repo,
    )

    print("Background worker started. Listening for queued statistical compute jobs...")
    try:
        while True:
            did_work = worker.execute_next_job()
            if args.once:
                break
            if not did_work:
                time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("\nWorker shutting down cleanly.")
    finally:
        heartbeat_store.close()
        app.metadata.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
