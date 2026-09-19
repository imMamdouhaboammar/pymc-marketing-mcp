"""Deterministic behavioral evaluation helpers for Skill tool traces."""

from __future__ import annotations

from dataclasses import dataclass

from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.skillpack.registry import ToolTrace


@dataclass(frozen=True)
class TraceEvaluation:
    valid: bool
    reasons: tuple[str, ...]


ASYNC_SUBMIT_TOOLS = frozenset(
    {
        "submit_fit_mmm_job",
        "submit_transform_ad_export_job",
        "submit_budget_optimization_job",
        "submit_flighting_optimization_job",
        "submit_cross_validate_mmm_job",
        "submit_prior_sensitivity_job",
    }
)

JOB_TYPE_TO_SUBMIT_TOOL = {
    "fit_mmm": "submit_fit_mmm_job",
    "mmm.fit": "submit_fit_mmm_job",
    "transform_ad_export": "submit_transform_ad_export_job",
    "dataset.transform_ad_export": "submit_transform_ad_export_job",
    "budget_optimize": "submit_budget_optimization_job",
    "mmm.budget_optimize": "submit_budget_optimization_job",
    "flighting_optimize": "submit_flighting_optimization_job",
    "mmm.flighting_optimize": "submit_flighting_optimization_job",
    "cross_validate_mmm": "submit_cross_validate_mmm_job",
    "mmm.cross_validate": "submit_cross_validate_mmm_job",
    "prior_sensitivity": "submit_prior_sensitivity_job",
    "mmm.prior_sensitivity": "submit_prior_sensitivity_job",
}

SUBMIT_TOOL_TO_JOB_FAMILY = {
    "submit_fit_mmm_job": "fit_mmm",
    "submit_transform_ad_export_job": "transform_ad_export",
    "submit_budget_optimization_job": "budget_optimize",
    "submit_flighting_optimization_job": "flighting_optimize",
    "submit_cross_validate_mmm_job": "cross_validate_mmm",
    "submit_prior_sensitivity_job": "prior_sensitivity",
}


CONTINUATION_TOOLS = {
    "diagnose_mmm",
    "inspect_dataset",
    "validate_dataset",
    "simulate_budget",
    "optimize_budget",
    "recommend_next_measurement",
    "calibrate_mmm",
}


