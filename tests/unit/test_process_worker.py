from __future__ import annotations

import sqlite3
import time
from unittest.mock import MagicMock

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.executor import EnqueueOnlyJobExecutor
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.worker_cli import build_fit_mmm_handler
from marketing_mcp.persistence import SQLitePersistenceBackend
from marketing_mcp.storage.migrations import MigrationRunner


def _repo(path) -> SQLiteJobRepository:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    MigrationRunner(conn).apply_pending()
    return SQLiteJobRepository(conn)


def test_claim_next_job_is_atomic_and_oldest_first(tmp_path) -> None:
    first = _repo(tmp_path / "jobs.db")
    second = _repo(tmp_path / "jobs.db")
    first.create_job(JobRecord(job_id="oldest", job_type="fit_mmm", status=JobStatus.QUEUED))
    first.create_job(JobRecord(job_id="newest", job_type="fit_mmm", status=JobStatus.QUEUED))

    claimed = first.claim_next_job()
    claimed_by_second = second.claim_next_job()

    assert claimed is not None and claimed.job_id == "oldest"
    assert claimed.status == JobStatus.RUNNING
    assert claimed_by_second is not None and claimed_by_second.job_id == "newest"
    assert first.claim_next_job() is None


def test_worker_uses_repository_claim_instead_of_list_then_update() -> None:
    repository = MagicMock()
    job = JobRecord(
        job_id="job-1",
        job_type="fit_mmm",
        status=JobStatus.RUNNING,
        lease_owner="worker-a",
        fence_token=7,
    )
    repository.claim_next_job.return_value = job
    repository.get_job.return_value = job
    worker = ProcessJobWorker(
        repository,
        handlers={"fit_mmm": lambda _: {"model_id": "m1"}},
        worker_id="worker-a",
    )

    assert worker.execute_next_job() is True

    repository.list_jobs.assert_not_called()
    repository.claim_next_job.assert_called_once_with(
        tenant_id=None, worker_id="worker-a", lease_seconds=60
    )
    repository.finish_claim.assert_called_once_with(
        "job-1",
        worker_id="worker-a",
        fence_token=7,
        status=JobStatus.SUCCEEDED,
        result={"model_id": "m1"},
        error=None,
    )


def test_fit_handler_reconstructs_persisted_principal() -> None:
    app = MagicMock()
    summary = MagicMock()
    summary.model_dump.return_value = {"model_id": "m1"}
    app.models.fit.return_value = summary
    job = JobRecord(
        job_id="job-1",
        job_type="fit_mmm",
        status=JobStatus.RUNNING,
        owner="analyst",
        tenant_id="tenant-a",
        payload={
            "dataset_id": "dataset-1",
            "date_column": "date",
            "target_column": "sales",
            "channel_columns": ["search"],
        },
    )

    result = build_fit_mmm_handler(app)(job)

    config, principal = app.models.fit.call_args.args
    assert config.dataset_id == "dataset-1"
    assert principal.subject == "analyst"
    assert principal.tenant_id == "tenant-a"
    assert result == {"model_id": "m1"}


def test_claim_lease_heartbeat_and_fencing_prevent_stale_publication(tmp_path) -> None:
    repository = _repo(tmp_path / "jobs.db")
    repository.create_job(JobRecord(job_id="job-lease", job_type="fit_mmm"))

    first = repository.claim_next_job(worker_id="worker-a", lease_seconds=60)
    assert first is not None
    assert first.lease_owner == "worker-a"
    assert first.fence_token == 1
    assert first.attempts == 1
    original_expiry = first.lease_expires_at
    assert repository.renew_lease(
        first.job_id,
        worker_id="worker-a",
        fence_token=first.fence_token,
        lease_seconds=120,
    )
    assert repository.get_job(first.job_id).lease_expires_at > original_expiry

    repository.conn.execute(
        "UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?",
        ("2000-01-01T00:00:00+00:00", first.job_id),
    )
    repository.conn.commit()
    assert repository.recover_stale_running_jobs() == 1
    second = repository.claim_next_job(worker_id="worker-b", lease_seconds=60)
    assert second is not None and second.fence_token == 2

    with pytest.raises(DomainError, match="stale job claim"):
        repository.finish_claim(
            first.job_id,
            worker_id="worker-a",
            fence_token=first.fence_token,
            status=JobStatus.SUCCEEDED,
            result={"model_id": "stale"},
        )
    completed = repository.finish_claim(
        second.job_id,
        worker_id="worker-b",
        fence_token=second.fence_token,
        status=JobStatus.SUCCEEDED,
        result={"model_id": "winner"},
    )
    assert completed.result == {"model_id": "winner"}


