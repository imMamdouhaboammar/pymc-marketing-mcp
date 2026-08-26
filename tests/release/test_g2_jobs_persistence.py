"""Gate G2 Release Tests: Jobs, Persistence, and Crash Recovery (Wave 5).

Verifies:
- Long-running statistical workflows can be submitted as async background jobs
- Jobs transition through valid state machine (queued -> running -> succeeded / cancelled / failed)
- Jobs survive application restart (persistence in database)
- Stalled jobs from unexpected worker exit are recovered cleanly on restart
- Idempotency keys prevent duplicate background job submissions
- Multi-tenant isolation is enforced on job access
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.principal import Principal


def _app(tmp_path):
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )


class TestGateG2JobsPersistence:
    @pytest.mark.anyio
    async def test_job_submission_execution_and_persistence(self, tmp_path):
        app = _app(tmp_path)
        # Mock models.fit to avoid full MCMC sampling in fast unit test
        mock_summary = MagicMock()
        mock_summary.model_dump.return_value = {"model_id": "mmm-async-1", "converged": True}
        app.models.fit = MagicMock(return_value=mock_summary)

        config = FitMMMInput(
            dataset_id="d1",
            date_column="date",
            target_column="sales",
            channel_columns=["meta"],
        )

        async def _fit_runner(job, cancel_event):
            res = app.models.fit(config)
            return res.model_dump()

        principal = Principal(subject="data_scientist", auth_type="oauth", tenant_id="tenant_x")
        job = app.jobs.submit_job("fit_mmm", config.model_dump(), _fit_runner, principal=principal)
        assert job.status == JobStatus.QUEUED
        assert job.tenant_id == "tenant_x"

        # Wait for worker task to complete
        await asyncio.sleep(0.05)

        done_job = app.jobs.get_job(job.job_id, principal=principal)
        assert done_job.status == JobStatus.SUCCEEDED
        assert done_job.result == {"model_id": "mmm-async-1", "converged": True}

        # Verify state persisted when reopening application from same SQLite DB
        app.metadata.close()
        app_reopened = _app(tmp_path)
        persisted_job = app_reopened.jobs.get_job(job.job_id, principal=principal)
        assert persisted_job.status == JobStatus.SUCCEEDED
        assert persisted_job.result == {"model_id": "mmm-async-1", "converged": True}
        app_reopened.metadata.close()

    def test_idempotency_prevents_duplicate_submissions(self, tmp_path):
        app = _app(tmp_path)

        async def dummy_runner(job, cancel_event):
            return {}

        principal = Principal(subject="analyst", auth_type="oauth", tenant_id="t1")
        j1 = app.jobs.submit_job("fit", {}, dummy_runner, principal=principal, idempotency_key="idemp-1")
        j2 = app.jobs.submit_job("fit", {}, dummy_runner, principal=principal, idempotency_key="idemp-1")
        assert j1.job_id == j2.job_id
        app.metadata.close()

    def test_cross_tenant_job_access_blocked(self, tmp_path):
        app = _app(tmp_path)

        async def dummy_runner(job, cancel_event):
            return {}

        p_owner = Principal(subject="u1", auth_type="oauth", tenant_id="tenant_alpha")
        p_attacker = Principal(subject="u2", auth_type="oauth", tenant_id="tenant_beta")

        job = app.jobs.submit_job("fit", {}, dummy_runner, principal=p_owner)

        # Owner can read and list
        assert app.jobs.get_job(job.job_id, principal=p_owner).job_id == job.job_id
        jobs_list = app.jobs.list_jobs(principal=p_owner)
        assert len(jobs_list) >= 1

        # Attacker from another tenant is forbidden
        with pytest.raises(DomainError) as exc:
            app.jobs.get_job(job.job_id, principal=p_attacker)
        assert exc.value.code == "AUTH_FORBIDDEN"
        app.metadata.close()

    def test_crash_recovery_resets_interrupted_jobs_on_boot(self, tmp_path):
        app = _app(tmp_path)
        # Directly insert a stalled running job into SQLite
        record = JobRecord(
            job_id="job-interrupted",
            job_type="fit_mmm",
            status=JobStatus.RUNNING,
            owner="local",
        )
        app.job_repo.create_job(record)
        app.metadata.close()

        # Reopen app - crash recovery runs in __init__
        reopened_app = _app(tmp_path)
        recovered = reopened_app.jobs.get_job("job-interrupted")
        assert recovered.status == JobStatus.FAILED
        assert recovered.error["code"] == "WORKER_CRASHED"
        reopened_app.metadata.close()
