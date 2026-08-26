"""Asynchronous jobs MCP tools (Wave 5 Task 5)."""

from __future__ import annotations

import asyncio
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobStatus
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.policy import require_scope, scopes_for_tool


def register_jobs_tools(mcp, app: Application, context_provider=None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="submit_fit_mmm_job",
        description="Submit an asynchronous MMM fitting job that executes in the background without blocking.",
    )
    async def submit_fit_mmm_job(config: FitMMMInput, idempotency_key: str | None = None):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("submit_fit_mmm_job")[0])

            async def _fit_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
                loop = asyncio.get_running_loop()
                # Run CPU-bound PyMC fit in executor thread
                res = await loop.run_in_executor(None, app.models.fit, config)
                return res.model_dump()

            job_rec = app.jobs.submit_job(
                job_type="fit_mmm",
                payload=config.model_dump(),
                runner_fn=_fit_runner,
                principal=principal,
                idempotency_key=idempotency_key,
            )
            return env(
                summary=job_rec.to_dict(),
                next_actions=["get_job_status"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="get_job_status",
        description="Retrieve the execution status, results, or error details of an asynchronous job.",
    )
    async def get_job_status(job_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("get_job_status")[0])
            record = app.jobs.get_job(job_id, principal=principal)
            next_acts = []
            if record.status == JobStatus.SUCCEEDED:
                next_acts = ["diagnose_mmm", "get_model_status"]
            elif record.status == JobStatus.RUNNING:
                next_acts = ["get_job_status", "cancel_job"]
            return env(
                summary=record.to_dict(),
                next_actions=next_acts,
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="cancel_job",
        description="Cancel a currently queued or running background job.",
    )
    async def cancel_job(job_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("cancel_job")[0])
            cancelled = app.jobs.cancel_job(job_id, principal=principal)
            return env(summary=cancelled.to_dict())
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="list_jobs",
        description="List recent asynchronous background jobs for the active tenant.",
    )
    async def list_jobs(status: str | None = None, limit: int = 50):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("list_jobs")[0])
            job_status = JobStatus(status) if status else None
            records = app.jobs.list_jobs(principal=principal, status=job_status, limit=limit)
            return env(summary={"jobs": [r.to_dict() for r in records], "count": len(records)})
        except DomainError as e:
            return e.to_dict()
