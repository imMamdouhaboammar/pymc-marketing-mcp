"""Data models and references for repositories and artifact storage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ArtifactRef:
    """Provider-neutral immutable blob reference with integrity and ownership."""

    uri: str
    sha256: str
    size_bytes: int
    version: str
    owner: str
    tenant_id: str | None
    content_type: str = "application/octet-stream"
    created_at: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.uri or not self.version or not self.owner:
            raise ValueError("artifact uri, version, and owner are required")
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError("artifact sha256 must be 64 lowercase hexadecimal characters")
        if self.size_bytes < 0:
            raise ValueError("artifact size_bytes cannot be negative")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(UTC).isoformat())


BlobRef = ArtifactRef

__all__ = ["ArtifactRef", "BlobRef"]
