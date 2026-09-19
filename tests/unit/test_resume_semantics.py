"""Unit tests for resume_job checkpoint result reuse and retry semantics."""

from __future__ import annotations

import sqlite3

import pytest

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.service import JobService
from marketing_mcp.security.principal import Principal
from marketing_mcp.storage.migrations import MigrationRunner


@pytest.fixture
def job_service():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    MigrationRunner(conn).apply_pending()
    repo = SQLiteJobRepository(conn)
    return JobService(repo)


def test_resume_job_reuses_checkpoint_result_without_runner(job_service):
    principal = Principal(
        subject="analyst",
        tenant_id="tenant_a",
        scopes=frozenset({"marketing:model"}),
        auth_type="api_key",
    )
    job = job_service.repo.create_job(
        JobRecord(
            job_id="job-checkpoint-reuse",
            job_type="fit_mmm",
            owner="analyst",
            tenant_id="tenant_a",
            payload={"dataset_id": "ds_1"},
            status=JobStatus.FAILED,
            error={"code": "TIMEOUT"},
        )
    )

    # Record checkpoint that reached computation completion with result
    expected_result = {"model_id": "mmm_reused", "status": "completed"}
    job_service.record_checkpoint(
        job.job_id,
        stage="fit_completed",
        progress_percent=100.0,
        state_data={"model_id": "mmm_reused", "result": expected_result},
    )

    runner_called = False

    async def dummy_runner(j, cancel_event):
        nonlocal runner_called
        runner_called = True
        return {"model_id": "mmm_wrong"}

    resumed = job_service.resume_job(job.job_id, dummy_runner, principal=principal)

    assert runner_called is False
    assert resumed.status == JobStatus.SUCCEEDED
    assert resumed.result == expected_result
    assert resumed.error is None

    # Verify latest checkpoint indicates result reuse
    latest_cp = job_service.repo.get_latest_checkpoint(job.job_id)
    assert latest_cp is not None
    assert latest_cp.stage == "resumed_from_checkpoint"
    assert latest_cp.progress_percent == 100.0


def test_resume_job_restarts_stage_when_no_checkpoint_result(job_service):
    principal = Principal(
        subject="analyst",
        tenant_id="tenant_a",
        scopes=frozenset({"marketing:model"}),
        auth_type="api_key",
    )
    job = job_service.repo.create_job(
        JobRecord(
            job_id="job-restart-stage",
            job_type="fit_mmm",
            owner="analyst",
            tenant_id="tenant_a",
            payload={"dataset_id": "ds_1"},
            status=JobStatus.FAILED,
            error={"code": "SAMPLING_ERROR"},
        )
    )

    # Intermediate checkpoint without result
    job_service.record_checkpoint(
        job.job_id,
        stage="sampling_initialized",
        progress_percent=30.0,
        state_data={"step": "tune"},
    )

    runner_submitted = False

    async def mock_runner(j, cancel_event):
        nonlocal runner_submitted
        runner_submitted = True
        return {"model_id": "mmm_new"}

    resumed = job_service.resume_job(job.job_id, mock_runner, principal=principal)

    # Since there was no checkpoint result, job is QUEUED and runner is submitted
    assert resumed.status == JobStatus.QUEUED
    checkpoints = job_service.repo.get_checkpoints(job.job_id)
    stages = [cp.stage for cp in checkpoints]
    assert "resumed" in stages


def test_expired_leased_job_recovers_as_succeeded_when_terminal_checkpoint_exists(job_service):
    """P1 Item 1: A process worker writes a terminal completed checkpoint then dies before finish_claim.
    When lease expires, recover_stale_running_jobs must mark it SUCCEEDED from the checkpoint,
    not requeue or fail it.
    """
    job = job_service.repo.create_job(
        JobRecord(
            job_id="job-leased-crashed-worker",
            job_type="fit_mmm",
            owner="analyst",
            tenant_id="tenant_a",
            payload={"dataset_id": "ds_1"},
            status=JobStatus.QUEUED,
            max_attempts=3,
        )
    )

    # Worker claims the job with a 1-second lease
    claimed = job_service.repo.claim_next_job(
        tenant_id="tenant_a",
        worker_id="worker-crashed",
        lease_seconds=1,
    )
    assert claimed is not None
    assert claimed.job_id == job.job_id
    assert claimed.status == JobStatus.RUNNING

    # Worker records terminal completed checkpoint
    expected_result = {"model_id": "mmm_crashed_worker_recovered", "r_hat": 1.01}
    job_service.record_checkpoint(
        job.job_id,
        stage="fit_completed",
        progress_percent=100.0,
        state_data={"result": expected_result},
    )

    # Worker dies without calling finish_claim. Advance clock so lease expires.
    import time
    time.sleep(1.1)

    # Recovery runs
    recovered_count = job_service.repo.recover_stale_running_jobs()
    assert recovered_count >= 1

    # Job must now be SUCCEEDED with restored result, NOT requeued
    recovered_job = job_service.repo.get_job(job.job_id)
    assert recovered_job.status == JobStatus.SUCCEEDED
    assert recovered_job.result == expected_result
    assert recovered_job.error is None
    assert recovered_job.lease_owner is None
    assert recovered_job.lease_expires_at is None


def test_resume_job_exhausted_attempts_allows_claim_next_job(job_service):
    """P1 Item 2: Explicit resume treats the job as a new execution generation,
    resetting the claimable attempt budget so an attempt-exhausted failed job can run again.
    """
    principal = Principal(
        subject="analyst",
        tenant_id="tenant_a",
        scopes=frozenset({"marketing:model"}),
        auth_type="api_key",
    )
    job = job_service.repo.create_job(
        JobRecord(
            job_id="job-exhausted-attempts",
            job_type="fit_mmm",
            owner="analyst",
            tenant_id="tenant_a",
            payload={"dataset_id": "ds_1"},
            status=JobStatus.FAILED,
            attempts=3,
            max_attempts=3,
            error={"code": "MAX_ATTEMPTS_EXCEEDED"},
        )
    )

    # Before resume: claim_next_job cannot claim this job because attempts == max_attempts
    claimed_before = job_service.repo.claim_next_job(tenant_id="tenant_a")
    assert claimed_before is None

    # User explicitly calls resume_job without a runner (e.g. for standalone worker pickup)
    resumed = job_service.resume_job(job.job_id, runner_fn=None, principal=principal)
    assert resumed.status == JobStatus.QUEUED

    # Now claim_next_job CAN claim it because attempts budget was reset for explicit resume
    claimed_after = job_service.repo.claim_next_job(tenant_id="tenant_a", worker_id="worker-resumed")
    assert claimed_after is not None
    assert claimed_after.job_id == job.job_id
    assert claimed_after.attempts == 1

