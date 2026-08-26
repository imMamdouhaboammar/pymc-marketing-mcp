"""Gate H4: Durable Jobs, Transport-Neutral Recovery, and MCP Task Boundary.

Gate H4 contract:
1. Long-running compute is durable and recoverable across process restarts.
2. Submission is persisted before background execution starts.
3. Process-isolated workers can process queued jobs independently from API server.
4. Idempotency keys prevent duplicate background compute jobs.
5. Multi-tenant authorization prevents cross-tenant job inspection or cancellation.
6. MCP server uses compatibility job tools without falsely claiming unsupported Tasks extension.
7. Job domain layer remains strictly decoupled from transport/MCP types.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.types import StatisticalJobType
from marketing_mcp.mcp.task_adapter import UnsupportedTasksExtensionAdapter
from marketing_mcp.security.principal import Principal


@pytest.fixture
def h4_app(tmp_path: Path):
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )


@pytest.mark.anyio
async def test_h4_durable_job_lifecycle_and_restart(tmp_path: Path):
    """Test job submission, execution, and persistence across server restarts."""
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    async def _dummy_runner(job, cancel_event):
        return {"model_id": "model_async_123", "status": "completed"}

    principal = Principal(subject="scientist_1", auth_type="oauth", tenant_id="tenant_gamma")
    job = app.jobs.submit_job(
        job_type=StatisticalJobType.MMM_FIT.value,
        payload={"dataset_id": "ds_gamma", "target": "sales"},
        runner_fn=_dummy_runner,
        principal=principal,
    )

    assert job.status == JobStatus.QUEUED
    assert job.tenant_id == "tenant_gamma"

    # Wait for execution
    await asyncio.sleep(0.05)

    completed = app.jobs.get_job(job.job_id, principal=principal)
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.result == {"model_id": "model_async_123", "status": "completed"}

    # Simulate restart by reloading Application from same metadata DB
    app.metadata.close()
    restarted_app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    persisted = restarted_app.jobs.get_job(job.job_id, principal=principal)
    assert persisted.status == JobStatus.SUCCEEDED
    assert persisted.result["model_id"] == "model_async_123"
    restarted_app.metadata.close()


def test_h4_process_worker_execution(tmp_path: Path):
    """Test standalone ProcessJobWorker processing queued jobs without API loop."""
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    # Insert a queued job directly into repository
    job_record = JobRecord(
        job_id="job-worker-1",
        job_type="mmm.fit",
        status=JobStatus.QUEUED,
        owner="worker_user",
        tenant_id="tenant_1",
        payload={"dataset_id": "d1"},
    )
    app.job_repo.create_job(job_record)

    worker = ProcessJobWorker(app.job_repo)
    worker.register_handler("mmm.fit", lambda j: {"fit_done": True, "dataset": j.payload["dataset_id"]})

    # Execute one job
    did_execute = worker.execute_next_job()
    assert did_execute is True

    # Verify job status in repo
    updated = app.job_repo.get_job("job-worker-1")
    assert updated.status == JobStatus.SUCCEEDED
    assert updated.result == {"fit_done": True, "dataset": "d1"}


def test_h4_tasks_extension_safety():
    """Verify server does not falsely claim unsupported Tasks protocol extension."""
    adapter = UnsupportedTasksExtensionAdapter()
    assert adapter.supported is False
