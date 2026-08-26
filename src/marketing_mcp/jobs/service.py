"""Job coordination service with tenant authorization and idempotency handling."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from marketing_mcp.jobs.executor import AsyncioJobExecutor, JobExecutor
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import JobRepository
from marketing_mcp.security.ownership import authorize_job
from marketing_mcp.security.principal import Principal


class JobService:
    """Service layer for job lifecycle management."""

    def __init__(self, repo: JobRepository, executor: JobExecutor | None = None):
        self.repo = repo
        self.executor = executor or AsyncioJobExecutor(repo)

    def submit_job(
        self,
        job_type: str,
        payload: dict[str, Any],
        runner_fn: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        principal: Principal | None = None,
        idempotency_key: str | None = None,
    ) -> JobRecord:
        tenant_id = principal.tenant_id if principal else None
        owner = principal.subject if principal else "local"

        # Check idempotency
        if idempotency_key:
            existing = self.repo.find_by_idempotency_key(idempotency_key, tenant_id=tenant_id)
            if existing:
                return existing

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        record = JobRecord(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            owner=owner,
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            payload=payload,
        )
        created = self.repo.create_job(record)
        self.executor.submit(created, runner_fn)
        return created

    def get_job(self, job_id: str, principal: Principal | None = None) -> JobRecord:
        record = self.repo.get_job(job_id)
        authorize_job(principal, record.to_dict(), action="read")
        return record

    def cancel_job(self, job_id: str, principal: Principal | None = None) -> JobRecord:
        record = self.repo.get_job(job_id)
        authorize_job(principal, record.to_dict(), action="write")
        self.executor.cancel(job_id)
        return self.repo.update_job(job_id, JobStatus.CANCELLED)

    def list_jobs(
        self, principal: Principal | None = None, status: JobStatus | None = None, limit: int = 50
    ) -> list[JobRecord]:
        tenant_id = principal.tenant_id if principal and principal.auth_type != "stdio" else None
        return self.repo.list_jobs(tenant_id=tenant_id, status=status, limit=limit)
