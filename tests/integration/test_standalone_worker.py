"""Separate-process acceptance for durable job execution."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.storage.migrations import MigrationRunner


def _repository(path: Path) -> SQLiteJobRepository:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    MigrationRunner(connection).apply_pending()
    return SQLiteJobRepository(connection)


def test_queued_job_completes_after_submitting_process_exits(tmp_path: Path) -> None:
    database = tmp_path / "shared-jobs.db"
    submitter = _repository(database)
    submitter.create_job(
        JobRecord(
            job_id="job-separate-process",
            job_type="test.echo",
            owner="analyst",
            tenant_id="tenant-a",
            payload={"value": "persisted"},
        )
    )
    submitter.conn.close()

    worker_code = """
import sqlite3
import sys
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.storage.migrations import MigrationRunner

connection = sqlite3.connect(sys.argv[1])
connection.row_factory = sqlite3.Row
MigrationRunner(connection).apply_pending()
repository = SQLiteJobRepository(connection)
worker = ProcessJobWorker(
    repository,
    handlers={"test.echo": lambda job: {"value": job.payload["value"], "tenant": job.tenant_id}},
    worker_id="worker-child",
)
raise SystemExit(0 if worker.execute_next_job() else 2)
"""
    result = subprocess.run(
        [sys.executable, "-c", worker_code, str(database)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    observer = _repository(database)
    completed = observer.get_job("job-separate-process")
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.result == {"value": "persisted", "tenant": "tenant-a"}
    assert completed.attempts == 1
    assert completed.lease_owner is None
    observer.conn.close()
