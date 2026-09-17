"""Deterministic behavioral evaluation helpers for Skill tool traces."""

from __future__ import annotations

from dataclasses import dataclass

from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.skillpack.registry import ToolTrace


@dataclass(frozen=True)
class TraceEvaluation:
    valid: bool
    reasons: tuple[str, ...]


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
    consecutive_polls = 0

    for index, step in enumerate(trace.steps):
        event = step.get("event")
        tool = step.get("tool")
        result = step.get("result")

        if event == "disconnect":
            disconnected = True
            resubmit_allowed_after_recovery = False
            consecutive_polls = 0
            continue

        if tool != "poll_job_progress":
            consecutive_polls = 0
        if tool == "poll_job_progress":
            consecutive_polls += 1
            if (
                trace.max_consecutive_polls is not None
                and consecutive_polls > trace.max_consecutive_polls
            ):
                reasons.append(
                    "unbounded polling: trace exceeded its declared consecutive polling budget"
                )

        if tool == "register_dataset" and step.get("client") == "remote":
            arguments = step.get("arguments") or {}
            path = arguments.get("path")
            if path and not str(path).startswith(("http://", "https://")):
                reasons.append(
                    "remote client-local filesystem path must not be treated as server-readable input"
                )

        if tool in {"fit_mmm", "calibrate_mmm"}:
            decision_ready = False

        if tool == "diagnose_mmm":
            decision_ready = result in {"approved", "approved_with_caution"}

        if tool in gated and not decision_ready:
            reasons.append(f"{tool} called before an approved diagnostic gate at step {index}")

        if disconnected and tool == "recover_execution_state":
            recovery = result if isinstance(result, dict) else {}
            resubmit_allowed_after_recovery = (
                recovery.get("status") in {"failed", "cancelled"}
                and recovery.get("can_resume") is False
                and recovery.get("has_usable_result") is False
            )
        if disconnected and tool == "submit_fit_mmm_job" and not resubmit_allowed_after_recovery:
            reasons.append(
                "expensive fit resubmitted after disconnect without authoritative terminal "
                "unrecoverable state"
            )

    return TraceEvaluation(valid=not reasons, reasons=tuple(reasons))