def test_fresh_lease_is_not_recovered_and_cancellation_wins_race(tmp_path) -> None:
    repository = _repo(tmp_path / "jobs.db")
    repository.create_job(JobRecord(job_id="job-cancel", job_type="fit_mmm"))

    claimed = repository.claim_next_job(worker_id="worker-a", lease_seconds=60)
    assert claimed is not None
    assert repository.recover_stale_running_jobs() == 0
    cancelling = repository.request_cancellation(claimed.job_id)
    assert cancelling.status == JobStatus.CANCELLING

    with pytest.raises(DomainError, match="cancellation"):
        repository.finish_claim(
            claimed.job_id,
            worker_id="worker-a",
            fence_token=claimed.fence_token,
            status=JobStatus.SUCCEEDED,
            result={"model_id": "must-not-publish"},
        )
    cancelled = repository.finish_claim(
        claimed.job_id,
        worker_id="worker-a",
        fence_token=claimed.fence_token,
        status=JobStatus.CANCELLED,
    )
    assert cancelled.status == JobStatus.CANCELLED
    assert cancelled.result is None


def test_process_worker_uses_fenced_completion_and_honors_cancellation(tmp_path) -> None:
    repository = _repo(tmp_path / "jobs.db")
    repository.create_job(JobRecord(job_id="job-race", job_type="fit_mmm"))

    def cancel_during_handler(job: JobRecord) -> dict[str, str]:
        repository.request_cancellation(job.job_id)
        return {"model_id": "must-not-publish"}

    worker = ProcessJobWorker(
        repository,
        handlers={"fit_mmm": cancel_during_handler},
        worker_id="worker-a",
    )
    assert worker.execute_next_job() is True
    completed = repository.get_job("job-race")
    assert completed.status == JobStatus.CANCELLED
    assert completed.result is None


def test_process_worker_heartbeats_long_running_claim() -> None:
    repository = MagicMock()
    heartbeat_repository = MagicMock()
    heartbeat_repository.renew_lease.return_value = True
    job = JobRecord(
        job_id="job-long",
        job_type="fit_mmm",
        status=JobStatus.RUNNING,
        lease_owner="worker-a",
        fence_token=3,
    )
    repository.claim_next_job.return_value = job
    repository.get_job.return_value = job

    def slow_handler(_job: JobRecord) -> dict[str, str]:
        time.sleep(0.05)
        return {"model_id": "m1"}

    worker = ProcessJobWorker(
        repository,
        handlers={"fit_mmm": slow_handler},
        worker_id="worker-a",
        lease_seconds=3,
        heartbeat_repository=heartbeat_repository,
        heartbeat_interval=0.01,
    )
    assert worker.execute_next_job() is True
    heartbeat_repository.renew_lease.assert_called()


def test_production_profile_composes_enqueue_only_api(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        ingest_dir=tmp_path / "inbox",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
        oauth_issuer="https://issuer.example.com/",
        oauth_audience="pymc-marketing-mcp",
    )

    persistence = SQLitePersistenceBackend(tmp_path / "test-persistence.db")
    app = Application(settings, persistence=persistence)
    try:
        assert settings.job_execution_mode == "enqueue-only"
        assert isinstance(app.jobs.executor, EnqueueOnlyJobExecutor)
    finally:
        persistence.close()
