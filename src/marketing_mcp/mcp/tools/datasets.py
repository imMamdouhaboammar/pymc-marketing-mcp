"""Datasets MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.security import safe_ingest_path
from marketing_mcp.security.ownership import authorize_dataset
from marketing_mcp.security.policy import require_scope, scopes_for_tool


import base64
import urllib.error
import urllib.parse
import urllib.request


def register_datasets_tools(mcp, app: Application, context_provider: Any = None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="register_dataset",
        description=(
            "Register a marketing dataset for MMM or CLV analysis and return a stable dataset reference. "
            "Supports direct CSV text in 'content', base64-encoded CSV/Parquet in 'content_base64', "
            "remote HTTP/HTTPS URL in 'url' or 'path', or an existing server path in 'path'."
        ),
    )
    async def register_dataset(
        path: str | None = None,
        content: str | None = None,
        content_base64: str | None = None,
        url: str | None = None,
        filename: str | None = None,
    ):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("register_dataset")[0])

            # 1. Direct CSV text content
            if content is not None:
                raw = content.encode("utf-8")
                ext = (Path(filename).suffix.lower() if filename else ".csv") or ".csv"
                r = app.datasets.register_bytes(
                    raw, format=ext.lstrip("."), filename=filename, principal=principal
                )
                return env(
                    summary=r.model_dump(),
                    provenance={"fingerprint": r.fingerprint},
                    next_actions=["inspect_dataset", "validate_dataset"],
                )

            # 2. Base64-encoded bytes
            if content_base64 is not None:
                try:
                    raw = base64.b64decode(content_base64)
                except Exception as exc:
                    raise DomainError(
                        "INVALID_BASE64",
                        f"Failed to decode base64 content: {exc}",
                        evidence={"details": str(exc)},
                        next_action="Provide valid base64-encoded file bytes",
                    ) from exc
                ext = (Path(filename).suffix.lower() if filename else ".csv") or ".csv"
                r = app.datasets.register_bytes(
                    raw, format=ext.lstrip("."), filename=filename, principal=principal
                )
                return env(
                    summary=r.model_dump(),
                    provenance={"fingerprint": r.fingerprint},
                    next_actions=["inspect_dataset", "validate_dataset"],
                )

            # 3. HTTP / HTTPS URL download
            target_url = url or (
                path if (path and (path.startswith("http://") or path.startswith("https://"))) else None
            )
            if target_url is not None:
                if not (target_url.startswith("http://") or target_url.startswith("https://")):
                    raise DomainError(
                        "UNSUPPORTED_SCHEME",
                        f"URL must start with http:// or https://, got: '{target_url}'",
                        evidence={"url": target_url},
                        next_action="Provide a valid http:// or https:// URL",
                    )
                try:
                    req = urllib.request.Request(
                        target_url,
                        headers={"User-Agent": "PyMC-Marketing-MCP/0.4.0 (Dataset Ingest)"},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        raw = resp.read()
                except urllib.error.HTTPError as exc:
                    raise DomainError(
                        "UNREACHABLE_SOURCE",
                        f"HTTP {exc.code} {exc.reason} when downloading dataset from URL: {target_url}",
                        evidence={"url": target_url, "http_status": exc.code, "reason": str(exc.reason)},
                        next_action="Verify that the dataset URL is public and accessible",
                    ) from exc
                except urllib.error.URLError as exc:
                    raise DomainError(
                        "UNREACHABLE_SOURCE",
                        f"Failed to connect to dataset URL '{target_url}': {exc.reason}",
                        evidence={"url": target_url, "reason": str(exc.reason)},
                        next_action="Verify the host name and network connection to the URL",
                    ) from exc
                parsed_path = urllib.parse.urlparse(target_url).path
                ext = (
                    Path(parsed_path).suffix.lower()
                    or (Path(filename).suffix.lower() if filename else ".csv")
                    or ".csv"
                )
                fn = filename or Path(parsed_path).name or "downloaded_dataset.csv"
                r = app.datasets.register_bytes(
                    raw, format=ext.lstrip("."), filename=fn, principal=principal
                )
                return env(
                    summary=r.model_dump(),
                    provenance={"fingerprint": r.fingerprint},
                    next_actions=["inspect_dataset", "validate_dataset"],
                )

            # 4. Server filesystem path
            if path is not None:
                source = safe_ingest_path(
                    Path(path), app.settings.ingest_dir, app.settings.max_dataset_mb * 1024 * 1024
                )
                r = app.datasets.register_file(source, principal=principal)
                return env(
                    summary=r.model_dump(),
                    provenance={"fingerprint": r.fingerprint},
                    next_actions=["inspect_dataset", "validate_dataset"],
                )

            # 5. Missing all parameters
            raise DomainError(
                "MISSING_INPUT",
                "register_dataset requires at least one of 'content', 'content_base64', 'url', or 'path'",
                evidence=None,
                next_action="Pass CSV text in 'content', base64 data in 'content_base64', or a download URL in 'url'",
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="list_datasets",
        description="List all registered datasets and available inbox files on the server.",
    )
    async def list_datasets():
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("list_datasets")[0])
            registered = app.metadata.list_datasets()
            if principal and principal.tenant_id and principal.tenant_id != "default":
                registered = [d for d in registered if d.get("tenant_id") == principal.tenant_id]

            inbox_files = []
            if app.settings.ingest_dir.exists():
                for f in sorted(app.settings.ingest_dir.iterdir()):
                    if f.is_file() and f.suffix.lower() in {".csv", ".parquet"}:
                        inbox_files.append({"name": f.name, "size_bytes": f.stat().st_size})

            return env(
                summary={
                    "total_registered": len(registered),
                    "total_inbox_files": len(inbox_files),
                },
                evidence={
                    "registered_datasets": [
                        {
                            "dataset_id": d.get("dataset_id"),
                            "rows": d.get("rows"),
                            "format": d.get("format"),
                            "created_at": d.get("created_at"),
                            "fingerprint": d.get("fingerprint")[:12] if d.get("fingerprint") else None,
                        }
                        for d in registered
                    ],
                    "inbox_files": inbox_files,
                },
                next_actions=["inspect_dataset", "validate_dataset", "register_dataset"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="inspect_dataset",
        description=(
            "Inspect a registered dataset before MMM configuration. "
            "Returns candidate targets, channels, controls, frequency, and data issues."
        ),
    )
    async def inspect_dataset(dataset_id: str):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("inspect_dataset")[0])
            dataset = app.metadata.get_dataset(dataset_id)
            if not dataset:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
            authorize_dataset(principal, dataset, action="read")

            r = app.datasets.inspect(dataset_id)
            return env(
                summary=r.model_dump(),
                warnings=[x.model_dump() for x in r.issues],
                next_actions=["validate_dataset"] if r.mmm_candidate else ["repair_dataset"],
            )
        except DomainError as e:
            return e.to_dict()

    @mcp.tool(
        name="validate_dataset",
        description=(
            "Run MMM-specific data quality, panel-shape, and identifiability checks. "
            "This must pass before fitting."
        ),
    )
    async def validate_dataset(
        dataset_id: str,
        date_column: str,
        target_column: str,
        channel_columns: list[str],
        control_columns: list[str] | None = None,
        dims: list[str] | None = None,
    ):
        try:
            principal = resolve_context().principal
            require_scope(principal, scopes_for_tool("validate_dataset")[0])
            dataset = app.metadata.get_dataset(dataset_id)
            if not dataset:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
            authorize_dataset(principal, dataset, action="read")

            r = app.datasets.validate(
                dataset_id,
                date_column,
                target_column,
                channel_columns,
                control_columns or [],
                dims or [],
            )
            return env(
                summary={"dataset_id": dataset_id, "valid_for_modeling": r.valid_for_modeling},
                evidence={"findings": [f.model_dump() for f in r.findings]},
                next_actions=["fit_mmm"] if r.valid_for_modeling else ["repair_dataset"],
            )
        except DomainError as e:
            return e.to_dict()
