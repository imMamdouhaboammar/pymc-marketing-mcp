"""Job state machine and transition validator."""

from __future__ import annotations

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobStatus

VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLING, JobStatus.CANCELLED},
    JobStatus.CANCELLING: {JobStatus.CANCELLED, JobStatus.FAILED},
    JobStatus.SUCCEEDED: set(),
    JobStatus.CANCELLED: {JobStatus.QUEUED, JobStatus.SUCCEEDED},
    JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.SUCCEEDED},
}


def can_transition(current: JobStatus, target: JobStatus) -> bool:
    """Return True if transitioning from current to target is allowed."""
    if current == target:
        return True
    return target in VALID_TRANSITIONS.get(current, set())


def validate_transition(current: JobStatus, target: JobStatus) -> None:
    """Validate transition or raise DomainError INVALID_STATE."""
    if not can_transition(current, target):
        raise DomainError(
            "INVALID_STATE",
            f"Cannot transition job from state '{current.value}' to '{target.value}'",
            evidence={"current_state": current.value, "target_state": target.value},
            next_action="Verify current job status before triggering state mutation",
        )
