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
    resubmit_allowed_after_recovery = False
    resume_allowed_after_recovery = False
    authorized_job_id: str | None = None
    authorized_job_type: str | None = None
    last_recovery: dict | None = None
    consecutive_polls = 0

    for index, step in enumerate(trace.steps):
        event = step.get("event")
        tool = step.get("tool")
        result = step.get("result")

        if event == "disconnect":
            disconnected = True
            resubmit_allowed_after_recovery = False
            resume_allowed_after_recovery = False
            authorized_job_id = None
            authorized_job_type = None
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
            recovery_raw = result if isinstance(result, dict) else {}
            recovery = (
                recovery_raw.get("summary")
                if isinstance(recovery_raw.get("summary"), dict)
                else recovery_raw
            )
            last_recovery = recovery
            resubmit_allowed_after_recovery = (
                recovery.get("status") in {"failed", "cancelled"}
                and recovery.get("can_resume") is False
                and recovery.get("has_usable_result") is False
            )
            resume_allowed_after_recovery = recovery.get("can_resume") is True and not recovery.get(
                "has_usable_result"
            )
            authorized_job_id = recovery.get("job_id")
            authorized_job_type = recovery.get("job_type")

        if tool == "resume_job":
            resume_args = step.get("arguments") or {}
            target_job_id = resume_args.get("job_id")
            target_job_type = resume_args.get("job_type")

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
            elif authorized_job_id and target_job_id and target_job_id != authorized_job_id:
                reasons.append(
                    f"resume_job called for job '{target_job_id}' at step {index} but recovery authorized job '{authorized_job_id}'"
                )
            elif authorized_job_type and target_job_type and target_job_type != authorized_job_type:
                reasons.append(
                    f"resume_job called for job type '{target_job_type}' at step {index} but recovery authorized '{authorized_job_type}'"
                )

            # Consume/reset authorization after resume
            resume_allowed_after_recovery = False
            authorized_job_id = None
            authorized_job_type = None

        if disconnected and tool in ASYNC_SUBMIT_TOOLS:
            if not resubmit_allowed_after_recovery:
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
            else:
                resubmit_allowed_after_recovery = False

    return TraceEvaluation(valid=not reasons, reasons=tuple(reasons))
