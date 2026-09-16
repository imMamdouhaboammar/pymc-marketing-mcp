from __future__ import annotations

import re
from pathlib import Path

from marketing_mcp.errors import DomainError

_ID = re.compile(r"^[a-zA-Z0-9_-]{1,96}$")


def safe_identifier(value: str, kind: str) -> str:
    if not _ID.fullmatch(value):
        raise DomainError("INVALID_IDENTIFIER", f"Invalid {kind} identifier")
    return value


def safe_source_path(path: Path, max_bytes: int) -> Path:
    p = path.resolve()
    if p.suffix.lower() not in {".csv", ".parquet"}:
        raise DomainError(
            "UNSUPPORTED_DATASET_FORMAT",
            f"File '{path.name}' has an unsupported extension '{p.suffix}'. Only CSV and Parquet are supported",
            evidence={"attempted_path": str(path), "extension": p.suffix},
            next_action="Provide a file with .csv or .parquet extension",
        )
    if not p.is_file():
        path_str = str(path)
        is_client_sandbox = any(
            path_str.startswith(prefix) for prefix in ("/mnt/user-data", "/mnt/data", "/home/sandbox")
        ) or any(path_str.startswith(drive) for drive in ("C:", "D:", "/Users/"))
        if is_client_sandbox:
            raise DomainError(
                "CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE",
                f"Path '{path}' is located in a client sandbox or local environment. Remote MCP servers cannot access client files directly.",
                evidence={"attempted_path": path_str},
                next_action="Pass the dataset content directly to register_dataset via 'content' (raw CSV text) or 'content_base64' (base64 string), or provide a downloadable HTTP(S) URL via 'url'.",
            )
        raise DomainError(
            "FILE_NOT_FOUND",
            f"Dataset file '{path}' does not exist on the server.",
            evidence={"attempted_path": path_str},
            next_action="Verify the file exists in the server ingest directory, or pass file content directly via 'content' or 'content_base64'.",
        )
    if p.stat().st_size > max_bytes:
        raise DomainError(
            "DATASET_TOO_LARGE",
            f"Dataset file '{path.name}' ({p.stat().st_size} bytes) exceeds maximum allowed size of {max_bytes} bytes",
            evidence={"file_size": p.stat().st_size, "max_bytes": max_bytes},
            next_action="Pre-aggregate or filter dataset to reduce size before registering",
        )
    return p


def safe_ingest_path(path: Path, ingest_root: Path, max_bytes: int) -> Path:
    root = Path(ingest_root).resolve()
    target = path if path.is_absolute() else (root / path)
    p = safe_source_path(target, max_bytes)
    try:
        p.relative_to(root)
    except ValueError as e:
        raise DomainError(
            "PATH_NOT_ALLOWED",
            "Dataset path must be inside the configured ingest directory",
            evidence={"ingest_root": str(root)},
        ) from e
    return p
