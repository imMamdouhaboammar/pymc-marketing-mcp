import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from marketing_mcp.app import Application
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.envelope import env
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.security.policy import require_scope, scopes_for_tool

logger = logging.getLogger(__name__)


def register_artifacts_tools(mcp, app: Application, context_provider=None) -> None:
    from marketing_mcp.mcp.context import stdio_context_provider

    resolve_context = context_provider or stdio_context_provider

    @mcp.tool(
        name="export_artifact_to_sandbox",
        description=(
            "Push/stage a model or dataset artifact (up to 1GB) for the AI client sandbox to download, "
            "providing streaming URLs, curl commands, python snippets, and SHA256 integrity checksums."
        ),
    )
    @mcp_error_boundary("export_artifact_to_sandbox", "artifacts", "export")
    async def export_artifact_to_sandbox(
        model_id: str | None = None,
        artifact_uri: str | None = None,
        export_name: str | None = None,
    ):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("export_artifact_to_sandbox")[0])

        ref: ArtifactRef | None = None
        meta_info: dict[str, Any] = {}

        if model_id:
            rec = app.models.status(model_id)
            if not rec.artifact_ref:
                raise DomainError("ARTIFACT_NOT_FOUND", f"Model {model_id} has no artifact reference")
            ref = ArtifactRef(**rec.artifact_ref)
            meta_info = {
                "model_id": rec.model_id,
                "dataset_id": rec.dataset_id,
                "lineage_stage": rec.lineage_stage,
                "created_at": rec.created_at,
            }
        elif artifact_uri:
            prefix = "blob://"
            if not artifact_uri.startswith(prefix):
                raise DomainError("INPUT_INVALID", "Unsupported artifact URI scheme")
            parts = artifact_uri[len(prefix):].split("/")
            if len(parts) != 2:
                raise DomainError("INPUT_INVALID", "Malformed artifact URI")
            _namespace, digest = parts
            ref = ArtifactRef(
                uri=artifact_uri,
                sha256=digest,
                size_bytes=0,
                version=digest,
                content_type="application/octet-stream",
                owner=principal.subject if principal else "local",
                tenant_id=principal.tenant_id if principal else None,
            )
            target_path = app.artifacts.object_path(ref)
            if target_path.is_file():
                ref.size_bytes = target_path.stat().st_size
            else:
                raise DomainError("ARTIFACT_NOT_FOUND", f"Artifact at {artifact_uri} does not exist")
        else:
            raise DomainError("INPUT_INVALID", "Must provide either model_id or artifact_uri")

        owner = principal.subject if principal else "local"
        tenant_id = principal.tenant_id if principal else None
        base_url = os.getenv("MARKETING_MCP_PUBLIC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")

        # Delegate to app.artifacts.export_to_sandbox
        export_payload = app.artifacts.export_to_sandbox(
            ref,
            owner=owner,
            tenant_id=tenant_id,
            export_name=export_name,
            base_url=base_url,
        )
        export_payload["metadata"] = meta_info

        # Record in artifact_lifecycle for TTL tracking and server cleanup
        if hasattr(app.persistence, "metadata") and hasattr(app.persistence.metadata, "conn"):
            try:
                conn = app.persistence.metadata.conn
                now_dt = datetime.now(UTC)
                expires_dt = now_dt + timedelta(hours=24)
                conn.execute(
                    """
                    INSERT INTO artifact_lifecycle (
                        artifact_uri, status, size_bytes, sha256, exported_at, created_at, expires_at
                    ) VALUES (?, 'exported', ?, ?, ?, ?, ?)
                    ON CONFLICT(artifact_uri) DO UPDATE SET
                        status = 'exported', exported_at = excluded.exported_at, expires_at = excluded.expires_at
                    """,
                    (
                        ref.uri,
                        ref.size_bytes,
                        ref.sha256,
                        now_dt.isoformat(),
                        now_dt.isoformat(),
                        expires_dt.isoformat(),
                    ),
                )
                conn.commit()
            except Exception as exc:
                logger.warning("Failed to record artifact lifecycle", exc_info=exc, extra={"artifact_uri": ref.uri})

        return env(
            summary=export_payload,
            next_actions=["cleanup_server_storage"],
        )

    @mcp.tool(
        name="cleanup_server_storage",
        description="Run server garbage collection to purge expired, delivered, or orphaned artifacts and temp files.",
    )
    @mcp_error_boundary("cleanup_server_storage", "artifacts", "gc")
    async def cleanup_server_storage(older_than_hours: int = 24, dry_run: bool = False):
        principal = resolve_context().principal
        require_scope(principal, scopes_for_tool("cleanup_server_storage")[0])

        conn = getattr(getattr(app.persistence, "metadata", None), "conn", None)
        # Delegate to app.artifacts.cleanup_storage
        report = app.artifacts.cleanup_storage(
            older_than_hours=older_than_hours,
            dry_run=dry_run,
            metadata_conn=conn,
        )

        return env(
            summary=report,
            next_actions=["list_jobs"],
        )
