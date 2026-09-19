"""Unit tests for Job State Machine, Repository, and Executor (Wave 5 Task 3)."""

from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.executor import AsyncioJobExecutor
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.service import JobService
from marketing_mcp.jobs.state import can_transition, validate_transition
from marketing_mcp.security.principal import Principal
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
        # FAILED → RUNNING is never allowed (jobs must re-queue first)
        assert not can_transition(JobStatus.FAILED, JobStatus.RUNNING)
        with pytest.raises(DomainError) as exc:
            validate_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert exc.value.code == "INVALID_STATE"
        # FAILED → QUEUED and FAILED → SUCCEEDED are valid for resume_job checkpoint reuse
        assert can_transition(JobStatus.FAILED, JobStatus.QUEUED)
        assert can_transition(JobStatus.FAILED, JobStatus.SUCCEEDED)


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
            await cancel_event.wait()
            raise asyncio.CancelledError()

        job = service.submit_job("fit_mmm", {}, slow_worker)
        await asyncio.sleep(0.01)
        requested = service.cancel_job(job.job_id)
        assert requested.status == JobStatus.CANCELLING

        # The cooperative worker observes the cancellation event before the
        # executor records the terminal state.
        await asyncio.sleep(0)
        cancelled = service.get_job(job.job_id)
        assert cancelled.status == JobStatus.CANCELLED

    @pytest.mark.anyio
    async def test_cpu_job_stays_cancelling_until_thread_returns(self, job_repo):
        executor = AsyncioJobExecutor(job_repo)
        service = JobService(job_repo, executor)
        started = threading.Event()
        release = threading.Event()

        async def cpu_worker(job, cancel_event):
            loop = asyncio.get_running_loop()

            def blocking_work():
                started.set()
                release.wait(timeout=2)

            await loop.run_in_executor(None, blocking_work)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            return {"done": True}

        job = service.submit_job("fit_mmm", {}, cpu_worker)
        assert await asyncio.to_thread(started.wait, 1)
        requested = service.cancel_job(job.job_id)
        assert requested.status == JobStatus.CANCELLING

        await asyncio.sleep(0)
        assert service.get_job(job.job_id).status == JobStatus.CANCELLING

        release.set()
        for _ in range(20):
            await asyncio.sleep(0.01)
            if service.get_job(job.job_id).status == JobStatus.CANCELLED:
                break
        assert service.get_job(job.job_id).status == JobStatus.CANCELLED

    def test_idempotency_key_returns_existing_job(self, job_repo):
        service = JobService(job_repo)

        async def dummy_worker(job, cancel_event):
            return {}

        job1 = service.submit_job("fit", {}, dummy_worker, idempotency_key="fit-request-abc")
        job2 = service.submit_job("fit", {}, dummy_worker, idempotency_key="fit-request-abc")
        assert job1.job_id == job2.job_id

    def test_recover_job_state_does_not_mask_authorization_errors(self, job_repo):
        record = JobRecord(
            job_id="job-private",
            job_type="fit_mmm",
            owner="owner-a",
            tenant_id="tenant-a",
        )
        job_repo.create_job(record)
        principal = Principal(
            subject="owner-b",
            auth_type="api_key",
            scopes=frozenset({"marketing:read"}),
            tenant_id="tenant-b",
        )

        with pytest.raises(DomainError) as exc:
            JobService(job_repo).recover_job_state("job-private", principal=principal)

        assert exc.value.code == "AUTH_FORBIDDEN"

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
