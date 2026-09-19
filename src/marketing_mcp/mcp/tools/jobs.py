"""Asynchronous jobs MCP tools (Wave 5 Task 5)."""

from __future__ import annotations

import asyncio
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobStatus
from marketing_mcp.mcp.envelope import env
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    CrossValidateMMMInput,
    FitMMMInput,
    FlightingOptimizationInput,
    PriorSensitivityInput,
)
from marketing_mcp.security.ownership import authorize_dataset, authorize_model
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

        # Synchronously validate dataset suitability before admitting job (MMM-VAL-001)
        val_res = app.datasets.validate(
            dataset_id=config.dataset_id,
            date_column=config.date_column,
            target_column=config.target_column,
            channel_columns=config.channel_columns,
            control_columns=config.control_columns or [],
            dims=config.dims or [],
        )
        if not val_res.valid_for_modeling:
            err_findings = [f.message for f in val_res.findings if f.severity == "error"]
            raise DomainError(
                "DATASET_VALIDATION_FAILED",
                f"Dataset {config.dataset_id} validation failed for MMM fitting: {'; '.join(err_findings)}",
                evidence={"findings": [f.__dict__ for f in val_res.findings]},
                next_action="Inspect dataset columns, date format, and values using inspect_dataset or validate_dataset",
            )

        # fast_admit_job performs a cheap size/admission check and returns an interaction-level
        # `admission_id`. This is NOT the canonical job ID — the canonical job ID is created
        # exclusively by app.jobs.submit_job() below and is the persistent identifier.
        adm = fast_admit_job(payload_bytes_len, max_size=10 * 1024 * 1024, tenant_id=tenant_id)
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
                "fit_completed",
                progress_percent=100.0,
                state_data={"model_id": res.model_id, "result": res_dict},
            )
            return res_dict

        if getattr(app.settings, "platform_client_enabled", False) and hasattr(app, "platform_client"):
            from uuid import uuid4

            project_id = getattr(principal, "project_id", None) or uuid4()
            model_spec_ver_id = uuid4()
            ds_ver_id = getattr(config, "dataset_version_id", None) or uuid4()

            dispatch_res = await app.platform_client.dispatch_run(
                project_id=project_id,
                model_spec_version_id=model_spec_ver_id,
                dataset_version_id=ds_ver_id,
                requested_via="mcp",
            )
            run_rec = dispatch_res["run"]
            job_rec = dispatch_res["job"]
            return env(
                summary={
                    "job_id": str(job_rec["job_id"]),
                    "run_id": str(run_rec["run_id"]),
                    "project_id": str(run_rec["project_id"]),
                    "status": job_rec["status"],
                    "stage": job_rec.get("stage", "validating"),
                    "progress_percent": job_rec.get("progress_percent", 0),
                    "sse_topic_uri": f"/api/v1/projects/{run_rec['project_id']}/events",
                    "poll_url": f"/api/v1/runs/{run_rec['run_id']}",
                },
                next_actions=["poll_job_progress", "get_job_status"],
            )

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
        name="submit_transform_ad_export_job",
        description="Submit an asynchronous job to transform raw long-form advertising exports into wide-form modeling format without blocking.",
    )
    @mcp_error_boundary("submit_transform_ad_export_job", "jobs", "submission")
    async def submit_transform_ad_export_job(
        dataset_id: str,
        date_column: str,
        channel_column: str,
        spend_column: str,
        target_columns: list[str],
        dimension_columns: list[str] | None = None,
        frequency: str = "D",
        idempotency_key: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_transform_ad_export_job")[0])
        t_id = principal.tenant_id if principal and principal.auth_type != "stdio" else None
        dataset = app.metadata.get_dataset(dataset_id, tenant_id=t_id)
        if not dataset:
            raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
        authorize_dataset(principal, dataset, action="read")

        payload = {
            "dataset_id": dataset_id,
            "date_column": date_column,
            "channel_column": channel_column,
            "spend_column": spend_column,
            "target_columns": target_columns,
            "dimension_columns": dimension_columns,
            "frequency": frequency,
        }

        async def _transform_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "transformation_initialized", progress_percent=20.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            registered, provenance, plan = await loop.run_in_executor(
                None,
                lambda: app.datasets.transform_long_form(
                    dataset_id=dataset_id,
                    date_column=date_column,
                    channel_column=channel_column,
                    spend_column=spend_column,
                    target_columns=target_columns,
                    dimension_columns=dimension_columns,
                    frequency=frequency,
                    principal=principal,
                ),
            )
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            from dataclasses import asdict

            res_dict = {
                "transformed_dataset_id": registered.dataset_id,
                "input_dataset_id": dataset_id,
                "rows": registered.rows,
                "format": registered.format,
                "spend_reconciled": provenance.spend_reconciled,
                "spend_delta": provenance.spend_delta,
                "calendar_frequency": plan.frequency,
                "inserted_periods": provenance.inserted_periods,
                "provenance": asdict(provenance),
                "transformation_plan": asdict(plan),
            }
            app.jobs.record_checkpoint(
                job.job_id,
                "transformation_completed",
                progress_percent=100.0,
                state_data={"result": res_dict},
            )
            return res_dict

        job_rec = app.jobs.submit_job(
            job_type="transform_ad_export",
            payload=payload,
            runner_fn=_transform_runner,
            principal=principal,
            idempotency_key=idempotency_key,
        )
        return env(
            summary=job_rec.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="submit_budget_optimization_job",
        description="Submit an asynchronous budget optimization job under channel/cell constraints without blocking the event loop.",
    )
    @mcp_error_boundary("submit_budget_optimization_job", "jobs", "submission")
    async def submit_budget_optimization_job(
        config: BudgetOptimizationInput,
        idempotency_key: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_budget_optimization_job")[0])
        model_rec = app.metadata.get_model(config.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{config.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        payload_dict = config.model_dump()

        async def _opt_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "optimization_initialized", progress_percent=20.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res = await loop.run_in_executor(None, app.decisions.optimize, config)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(
                job.job_id,
                "optimization_completed",
                progress_percent=100.0,
                state_data={"result": res},
            )
            return res

        job_rec = app.jobs.submit_job(
            job_type="budget_optimize",
            payload=payload_dict,
            runner_fn=_opt_runner,
            principal=principal,
            idempotency_key=idempotency_key,
        )
        return env(
            summary=job_rec.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="submit_flighting_optimization_job",
        description="Submit an asynchronous dynamic media flighting optimization job over a planning horizon.",
    )
    @mcp_error_boundary("submit_flighting_optimization_job", "jobs", "submission")
    async def submit_flighting_optimization_job(
        config: FlightingOptimizationInput,
        idempotency_key: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_flighting_optimization_job")[0])
        model_rec = app.metadata.get_model(config.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{config.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        payload_dict = config.model_dump()

        async def _flight_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "flighting_initialized", progress_percent=20.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res = await loop.run_in_executor(None, app.decisions.optimize_flighting, config)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(
                job.job_id,
                "optimization_completed",
                progress_percent=100.0,
                state_data={"result": res},
            )
            return res

        job_rec = app.jobs.submit_job(
            job_type="flighting_optimize",
            payload=payload_dict,
            runner_fn=_flight_runner,
            principal=principal,
            idempotency_key=idempotency_key,
        )
        return env(
            summary=job_rec.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="submit_cross_validate_mmm_job",
        description="Submit an asynchronous Time-Slice Cross-Validation job across multiple temporal folds.",
    )
    @mcp_error_boundary("submit_cross_validate_mmm_job", "jobs", "submission")
    async def submit_cross_validate_mmm_job(
        input: CrossValidateMMMInput,
        idempotency_key: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_cross_validate_mmm_job")[0])
        model_rec = app.metadata.get_model(input.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        payload_dict = input.model_dump()

        async def _cv_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "cv_initialized", progress_percent=15.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res = await loop.run_in_executor(None, lambda: app.diagnostics.cross_validate(input, cancel_event=cancel_event))
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(
                job.job_id,
                "cv_completed",
                progress_percent=100.0,
                state_data={"result": res},
            )
            return res

        job_rec = app.jobs.submit_job(
            job_type="cross_validate_mmm",
            payload=payload_dict,
            runner_fn=_cv_runner,
            principal=principal,
            idempotency_key=idempotency_key,
        )
        return env(
            summary=job_rec.to_dict(),
            next_actions=["poll_job_progress", "get_job_status"],
        )

    @mcp.tool(
        name="submit_prior_sensitivity_job",
        description="Submit an asynchronous prior sensitivity evaluation job exploring channel rank order stability.",
    )
    @mcp_error_boundary("submit_prior_sensitivity_job", "jobs", "submission")
    async def submit_prior_sensitivity_job(
        input: PriorSensitivityInput,
        idempotency_key: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("submit_prior_sensitivity_job")[0])
        model_rec = app.metadata.get_model(input.model_id)
        if not model_rec:
            raise DomainError("MODEL_NOT_FOUND", f"Model '{input.model_id}' was not found")
        authorize_model(principal, model_rec, action="read")

        payload_dict = input.model_dump()

        async def _ps_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(job.job_id, "sensitivity_initialized", progress_percent=20.0)
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            res = await loop.run_in_executor(None, lambda: app.diagnostics.prior_sensitivity(input, cancel_event=cancel_event))
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            app.jobs.record_checkpoint(
                job.job_id,
                "sensitivity_completed",
                progress_percent=100.0,
                state_data={"result": res},
            )
            return res

        job_rec = app.jobs.submit_job(
            job_type="prior_sensitivity",
            payload=payload_dict,
            runner_fn=_ps_runner,
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
        try:
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
        except DomainError:
            if getattr(app.settings, "platform_client_enabled", False) and hasattr(app, "platform_client"):
                status_res = await app.platform_client.get_job_status(job_id)
                return env(
                    summary=status_res,
                    next_actions=["poll_job_progress", "get_job_status"],
                )
            raise

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

        async def _resume_runner(job, cancel_event: asyncio.Event) -> dict[str, Any]:
            loop = asyncio.get_running_loop()
            if cancel_event.is_set():
                raise asyncio.CancelledError()
            latest_cp = app.jobs.repo.get_latest_checkpoint(job.job_id)
            if latest_cp and latest_cp.state_data and "result" in latest_cp.state_data:
                return latest_cp.state_data["result"]
            jtype = rec.job_type
            if jtype in ("fit_mmm", "mmm.fit"):
                config = FitMMMInput(**rec.payload)
                app.jobs.record_checkpoint(job.job_id, "sampling_initialized", progress_percent=30.0)
                if cancel_event.is_set():
                    raise asyncio.CancelledError()
                res = await loop.run_in_executor(None, app.models.fit, config, principal)
                if cancel_event.is_set():
                    raise asyncio.CancelledError()
                res_dict = res.model_dump()
                app.jobs.record_checkpoint(
                    job.job_id,
                    "fit_completed",
                    progress_percent=100.0,
                    state_data={"model_id": res.model_id, "result": res_dict},
                )
                return res_dict
            elif jtype in ("budget_optimize", "mmm.budget_optimize"):
                config = BudgetOptimizationInput(**rec.payload)
                res = await loop.run_in_executor(None, app.decisions.optimize, config)
                app.jobs.record_checkpoint(
                    job.job_id,
                    "optimization_completed",
                    progress_percent=100.0,
                    state_data={"result": res},
                )
                return res
            elif jtype in ("flighting_optimize", "mmm.flighting_optimize"):
                config = FlightingOptimizationInput(**rec.payload)
                res = await loop.run_in_executor(None, app.decisions.optimize_flighting, config)
                app.jobs.record_checkpoint(
                    job.job_id,
                    "optimization_completed",
                    progress_percent=100.0,
                    state_data={"result": res},
                )
                return res
            elif jtype in ("cross_validate_mmm", "mmm.cross_validate"):
                config = CrossValidateMMMInput(**rec.payload)
                res = await loop.run_in_executor(None, app.diagnostics.cross_validate, config)
                app.jobs.record_checkpoint(
                    job.job_id,
                    "cv_completed",
                    progress_percent=100.0,
                    state_data={"result": res},
                )
                return res
            elif jtype in ("prior_sensitivity", "mmm.prior_sensitivity"):
                config = PriorSensitivityInput(**rec.payload)
                res = await loop.run_in_executor(None, app.diagnostics.prior_sensitivity, config)
                app.jobs.record_checkpoint(
                    job.job_id,
                    "sensitivity_completed",
                    progress_percent=100.0,
                    state_data={"result": res},
                )
                return res
            elif jtype in ("transform_ad_export", "dataset.transform_ad_export"):
                registered, provenance, plan = await loop.run_in_executor(
                    None,
                    lambda: app.datasets.transform_long_form(**rec.payload, principal=principal),
                )
                from dataclasses import asdict

                res_dict = {
                    "transformed_dataset_id": registered.dataset_id,
                    "input_dataset_id": rec.payload.get("dataset_id"),
                    "rows": registered.rows,
                    "format": registered.format,
                    "spend_reconciled": provenance.spend_reconciled,
                    "spend_delta": provenance.spend_delta,
                    "calendar_frequency": plan.frequency,
                    "inserted_periods": provenance.inserted_periods,
                    "provenance": asdict(provenance),
                    "transformation_plan": asdict(plan),
                }
                app.jobs.record_checkpoint(
                    job.job_id,
                    "transformation_completed",
                    progress_percent=100.0,
                    state_data={"result": res_dict},
                )
                return res_dict
            else:
                raise DomainError("JOB_NOT_RESUMABLE", f"Job type '{jtype}' cannot be resumed")

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
        # Authorization and canonical job state are owned by Python. Native code
        # acknowledges the interaction only after the canonical transition succeeds.
        cancelled = app.jobs.cancel_job(job_id, principal=principal)

        from marketing_mcp.accelerators import fast_acknowledge_cancellation

        ack = fast_acknowledge_cancellation(
            job_id,
            in_process=cancelled.status is JobStatus.CANCELLING,
        )
        if not ack.get("acknowledged"):
            err = ack.get("error") or {}
            raise DomainError(
                err.get("code", "INVALID_JOB_ID"),
                err.get("message", "Invalid job id"),
            )

        summary_dict = cancelled.to_dict()
        summary_dict["interaction_status"] = ack.get("status")
        summary_dict["fence_triggered"] = ack.get("fence_triggered", True)
        return env(summary=summary_dict)

    @mcp.tool(
        name="list_jobs",
        description="List recent asynchronous background jobs for the active tenant.",
    )
    @mcp_error_boundary("list_jobs", "jobs", "monitoring")
    async def list_jobs(status: str | None = None, limit: int = 50, verbose: bool = False):
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
        jobs_list = [
            r.to_dict() if verbose else (r.to_summary_dict() if hasattr(r, "to_summary_dict") else r.to_dict())
            for r in records
        ]
        return env(summary={"jobs": jobs_list, "count": len(records), "verbose": verbose})
