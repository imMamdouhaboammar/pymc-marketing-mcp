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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobRecord:
        d = dict(data)
        if isinstance(d.get("status"), str):
            d["status"] = JobStatus(d["status"])
        return cls(**d)
