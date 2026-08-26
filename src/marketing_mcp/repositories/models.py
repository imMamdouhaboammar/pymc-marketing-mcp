"""Data models and references for repositories and artifact storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class ArtifactRef:
    """Immutable reference to a stored artifact with checksum and metadata."""

    uri: str
    sha256: str
    size_bytes: int
    content_type: str = "application/x-netcdf"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(UTC).isoformat())
