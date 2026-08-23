"""Security primitives: request safety, execution principals, and scope policy."""

from marketing_mcp.security.principal import Principal
from marketing_mcp.security.request_safety import (
    safe_identifier,
    safe_ingest_path,
    safe_source_path,
)

__all__ = [
    "Principal",
    "safe_identifier",
    "safe_ingest_path",
    "safe_source_path",
]
