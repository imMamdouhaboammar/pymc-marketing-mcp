"""Asynchronous jobs MCP tools (Wave 5 Task 5)."""

from __future__ import annotations

import asyncio
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
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
    @mcp_error_boundary("submit_fit_mmm_job", "jobs", "submission")
    async def submit_fit_mmm_job(config: FitMMMInput, idempotency_key: str | None = None):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_fit_mmm_job")[0])

        payload_dict = config.model_dump()
        import json

        from marketing_mcp.accelerators import fast_admit_job

        payload_bytes_len = len(json.dumps(payload_dict).encode("utf-8"))
        tenant_id = principal.tenant_id if principal else None
        adm = fast_admit_job(payload_bytes_len, max_size=50 * 1024 * 1024, tenant_id=tenant_id)
        if not adm.get("admitted"):
            err = adm.get("error") or {}
            raise DomainError(
                err.get("code", "PAYLOAD_TOO_LARGE"),
                err.get("message", "Job payload exceeds limit"),
            )

        async def _fit_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "dataset_validated", progress_percent=15.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "sampling_initialized", progress_percent=30.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            # Run CPU-bound PyMC fit in executor thread
            res = await loop.run_in_executor(None, app.models.fit, config, principal)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res_dict = res.model_dump()
            app.jobs.record_checkpoint(
                job.job_id,
                "posterior_saved",
                progress_percent=90.0,
                state_data={"model_id": res.model_id, "result": res_dict},
            )
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(
                job.job_id,
                "diagnostics_completed",
                progress_percent=100.0,
                state_data={"model_id": res.model_id, "result": res_dict},
            )
            return res_dict

        job_rec = app.jobs.submit_job(
            job_type="fit_mmm",
            payload=payload_dict,
            runner_fn=_fit_runner,
            principal=principal,
            idempotency_key=idempotency_key,
        )
        return env(
            summary=job_rec.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="get_job_status",
        description="Retrieve the execution status, results, or error details of an asynchronous job.",
    )
    @mcp_error_boundary("get_job_status", "jobs", "monitoring")
    async def get_job_status(job_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("get_job_status")[0])
        record = app.jobs.get_job(job_id, principal=principal)
        next_acts = []
        if record.status == JobStatus.SUCCEEDED:
            next_acts = ["diagnose_mmm", "get_model_status", "export_artifact_to_sandbox"]
        elif record.status == JobStatus.RUNNING:
            next_acts = ["poll_job_progress", "get_job_status", "cancel_job"]
        return env(
            summary=record.to_dict(),
            next_actions=next_acts,
        )

    @mcp.tool(
        name="poll_job_progress",
        description="Non-blocking heartbeat poll waiting up to timeout_seconds for progress to avoid AI client timeout collapses.",
    )
    @mcp_error_boundary("poll_job_progress", "jobs", "monitoring")
    async def poll_job_progress(job_id: str, timeout_seconds: int = 25):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("poll_job_progress")[0])
        poll_result = await app.jobs.poll_job(
            job_id, timeout_seconds=timeout_seconds, principal=principal
        )
        next_acts = []
        if poll_result["is_terminal"]:
            next_acts = ["diagnose_mmm", "get_model_status", "export_artifact_to_sandbox"]
        else:
            next_acts = ["poll_job_progress", "cancel_job"]
        return env(summary=poll_result, next_actions=next_acts)

    @mcp.tool(
        name="recover_execution_state",
        description="Recover execution state and intermediate checkpoints after an unexpected disconnect or restart.",
    )
    @mcp_error_boundary("recover_execution_state", "jobs", "recovery")
    async def recover_execution_state(job_id_or_key: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("recover_execution_state")[0])
        rec_state = app.jobs.recover_job_state(job_id_or_key, principal=principal)
        next_acts = [rec_state["recommended_action"]]
        return env(summary=rec_state, next_actions=next_acts)

    @mcp.tool(
        name="resume_job",
        description="Resume an interrupted or failed job from its last valid checkpoint without repeating completed work.",
    )
    @mcp_error_boundary("resume_job", "jobs", "recovery")
    async def resume_job(job_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("resume_job")[0])
        rec = app.jobs.get_job(job_id, principal=principal)
        config = FitMMMInput(**rec.payload)

        async def _resume_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "sampling_initialized", progress_percent=30.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res = await loop.run_in_executor(None, app.models.fit, config, principal)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res_dict = res.model_dump()
            app.jobs.record_checkpoint(
                job.job_id,
                "posterior_saved",
                progress_percent=90.0,
                state_data={"model_id": res.model_id, "result": res_dict},
            )
            return res_dict

        resumed = app.jobs.resume_job(job_id, _resume_runner, principal=principal)
        return env(
            summary=resumed.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="cancel_job",
        description="Cancel a currently queued or running background job.",
    )
    @mcp_error_boundary("cancel_job", "jobs", "lifecycle")
    async def cancel_job(job_id: str):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("cancel_job")[0])
        from marketing_mcp.accelerators import fast_acknowledge_cancellation

        ack = fast_acknowledge_cancellation(job_id, in_process=True)
        if not ack.get("acknowledged"):
            err = ack.get("error") or {}
            raise DomainError(
                err.get("code", "INVALID_JOB_ID"),
                err.get("message", "Invalid job id"),
            )

        cancelled = app.jobs.cancel_job(job_id, principal=principal)
        summary_dict = cancelled.to_dict()
        summary_dict["fence_triggered"] = ack.get("fence_triggered", True)
        return env(summary=summary_dict)

    @mcp.tool(
        name="list_jobs",
        description="List recent asynchronous background jobs for the active tenant.",
    )
    @mcp_error_boundary("list_jobs", "jobs", "monitoring")
    async def list_jobs(status: str | None = None, limit: int = 50):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("list_jobs")[0])
        job_status = None
        if status:
            try:
                job_status = JobStatus(status.lower())
            except ValueError:
                valid_statuses = [s.value for s in JobStatus]
                raise DomainError(
                    "INPUT_INVALID",
                    f"Invalid job status '{status}'. Allowed: {', '.join(valid_statuses)}",
                    evidence={"status": status, "allowed": valid_statuses},
                    next_action="Provide a supported job status",
                )
        records = app.jobs.list_jobs(principal=principal, status=job_status, limit=limit)
        return env(summary={"jobs": [r.to_dict() for r in records], "count": len(records)})
