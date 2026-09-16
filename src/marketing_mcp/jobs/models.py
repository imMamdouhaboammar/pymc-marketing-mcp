"""Durable job models and state definitions (Wave 5 Task 3)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.CANCELLED, JobStatus.FAILED)


class JobCheckpointStage(str, Enum):
    DATASET_VALIDATED = "dataset_validated"
    PRIORS_COMPILED = "priors_compiled"
    SAMPLING_INITIALIZED = "sampling_initialized"
    CHAINS_SAMPLING = "chains_sampling"
    POSTERIOR_SAVED = "posterior_saved"
    DIAGNOSTICS_COMPLETED = "diagnostics_completed"
    CUSTOM = "custom"


@dataclass
class JobCheckpoint:
    checkpoint_id: str
    job_id: str
    stage: str
    step: int = 0
    total_steps: int = 1
    progress_percent: float = 0.0
    state_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobCheckpoint:
        return cls(**data)


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    status: JobStatus = JobStatus.QUEUED
    owner: str = "local"
    tenant_id: str | None = None
    idempotency_key: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    fence_token: int = 0
    attempts: int = 0
    max_attempts: int = 3
    checkpoints: list[JobCheckpoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["checkpoints"] = [c if isinstance(c, dict) else c.to_dict() for c in self.checkpoints]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        d = dict(data)
        if isinstance(d.get("status"), str):
            d["status"] = JobStatus(d["status"])
        if "checkpoints" in d and isinstance(d["checkpoints"], list):
            d["checkpoints"] = [
                JobCheckpoint.from_dict(c) if isinstance(c, dict) else c
                for c in d["checkpoints"]
            ]
        return cls(**d)
