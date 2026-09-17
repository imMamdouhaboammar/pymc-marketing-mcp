from __future__ import annotations

import json
import shutil
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketing_mcp.storage.artifacts import LocalArtifactStore


class StorageGarbageCollector:
    """Automated server garbage collector for temporary files, delivered artifacts, and orphans."""

    def __init__(self, artifacts: LocalArtifactStore, metadata_conn=None):
        self.artifacts = artifacts
        self.metadata_conn = metadata_conn

    def cleanup(
        self,
        older_than_hours: int = 24,
        dry_run: bool = False,
        clean_tmp: bool = True,
        force_unreferenced: bool = True,
    ) -> dict[str, Any]:
        cutoff_epoch = time.time() - (older_than_hours * 3600)
        freed_bytes = 0
        deleted_count = 0
        cleaned_paths: list[str] = []

        gc_errors: list[str] = []

        # 1. Clean temporary directories in system temp (/tmp/marketing-mcp-*)
        if clean_tmp:
            temp_root = Path(tempfile.gettempdir())
            for entry in temp_root.glob("marketing-mcp-*"):
                try:
                    stat = entry.stat()
                    if stat.st_mtime < cutoff_epoch or older_than_hours == 0:
                        size = 0
                        if entry.is_file():
                            size = stat.st_size
                            if not dry_run:
                                entry.unlink(missing_ok=True)
                        elif entry.is_dir():
                            for f in entry.rglob("*"):
                                if f.is_file():
                                    size += f.stat().st_size
                            if not dry_run:
                                shutil.rmtree(entry, ignore_errors=True)
                        freed_bytes += size
                        deleted_count += 1
                        cleaned_paths.append(str(entry))
                except Exception as exc:
                    gc_errors.append(f"Temp cleanup failed for {entry}: {exc}")

        # 2. Clean delivered/exported artifacts from lifecycle table
        if self.metadata_conn:
            try:
                now_iso = datetime.now(UTC).isoformat()
                rows = self.metadata_conn.execute(
                    """
                    SELECT artifact_uri, sha256 FROM artifact_lifecycle
                    WHERE status = 'exported' AND (expires_at IS NOT NULL AND expires_at <= ?)
                    """,
                    (now_iso,),
                ).fetchall()
                for r in rows:
                    uri = r["artifact_uri"]
                    digest = r["sha256"]
                    # Find and delete the blob file
                    for path in self.artifacts._blob_root.rglob(digest):
                        if path.is_file():
                            size = path.stat().st_size
                            if not dry_run:
                                path.unlink(missing_ok=True)
                            freed_bytes += size
                            deleted_count += 1
                            cleaned_paths.append(str(path))
                    if not dry_run:
                        self.metadata_conn.execute(
                            "DELETE FROM artifact_lifecycle WHERE artifact_uri = ?", (uri,)
                        )
                if not dry_run:
                    self.metadata_conn.commit()
            except Exception as exc:
                gc_errors.append(f"Lifecycle cleanup failed: {exc}")

        # 3. Clean unreferenced blobs not linked to any model, dataset, or job
        if force_unreferenced and self.metadata_conn:
            try:
                referenced_digests: set[str] = set()
                # Scan datasets
                for row in self.metadata_conn.execute("SELECT payload FROM datasets").fetchall():
                    try:
                        d = json.loads(row[0])
                        if "fingerprint" in d:
                            referenced_digests.add(d["fingerprint"])
                        if d.get("artifact_ref"):
                            referenced_digests.add(d["artifact_ref"].get("sha256", ""))
                    except Exception as exc:
                        gc_errors.append(f"Skipping corrupt dataset payload: {exc}")
                # Scan models
                for row in self.metadata_conn.execute("SELECT payload FROM models").fetchall():
                    try:
                        d = json.loads(row[0])
                        if d.get("artifact_ref"):
                            referenced_digests.add(d["artifact_ref"].get("sha256", ""))
                    except Exception as exc:
                        gc_errors.append(f"Skipping corrupt model payload: {exc}")
                # Scan jobs
                for row in self.metadata_conn.execute("SELECT result FROM jobs WHERE result IS NOT NULL").fetchall():
                    try:
                        d = json.loads(row[0])
                        if d.get("artifact_ref"):
                            referenced_digests.add(d["artifact_ref"].get("sha256", ""))
                    except Exception as exc:
                        gc_errors.append(f"Skipping corrupt job result: {exc}")

                referenced_digests.discard("")

                # Check all blobs
                if self.artifacts._blob_root.exists():
                    for blob_file in self.artifacts._blob_root.rglob("*"):
                        if blob_file.is_file():
                            digest = blob_file.name
                            if len(digest) == 64 and digest not in referenced_digests:
                                stat = blob_file.stat()
                                if stat.st_mtime < cutoff_epoch or older_than_hours == 0:
                                    size = stat.st_size
                                    if not dry_run:
                                        blob_file.unlink(missing_ok=True)
                                    freed_bytes += size
                                    deleted_count += 1
                                    cleaned_paths.append(str(blob_file))
            except Exception as exc:
                gc_errors.append(f"Unreferenced blob cleanup failed: {exc}")

        # Remaining stats
        total_remaining_bytes = 0
        remaining_files = 0
        if self.artifacts._blob_root.exists():
            for f in self.artifacts._blob_root.rglob("*"):
                if f.is_file():
                    total_remaining_bytes += f.stat().st_size
                    remaining_files += 1

        return {
            "dry_run": dry_run,
            "older_than_hours": older_than_hours,
            "deleted_files_count": deleted_count,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "remaining_blobs_count": remaining_files,
            "remaining_storage_mb": round(total_remaining_bytes / (1024 * 1024), 2),
            "cleaned_paths": cleaned_paths[:50],
            "errors": gc_errors,
        }
