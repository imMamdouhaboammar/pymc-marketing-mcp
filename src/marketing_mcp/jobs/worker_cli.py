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
from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.principal import Principal
from marketing_mcp.storage.metadata import SQLiteMetadataStore


def build_fit_mmm_handler(app: Application) -> Callable[[JobRecord], dict[str, Any]]:
    """Build the standalone fit handler using persisted job ownership."""

    def fit_mmm(job: JobRecord) -> dict[str, Any]:
        config = FitMMMInput.model_validate(job.payload)
        principal = Principal(
            subject=job.owner,
            auth_type="oauth" if job.tenant_id else "stdio",
            tenant_id=job.tenant_id,
        )
        return app.models.fit(config, principal).model_dump()

    return fit_mmm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="marketing-mcp-worker", description="Background compute worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Interval in seconds to poll for queued jobs")
    args = parser.parse_args(argv)

    app = Application()
    heartbeat_store = SQLiteMetadataStore(app.settings.metadata_db)
    heartbeat_repo = SQLiteJobRepository(heartbeat_store.conn)
    worker = ProcessJobWorker(
        app.job_repo,
        handlers={"fit_mmm": build_fit_mmm_handler(app)},
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