def evaluate_tool_trace(trace: ToolTrace) -> TraceEvaluation:
    """Evaluate safety/order invariants without executing expensive statistical tools."""
    gated = {
        cap.name
        for cap in get_capability_inventory()
        if cap.kind == "tool" and cap.decision_gate_required
    }
    reasons: list[str] = []
    decision_ready = False
    disconnected = False
    authorized_resubmit_tool: str | None = None
    authorized_resubmit_job_id: str | None = None
    authorized_resubmit_job_type: str | None = None
    resume_allowed_after_recovery = False
    authorized_resume_job_id: str | None = None
    authorized_resume_job_type: str | None = None
    last_submitted_async_tool: str | None = None
    last_submitted_async_job_id: str | None = None
    last_recovery: dict | None = None
    consecutive_polls = 0

    for index, step in enumerate(trace.steps):
        event = step.get("event")
        tool = step.get("tool")
        result = step.get("result")

        if event == "disconnect":
            disconnected = True
            authorized_resubmit_tool = None
            authorized_resubmit_job_id = None
            authorized_resubmit_job_type = None
            resume_allowed_after_recovery = False
            authorized_resume_job_id = None
            authorized_resume_job_type = None
            last_recovery = None
            consecutive_polls = 0
            continue

        if tool != "poll_job_progress":
            consecutive_polls = 0
        if tool == "poll_job_progress":
            consecutive_polls += 1
            poll_budget = (
                trace.max_consecutive_polls if trace.max_consecutive_polls is not None else 3
            )
            if consecutive_polls > poll_budget:
                reasons.append("unbounded polling: trace exceeded consecutive polling budget")

        if disconnected and last_recovery and last_recovery.get("has_usable_result"):
            if tool in CONTINUATION_TOOLS:
                disconnected = False
                last_recovery = None

        if tool == "register_dataset" and step.get("client") == "remote":
            arguments = step.get("arguments") or {}
            path = arguments.get("path")
            if path and not str(path).startswith(("http://", "https://")):
                reasons.append(
                    "remote client-local filesystem path must not be treated as server-readable input"
                )

        if tool in {"fit_mmm", "calibrate_mmm", "submit_fit_mmm_job", "resume_job"}:
            decision_ready = False

        if tool == "diagnose_mmm":
            status = None
            if isinstance(result, str):
                status = result
            elif isinstance(result, dict):
                status = result.get("decision_status") or (result.get("summary") or {}).get(
                    "decision_status"
                )
            decision_ready = status in {"approved", "approved_with_caution"}

        if tool in gated and not decision_ready:
            reasons.append(f"{tool} called before an approved diagnostic gate at step {index}")

        if disconnected and tool == "recover_execution_state":
            rec_args = step.get("arguments") or {}
            rec_arg_id = rec_args.get("job_id_or_key") or rec_args.get("job_id")

            recovery_raw = result if isinstance(result, dict) else {}
            recovery = (
                recovery_raw.get("summary")
                if isinstance(recovery_raw.get("summary"), dict)
                else recovery_raw
            )
            last_recovery = recovery
            rec_status = recovery.get("status")
            rec_can_resume = recovery.get("can_resume")
            rec_has_usable_result = recovery.get("has_usable_result")
            rec_job_type = recovery.get("job_type")
            rec_job_id = recovery.get("job_id")

            job_id_valid = (
                rec_job_id is not None
                and isinstance(rec_job_id, str)
                and bool(rec_job_id.strip())
            )
            if not job_id_valid:
                reasons.append(
                    f"recover_execution_state at step {index} returned missing or invalid 'job_id'; "
                    "recovery state must be bound to a concrete job resource"
                )

            job_type_valid = (
                rec_job_type is not None
                and isinstance(rec_job_type, str)
                and rec_job_type in JOB_TYPE_TO_SUBMIT_TOOL
            )
            if not job_type_valid:
                reasons.append(
                    f"recover_execution_state at step {index} returned missing or unknown 'job_type' '{rec_job_type}'; "
                    "recovery state must identify a known job family"
                )

            originating_job_matched = True
            if not last_submitted_async_job_id:
                originating_job_matched = False
                reasons.append(
                    f"recover_execution_state at step {index} cannot match recovered job '{rec_job_id}' "
                    "because preceding async submission did not record an authoritative 'job_id'"
                )
            elif job_id_valid and rec_job_id != last_submitted_async_job_id:
                originating_job_matched = False
                reasons.append(
                    f"recovery resource mismatch: recover_execution_state at step {index} recovered "
                    f"job '{rec_job_id}' but originating submission was for job '{last_submitted_async_job_id}'"
                )

            if (
                rec_arg_id
                and last_submitted_async_job_id
                and rec_arg_id != last_submitted_async_job_id
            ):
                originating_job_matched = False
                reasons.append(
                    f"recovery argument mismatch: recover_execution_state at step {index} requested "
                    f"'{rec_arg_id}' but originating submission was for job '{last_submitted_async_job_id}'"
                )

            originating_family_matched = True
            if not last_submitted_async_tool:
                originating_family_matched = False
                reasons.append(
                    f"recover_execution_state called at step {index} without any preceding asynchronous job submission"
                )
            elif job_type_valid:
                expected_submit_tool = JOB_TYPE_TO_SUBMIT_TOOL[rec_job_type]
                if expected_submit_tool != last_submitted_async_tool:
                    originating_family_matched = False
                    reasons.append(
                        f"recovery family mismatch: recover_execution_state at step {index} recovered "
                        f"job_type '{rec_job_type}' (tool '{expected_submit_tool}') which does not match originating submission "
                        f"'{last_submitted_async_tool}'"
                    )

            if (
                rec_status in {"failed", "cancelled"}
                and rec_can_resume is False
                and rec_has_usable_result is False
                and job_id_valid
                and job_type_valid
                and originating_job_matched
                and originating_family_matched
            ):
                authorized_resubmit_tool = JOB_TYPE_TO_SUBMIT_TOOL[rec_job_type]
                authorized_resubmit_job_type = rec_job_type
                authorized_resubmit_job_id = rec_job_id
            else:
                authorized_resubmit_tool = None
                authorized_resubmit_job_id = None
                authorized_resubmit_job_type = None

            if (
                rec_can_resume is True
                and not rec_has_usable_result
                and job_id_valid
                and job_type_valid
                and originating_job_matched
                and originating_family_matched
            ):
                resume_allowed_after_recovery = True
                authorized_resume_job_id = rec_job_id
                authorized_resume_job_type = rec_job_type
            else:
                resume_allowed_after_recovery = False
                authorized_resume_job_id = None
                authorized_resume_job_type = None

        if tool == "resume_job":
            resume_args = step.get("arguments") or {}
            unsupported_args = set(resume_args.keys()) - {"job_id"}
            if unsupported_args:
                reasons.append(
                    f"resume_job called with unsupported argument(s) {sorted(unsupported_args)} at step {index}; "
                    "MCP tool accepts only 'job_id'"
                )

            target_job_id = resume_args.get("job_id")
            if not target_job_id or not isinstance(target_job_id, str) or not str(target_job_id).strip():
                reasons.append(
                    f"resume_job called at step {index} without a valid non-empty 'job_id'"
                )

            valid_resume_authorized = (
                resume_allowed_after_recovery
                and bool(authorized_resume_job_id)
                and target_job_id == authorized_resume_job_id
                and not unsupported_args
            )

            if not resume_allowed_after_recovery:
                if last_recovery and last_recovery.get("has_usable_result"):
                    reasons.append(
                        f"resume_job called at step {index} but recovery returned has_usable_result=True; "
                        "correct action is continuation without resume"
                    )
                elif last_recovery and last_recovery.get("can_resume") is False:
                    reasons.append(
                        f"resume_job called at step {index} but recovery returned can_resume=False"
                    )
                elif disconnected:
                    reasons.append(
                        f"resume_job called after disconnect at step {index} without authoritative recovery "
                        "confirming can_resume=True"
                    )
                else:
                    reasons.append(
                        f"resume_job called at step {index} without authoritative recovery "
                        "confirming can_resume=True"
                    )
            else:
                if authorized_resume_job_id and target_job_id and target_job_id != authorized_resume_job_id:
                    reasons.append(
                        f"resume_job called for job '{target_job_id}' at step {index} but recovery authorized job '{authorized_resume_job_id}'"
                    )
                if authorized_resume_job_type and last_submitted_async_tool:
                    expected_submit_tool = JOB_TYPE_TO_SUBMIT_TOOL.get(authorized_resume_job_type)
                    if expected_submit_tool and expected_submit_tool != last_submitted_async_tool:
                        reasons.append(
                            f"resume_job at step {index} attempts to resume recovered job of type '{authorized_resume_job_type}' "
                            f"which does not match originating submission '{last_submitted_async_tool}'"
                        )

            # Valid authorized resume closes recovery/disconnect context
            if valid_resume_authorized:
                disconnected = False
                last_recovery = None

            # Consume/reset authorization after resume attempt
            resume_allowed_after_recovery = False
            authorized_resume_job_id = None
            authorized_resume_job_type = None
            authorized_resubmit_tool = None
            authorized_resubmit_job_id = None
            authorized_resubmit_job_type = None

        if tool in ASYNC_SUBMIT_TOOLS:
            sub_res = step.get("result")
            sub_job_id = None
            if isinstance(sub_res, dict):
                sub_job_id = sub_res.get("job_id") or (sub_res.get("summary") or {}).get("job_id")
            elif isinstance(sub_res, str):
                sub_job_id = sub_res
            elif isinstance(step.get("arguments"), dict):
                sub_job_id = step["arguments"].get("job_id")

            if disconnected:
                if not authorized_resubmit_tool:
                    if tool == "submit_fit_mmm_job":
                        reasons.append(
                            "expensive fit resubmitted after disconnect without authoritative terminal "
                            "unrecoverable state"
                        )
                    else:
                        reasons.append(
                            f"expensive {tool} resubmitted after disconnect without authoritative terminal "
                            "unrecoverable state"
                        )
                elif tool != authorized_resubmit_tool:
                    reasons.append(
                        f"cross-family resubmission blocked: '{tool}' invoked at step {index} but "
                        f"recovery authorized resubmission for '{authorized_resubmit_tool}' "
                        f"(recovered job_type='{authorized_resubmit_job_type}', job_id='{authorized_resubmit_job_id}')"
                    )
                else:
                    # Valid authorized same-family resubmission closes recovery/disconnect context
                    disconnected = False
                    last_recovery = None

                # Authorization consumed immediately upon resubmission attempt
                authorized_resubmit_tool = None
                authorized_resubmit_job_id = None
                authorized_resubmit_job_type = None
                resume_allowed_after_recovery = False
                authorized_resume_job_id = None
                authorized_resume_job_type = None

            last_submitted_async_tool = tool
            if sub_job_id and isinstance(sub_job_id, str) and sub_job_id.strip():
                last_submitted_async_job_id = sub_job_id.strip()
            else:
                last_submitted_async_job_id = None

    return TraceEvaluation(valid=not reasons, reasons=tuple(reasons))
