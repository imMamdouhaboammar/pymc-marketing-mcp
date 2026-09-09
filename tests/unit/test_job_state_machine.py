"""Unit tests for Job State Machine, Repository, and Executor (Wave 5 Task 3)."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.executor import AsyncioJobExecutor
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.service import JobService
from marketing_mcp.jobs.state import can_transition, validate_transition
from marketing_mcp.storage.migrations import MigrationRunner


@pytest.fixture
def job_repo():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    MigrationRunner(conn).apply_pending()
    return SQLiteJobRepository(conn)


class TestJobStateMachine:
    def test_valid_transitions(self):
        assert can_transition(JobStatus.QUEUED, JobStatus.RUNNING)
        assert can_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert can_transition(JobStatus.RUNNING, JobStatus.FAILED)
        assert can_transition(JobStatus.RUNNING, JobStatus.CANCELLED)

    def test_invalid_transitions_fail(self):
        assert not can_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert not can_transition(JobStatus.FAILED, JobStatus.SUCCEEDED)
        with pytest.raises(DomainError) as exc:
            validate_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert exc.value.code == "INVALID_STATE"


class TestJobRepositoryAndService:
    def test_create_and_retrieve_job(self, job_repo):
        record = JobRecord(
            job_id="job-1",
            job_type="fit_mmm",
            status=JobStatus.QUEUED,
            owner="user1",
            payload={"dataset_id": "d1"},
        )
        job_repo.create_job(record)
        retrieved = job_repo.get_job("job-1")
        assert retrieved.job_id == "job-1"
        assert retrieved.status == JobStatus.QUEUED
        assert retrieved.payload == {"dataset_id": "d1"}

    def test_update_job_status_and_result(self, job_repo):
        record = JobRecord(job_id="job-2", job_type="fit_mmm", status=JobStatus.QUEUED)
        job_repo.create_job(record)
        job_repo.update_job("job-2", JobStatus.RUNNING)
        updated = job_repo.update_job("job-2", JobStatus.SUCCEEDED, result={"model_id": "m1"})
        assert updated.status == JobStatus.SUCCEEDED
        assert updated.result == {"model_id": "m1"}

    @pytest.mark.anyio
    async def test_async_job_executor_runs_and_succeeds(self, job_repo):
        executor = AsyncioJobExecutor(job_repo)
        service = JobService(job_repo, executor)

        async def worker(job, cancel_event):
            await asyncio.sleep(0.01)
            return {"fitted": True}

        job = service.submit_job("fit_mmm", {"param": 1}, worker)
        assert job.status == JobStatus.QUEUED

        # Allow task loop to finish
        await asyncio.sleep(0.05)
        done = service.get_job(job.job_id)
        assert done.status == JobStatus.SUCCEEDED
        assert done.result == {"fitted": True}

    @pytest.mark.anyio
    async def test_async_job_cancellation(self, job_repo):
        executor = AsyncioJobExecutor(job_repo)
        service = JobService(job_repo, executor)

        async def slow_worker(job, cancel_event):
            await asyncio.sleep(1.0)
            return {"done": True}

        job = service.submit_job("fit_mmm", {}, slow_worker)
        await asyncio.sleep(0.01)
        service.cancel_job(job.job_id)
        cancelled = service.get_job(job.job_id)
        assert cancelled.status == JobStatus.CANCELLED

    def test_idempotency_key_returns_existing_job(self, job_repo):
        service = JobService(job_repo)

        async def dummy_worker(job, cancel_event):
            return {}

        job1 = service.submit_job("fit", {}, dummy_worker, idempotency_key="fit-request-abc")
        job2 = service.submit_job("fit", {}, dummy_worker, idempotency_key="fit-request-abc")
        assert job1.job_id == job2.job_id

    def test_crash_recovery_fails_only_expired_exhausted_lease(self, job_repo):
        record = JobRecord(job_id="job-crashed", job_type="fit_mmm", max_attempts=1)
        job_repo.create_job(record)
        claimed = job_repo.claim_next_job(worker_id="dead-worker", lease_seconds=60)
        assert claimed is not None
        job_repo.conn.execute(
            "UPDATE jobs SET lease_expires_at = ? WHERE job_id = ?",
            ("2000-01-01T00:00:00+00:00", claimed.job_id),
        )
        job_repo.conn.commit()

        recovered_count = job_repo.recover_stale_running_jobs()
        assert recovered_count == 1

        recovered = job_repo.get_job("job-crashed")
        assert recovered.status == JobStatus.FAILED
        assert recovered.error["code"] == "WORKER_ATTEMPTS_EXHAUSTED"
