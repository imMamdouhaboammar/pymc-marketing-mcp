"""Idempotency and semantic hash generation for background compute jobs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonicalize_semantic_input(data: Any) -> str:
    """Serialize input data into a deterministic, reproducible JSON string."""
    raw_dict: dict[str, Any]
    if isinstance(data, BaseModel):
        raw_dict = data.model_dump()
    elif isinstance(data, dict):
        raw_dict = {str(k): v for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        raw_dict = {"items": list(data)}
    elif hasattr(data, "__dict__"):
        raw_dict = dict(vars(data))
    else:
        raw_dict = {"value": str(data)}

    # Exclude ephemeral/non-semantic fields
    cleaned = {
        k: v
        for k, v in sorted(raw_dict.items())
        if k not in ("request_id", "timestamp", "trace_id", "span_id", "created_at")
    }
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_semantic_idempotency_key(
    tenant_id: str | None,
    job_type: str,
    semantic_input: Any,
) -> str:
    """Compute a deterministic SHA-256 idempotency key scoped to tenant, job type, and inputs."""
    canon = canonicalize_semantic_input(semantic_input)
    scoped_string = f"{tenant_id or 'default'}:{job_type}:{canon}"
    digest = hashlib.sha256(scoped_string.encode("utf-8")).hexdigest()
    return f"idemp_{digest[:24]}"


__all__ = ["canonicalize_semantic_input", "compute_semantic_idempotency_key"]
