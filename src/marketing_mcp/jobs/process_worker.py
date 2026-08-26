"""Process-isolated background job worker execution."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class ProcessJobWorker:
    """Worker engine capable of executing jobs with isolation."""

    def __init__(
        self,
        repository: JobRepository,
        handlers: dict[str, Callable[[JobRecord], dict[str, Any]]] | None = None,
    ):
        self.repository = repository
        self.handlers = handlers or {}

    def register_handler(self, job_type: str, handler: Callable[[JobRecord], dict[str, Any]]) -> None:
        self.handlers[job_type] = handler

    def execute_next_job(self, tenant_id: str | None = None) -> bool:
        """Fetch and execute the oldest queued job. Returns True if a job was executed."""
        queued_jobs = self.repository.list_jobs(tenant_id=tenant_id, status=JobStatus.QUEUED, limit=1)
        if not queued_jobs:
            return False

        job = queued_jobs[0]
        handler = self.handlers.get(job.job_type)
        if not handler:
            self.repository.update_job(
                job.job_id,
                JobStatus.FAILED,
                error={"code": "NO_HANDLER", "message": f"No handler registered for job type '{job.job_type}'"},
            )
            return True

        try:
            self.repository.update_job(job.job_id, JobStatus.RUNNING)
            result = handler(job)
            self.repository.update_job(job.job_id, JobStatus.SUCCEEDED, result=result)
        except Exception as e:
            logger.exception("Worker execution failed for job %s", job.job_id)
            self.repository.update_job(
                job.job_id,
                JobStatus.FAILED,
                error={"code": "WORKER_EXECUTION_FAILED", "message": str(e)},
            )

        return True


__all__ = ["ProcessJobWorker"]
