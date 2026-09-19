"""Job coordination service with tenant authorization and idempotency handling."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.executor import AsyncioJobExecutor, JobExecutor
from marketing_mcp.jobs.models import JobCheckpoint, JobRecord, JobStatus
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

    def record_checkpoint(
        self,
        job_id: str,
        stage: str,
        progress_percent: float = 0.0,
        step: int = 0,
        total_steps: int = 1,
        state_data: dict[str, Any] | None = None,
    ) -> JobCheckpoint:
        cp = JobCheckpoint(
            checkpoint_id=f"cp-{uuid.uuid4().hex[:10]}",
            job_id=job_id,
            stage=stage,
            step=step,
            total_steps=total_steps,
            progress_percent=progress_percent,
            state_data=state_data or {},
        )
        self.repo.save_checkpoint(cp)
        return cp

    def get_checkpoints(
        self, job_id: str, principal: Principal | None = None
    ) -> list[JobCheckpoint]:
        self.get_job(job_id, principal=principal)
        return self.repo.get_checkpoints(job_id)

    def get_latest_checkpoint(
        self, job_id: str, principal: Principal | None = None
    ) -> JobCheckpoint | None:
        self.get_job(job_id, principal=principal)
        return self.repo.get_latest_checkpoint(job_id)

    async def poll_job(
        self,
        job_id: str,
        timeout_seconds: int = 25,
        poll_interval: float = 1.0,
        principal: Principal | None = None,
    ) -> dict[str, Any]:
        """Poll job status with timeout to prevent AI client call collapse."""
        import asyncio
        import time

        start_time = time.monotonic()
        safe_timeout = max(1, min(timeout_seconds, 60))

        while True:
            job = self.get_job(job_id, principal=principal)
            latest_cp = self.repo.get_latest_checkpoint(job_id)
            elapsed = time.monotonic() - start_time

            if job.status.is_terminal or elapsed >= safe_timeout:
                return {
                    "job": job.to_dict(),
                    "latest_checkpoint": latest_cp.to_dict() if latest_cp else None,
                    "is_terminal": job.status.is_terminal,
                    "elapsed_seconds": round(elapsed, 2),
                    "timed_out": not job.status.is_terminal and elapsed >= safe_timeout,
                }
            await asyncio.sleep(poll_interval)

    def recover_job_state(
        self,
        job_id_or_key: str,
        principal: Principal | None = None,
    ) -> dict[str, Any]:
        """Recover full execution context from an interrupted or existing job."""
        tenant_id = principal.tenant_id if principal else None
        job: JobRecord | None = None
        try:
            job = self.get_job(job_id_or_key, principal=principal)
        except DomainError as exc:
            if exc.code != "JOB_NOT_FOUND":
                raise
            job = self.repo.find_by_idempotency_key(job_id_or_key, tenant_id=tenant_id)
            if job:
                authorize_job(principal, job.to_dict(), action="read")

        if not job:
            raise DomainError(
                "JOB_NOT_FOUND", f"Job or idempotency key '{job_id_or_key}' was not found"
            )

        checkpoints = self.repo.get_checkpoints(job.job_id)
        latest_cp = checkpoints[-1] if checkpoints else None

        can_resume = job.status in (JobStatus.FAILED, JobStatus.CANCELLED) and bool(checkpoints)
        has_usable_result = job.status == JobStatus.SUCCEEDED or bool(
            latest_cp
            and latest_cp.stage
            in (
                "posterior_saved",
                "fit_completed",
                "diagnostics_completed",
                "optimization_completed",
                "cv_completed",
                "sensitivity_completed",
                "transformation_completed",
            )
        )

        recommended_action = "poll_job_progress"
        if has_usable_result:
            if job.job_type in ("fit_mmm", "mmm.fit"):
                recommended_action = "diagnose_mmm"
            elif job.job_type in ("cross_validate_mmm", "mmm.cross_validate"):
                recommended_action = "diagnose_mmm"
            elif job.job_type in ("prior_sensitivity", "mmm.prior_sensitivity"):
                recommended_action = "recommend_next_measurement"
            elif job.job_type in (
                "budget_optimize",
                "mmm.budget_optimize",
                "flighting_optimize",
                "mmm.flighting_optimize",
            ):
                recommended_action = "simulate_budget"
            elif job.job_type in ("transform_ad_export", "dataset.transform_ad_export"):
                recommended_action = "inspect_dataset"
            else:
                recommended_action = "get_model_status"
        elif can_resume:
            recommended_action = "resume_job"

        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "can_resume": can_resume,
            "has_usable_result": has_usable_result,
            "checkpoint_count": len(checkpoints),
            "latest_checkpoint": latest_cp.to_dict() if latest_cp else None,
            "result": job.result,
            "error": job.error,
            "recommended_action": recommended_action,
        }

    def resume_job(
        self,
        job_id: str,
        runner_fn: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        principal: Principal | None = None,
    ) -> JobRecord:
        """Resume an interrupted or failed job from its last recorded checkpoint."""
        job = self.get_job(job_id, principal=principal)
        authorize_job(principal, job.to_dict(), action="write")

        if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.QUEUED):
            raise DomainError(
                "INVALID_STATE",
                f"Job '{job_id}' is in state '{job.status.value}' and cannot be resumed",
            )

        updated = self.repo.update_job(job_id, JobStatus.QUEUED, error=None)
        self.record_checkpoint(
            job_id,
            stage="resumed",
            progress_percent=0.0,
            state_data={"previous_status": job.status.value},
        )
        self.executor.submit(updated, runner_fn)
        return updated

    def cancel_job(self, job_id: str, principal: Principal | None = None) -> JobRecord:
        record = self.repo.get_job(job_id)
        authorize_job(principal, record.to_dict(), action="write")
        if record.status in (JobStatus.CANCELLED, JobStatus.SUCCEEDED, JobStatus.FAILED):
            return record
        self.executor.cancel(job_id)
        # Cancellation is cooperative. Running work remains CANCELLING until
        # its runner returns to Python, observes the event, and fences the result.
        return self.repo.request_cancellation(job_id)

    def list_jobs(
        self, principal: Principal | None = None, status: JobStatus | None = None, limit: int = 50
    ) -> list[JobRecord]:
        tenant_id = principal.tenant_id if principal and principal.auth_type != "stdio" else None
        return self.repo.list_jobs(tenant_id=tenant_id, status=status, limit=limit)
