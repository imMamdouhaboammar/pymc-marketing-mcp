"""Scientific core algorithms decoupled from MCP and network transport."""

from __future__ import annotations

from marketing_mcp.scientific.datasets import (
    inspect_dataset_frame,
    summarize_dataset_frame,
    validate_dataset_frame,
)

__all__ = [
    "inspect_dataset_frame",
    "summarize_dataset_frame",
    "validate_dataset_frame",
]
