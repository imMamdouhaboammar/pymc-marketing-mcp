"""Unit tests for resume_job checkpoint result reuse and retry semantics."""

from __future__ import annotations

import asyncio
import sqlite3
import pytest

from marketing_mcp.errors import DomainError
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
