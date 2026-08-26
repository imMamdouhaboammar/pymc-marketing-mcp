"""CLI entrypoint for standalone background worker process."""

from __future__ import annotations

import argparse
import time

from marketing_mcp.app import Application
from marketing_mcp.jobs.process_worker import ProcessJobWorker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="marketing-mcp-worker", description="Background compute worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Interval in seconds to poll for queued jobs")
    args = parser.parse_args(argv)

    app = Application()
    worker = ProcessJobWorker(app.job_repo)

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
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
