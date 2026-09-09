"""Process-isolated background job worker execution."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from threading import Event, Thread
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class ProcessJobWorker:
    """Execute queued jobs through leased, fenced repository claims."""

    def __init__(
        self,
        repository: JobRepository,
        handlers: dict[str, Callable[[JobRecord], dict[str, Any]]] | None = None,
        *,
        worker_id: str | None = None,
        lease_seconds: int = 60,
        heartbeat_repository: JobRepository | None = None,
        heartbeat_interval: float | None = None,
    ):
        self.repository = repository
        self.handlers = handlers or {}
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:12]}"
        self.lease_seconds = lease_seconds
        self.heartbeat_repository = heartbeat_repository
        self.heartbeat_interval = heartbeat_interval or max(1.0, lease_seconds / 3)

    def register_handler(self, job_type: str, handler: Callable[[JobRecord], dict[str, Any]]) -> None:
        self.handlers[job_type] = handler

    def _finish(
        self,
        job: JobRecord,
        status: JobStatus,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> JobRecord:
        return self.repository.finish_claim(
            job.job_id,
            worker_id=self.worker_id,
            fence_token=job.fence_token,
            status=status,
            result=result,
            error=error,
        )

    def _start_heartbeat(self, job: JobRecord) -> tuple[Event, Event, Thread | None]:
        stop = Event()
        lost = Event()
        heartbeat_repository = self.heartbeat_repository
        if heartbeat_repository is None:
            return stop, lost, None

        def heartbeat() -> None:
            while not stop.wait(self.heartbeat_interval):
                try:
                    renewed = heartbeat_repository.renew_lease(
                        job.job_id,
                        worker_id=self.worker_id,
                        fence_token=job.fence_token,
                        lease_seconds=self.lease_seconds,
                    )
                except Exception:
                    logger.exception("Lease heartbeat failed for job %s", job.job_id)
                    lost.set()
                    return
                if not renewed:
                    lost.set()
                    return

        thread = Thread(target=heartbeat, name=f"heartbeat-{job.job_id}", daemon=True)
        thread.start()
        return stop, lost, thread

    @staticmethod
    def _stop_heartbeat(stop: Event, thread: Thread | None) -> None:
        stop.set()
        if thread is not None:
            thread.join()

    def execute_next_job(self, tenant_id: str | None = None) -> bool:
        """Claim and execute the oldest eligible job; return whether one was claimed."""
        job = self.repository.claim_next_job(
            tenant_id=tenant_id,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False
        handler = self.handlers.get(job.job_type)
        if not handler:
            self._finish(
                job,
                JobStatus.FAILED,
                error={
                    "code": "NO_HANDLER",
                    "message": f"No handler registered for job type '{job.job_type}'",
                },
            )
            return True

        stop, lease_lost, heartbeat = self._start_heartbeat(job)
        try:
            result = handler(job)
        except Exception as exc:
            self._stop_heartbeat(stop, heartbeat)
            logger.exception("Worker execution failed for job %s", job.job_id)
            try:
                current = self.repository.get_job(job.job_id)
                if current.status is JobStatus.CANCELLING:
                    self._finish(job, JobStatus.CANCELLED)
                elif not lease_lost.is_set():
                    self._finish(
                        job,
                        JobStatus.FAILED,
                        error={"code": "WORKER_EXECUTION_FAILED", "message": str(exc)},
                    )
            except DomainError as stale:
                logger.warning("Worker result discarded for %s: %s", job.job_id, stale)
            return True

        self._stop_heartbeat(stop, heartbeat)
        if lease_lost.is_set():
            logger.warning("Worker result discarded for %s after lease loss", job.job_id)
            return True
        try:
            current = self.repository.get_job(job.job_id)
            if current.status is JobStatus.CANCELLING:
                self._finish(job, JobStatus.CANCELLED)
            else:
                self._finish(job, JobStatus.SUCCEEDED, result=result)
        except DomainError as stale:
            logger.warning("Worker result discarded for %s: %s", job.job_id, stale)
        return True


__all__ = ["ProcessJobWorker"]
