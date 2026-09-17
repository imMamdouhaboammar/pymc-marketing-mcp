"""Asynchronous job execution engine and worker runner."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Protocol

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class JobExecutor(Protocol):
    """Protocol for executing async background jobs."""

    def submit(
        self,
        job: JobRecord,
        coro_fn: Callable[[JobRecord, asyncio.Event], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None: ...
    def cancel(self, job_id: str) -> bool: ...


class EnqueueOnlyJobExecutor:
    """Persist jobs for execution by a separate worker process."""

    def submit(
        self,
        job: JobRecord,
        coro_fn: Callable[[JobRecord, asyncio.Event], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        del job, coro_fn

    def cancel(self, job_id: str) -> bool:
        del job_id
        return False


class AsyncioJobExecutor:
    """In-process asynchronous job executor using asyncio Tasks."""

    def __init__(self, repo: JobRepository):
        self.repo = repo
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    def submit(
        self,
        job: JobRecord,
        coro_fn: Callable[[JobRecord, asyncio.Event], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        cancel_event = asyncio.Event()
        self._cancel_events[job.job_id] = cancel_event

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._run_job(job, coro_fn, cancel_event))
            self._tasks[job.job_id] = task
        except RuntimeError:
            pass

    async def _run_job(
        self,
        job: JobRecord,
        coro_fn: Callable[[JobRecord, asyncio.Event], Coroutine[Any, Any, dict[str, Any]]],
        cancel_event: asyncio.Event,
    ) -> None:
        try:
            self.repo.update_job(job.job_id, JobStatus.RUNNING)
            result = await coro_fn(job, cancel_event)
            current_job = self.repo.get_job(job.job_id)
            if cancel_event.is_set() or current_job.status in (JobStatus.CANCELLING, JobStatus.CANCELLED):
                if current_job.status != JobStatus.CANCELLED:
                    self.repo.update_job(job.job_id, JobStatus.CANCELLED)
            elif current_job.status == JobStatus.RUNNING:
                self.repo.update_job(job.job_id, JobStatus.SUCCEEDED, result=result)
        except asyncio.CancelledError:
            current_job = self.repo.get_job(job.job_id)
            if current_job.status != JobStatus.CANCELLED:
                self.repo.update_job(job.job_id, JobStatus.CANCELLED)
        except Exception as e:
            logger.exception("Job %s failed", job.job_id)
            from marketing_mcp.error_classifier import classify_exception

            norm = classify_exception(
                e,
                operation=job.job_type,
                component="jobs",
                stage="execution",
                request_id=job.job_id,
                tenant_id=job.tenant_id,
                job_id=job.job_id,
            )
            self.repo.update_job(
                job.job_id,
                JobStatus.FAILED,
                error=norm.model_dump(),
            )
        finally:
            self._tasks.pop(job.job_id, None)
            self._cancel_events.pop(job.job_id, None)

    def cancel(self, job_id: str) -> bool:
        cancel_event = self._cancel_events.get(job_id)
        task = self._tasks.get(job_id)
        if cancel_event is None or task is None or task.done():
            return False

        # Cooperative cancellation keeps the wrapper task alive while any
        # run_in_executor thread finishes. The job remains CANCELLING until the
        # runner returns to Python and observes this event, so terminal state is
        # never reported while CPU work is still active.
        cancel_event.set()
        return True
