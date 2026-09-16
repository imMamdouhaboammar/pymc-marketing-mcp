from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.security import safe_identifier


class LocalArtifactStore:
    """Filesystem implementation of the provider-neutral immutable blob contract."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._blob_root = self.root / "blobs"
        self._blob_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _namespace(owner: str, tenant_id: str | None) -> str:
        identity = f"{tenant_id or 'local'}\0{owner}".encode()
        return hashlib.sha256(identity).hexdigest()[:24]

    def put_bytes(
        self,
        data: bytes,
        *,
        content_type: str,
        owner: str,
        tenant_id: str | None,
    ) -> ArtifactRef:
        digest = hashlib.sha256(data).hexdigest()
        namespace = self._namespace(owner, tenant_id)
        destination = self._blob_root / namespace / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        ref = ArtifactRef(
            uri=f"blob://{namespace}/{digest}",
            sha256=digest,
            size_bytes=len(data),
            version=digest,
            content_type=content_type,
            owner=owner,
            tenant_id=tenant_id,
        )
        if destination.exists():
            self._verify_path(destination, ref)
            return ref

        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            try:
                os.link(temporary, destination)
            except FileExistsError:
                self._verify_path(destination, ref)
            except OSError:
                # GCS FUSE or object storage filesystems do not support hardlinks (Errno 38 / 95)
                try:
                    os.replace(temporary, destination)
                except OSError:
                    import shutil

                    shutil.move(str(temporary), str(destination))
        finally:
            temporary.unlink(missing_ok=True)
        return ref

    def put_file(
        self,
        source: Path,
        *,
        content_type: str,
        owner: str,
        tenant_id: str | None,
    ) -> ArtifactRef:
        src = Path(source)
        if not src.is_file():
            raise DomainError("BROKEN_ARTIFACT", f"Source file does not exist: {source}")

        # Stream-hash in 1MB chunks to prevent memory spikes on 1GB files
        hasher = hashlib.sha256()
        size_bytes = 0
        with src.open("rb") as f:
            while chunk := f.read(1048576):
                hasher.update(chunk)
                size_bytes += len(chunk)
        digest = hasher.hexdigest()
        namespace = self._namespace(owner, tenant_id)
        destination = self._blob_root / namespace / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        ref = ArtifactRef(
            uri=f"blob://{namespace}/{digest}",
            sha256=digest,
            size_bytes=size_bytes,
            version=digest,
            content_type=content_type,
            owner=owner,
            tenant_id=tenant_id,
        )
        if destination.exists():
            self._verify_file_integrity(destination, ref)
            return ref

        import shutil

        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copyfile(src, temporary)
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            try:
                os.link(temporary, destination)
            except (FileExistsError, OSError):
                try:
                    os.replace(temporary, destination)
                except OSError:
                    shutil.move(str(temporary), str(destination))
        finally:
            temporary.unlink(missing_ok=True)
        return ref

    def object_path(self, ref: ArtifactRef) -> Path:
        prefix = "blob://"
        if not ref.uri.startswith(prefix):
            raise DomainError("BROKEN_ARTIFACT", "Unsupported artifact reference")
        parts = ref.uri[len(prefix) :].split("/")
        if len(parts) != 2 or any(not part or not part.isalnum() for part in parts):
            raise DomainError("BROKEN_ARTIFACT", "Malformed artifact reference")
        namespace, digest = parts
        if namespace != self._namespace(ref.owner, ref.tenant_id) or digest != ref.sha256:
            raise DomainError("BROKEN_ARTIFACT", "Artifact reference identity is inconsistent")
        return self._blob_root / namespace / digest

    @staticmethod
    def _verify_file_integrity(path: Path, ref: ArtifactRef) -> None:
        if not path.is_file():
            raise DomainError("BROKEN_ARTIFACT", "The artifact is missing")
        stat = path.stat()
        if stat.st_size != ref.size_bytes:
            raise DomainError("BROKEN_ARTIFACT", "Artifact integrity verification failed")
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(1048576):
                hasher.update(chunk)
        if hasher.hexdigest() != ref.sha256:
            raise DomainError("BROKEN_ARTIFACT", "Artifact integrity verification failed")

    @classmethod
    def _verify_path(cls, path: Path, ref: ArtifactRef) -> bytes:
        cls._verify_file_integrity(path, ref)
        return path.read_bytes()

    @staticmethod
    def _authorize(ref: ArtifactRef, *, owner: str, tenant_id: str | None) -> None:
        if ref.owner != owner or ref.tenant_id != tenant_id:
            raise DomainError("AUTH_FORBIDDEN", "Artifact access is not permitted")

    def read_bytes(self, ref: ArtifactRef, *, owner: str, tenant_id: str | None) -> bytes:
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        return self._verify_path(self.object_path(ref), ref)

    def read_chunks(
        self,
        ref: ArtifactRef,
        *,
        owner: str,
        tenant_id: str | None,
        chunk_size: int = 1048576,
        start_byte: int = 0,
        end_byte: int | None = None,
    ) -> Iterator[bytes]:
        """Stream chunks from disk without reading the whole artifact into memory."""
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        path = self.object_path(ref)
        if not path.is_file():
            raise DomainError("BROKEN_ARTIFACT", "The artifact is missing")
        with path.open("rb") as f:
            if start_byte > 0:
                f.seek(start_byte)
            remaining = (end_byte - start_byte + 1) if end_byte is not None else None
            while True:
                read_len = chunk_size if remaining is None else min(chunk_size, remaining)
                if read_len <= 0:
                    break
                chunk = f.read(read_len)
                if not chunk:
                    break
                if remaining is not None:
                    remaining -= len(chunk)
                yield chunk

    @contextmanager
    def materialize(
        self,
        ref: ArtifactRef,
        *,
        owner: str,
        tenant_id: str | None,
        suffix: str = "",
    ) -> Iterator[Path]:
        """Materialize artifact without copying 1GB files into RAM."""
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        path = self.object_path(ref)
        self._verify_file_integrity(path, ref)

        # Zero-copy optimization: If path already satisfies suffix, yield it directly
        if not suffix or path.name.endswith(suffix):
            yield path
            return

        # Use temporary symlink to avoid disk I/O and RAM bloat on 1GB files
        import shutil

        with tempfile.TemporaryDirectory(prefix="marketing-mcp-artifact-") as directory:
            symlink_path = Path(directory) / f"artifact{suffix}"
            try:
                symlink_path.symlink_to(path.resolve())
                yield symlink_path
            except OSError:
                # Filesystem doesn't support symlink: stream-copy without loading to memory
                shutil.copyfile(path, symlink_path)
                try:
                    symlink_path.chmod(0o600)
                except OSError:
                    pass
                yield symlink_path

    def generate_signed_url(
        self,
        ref: ArtifactRef,
        *,
        owner: str,
        tenant_id: str | None,
        expires_in_seconds: int = 3600,
        bucket_name: str | None = None,
    ) -> str | None:
        """Generate signed GCS download URL when Cloud Storage is configured."""
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        bucket = bucket_name or os.getenv("GCS_BUCKET_NAME")
        if not bucket:
            return None
        try:
            from datetime import timedelta
            from google.cloud import storage

            client = storage.Client()
            gcs_bucket = client.bucket(bucket)
            blob_name = f"artifacts/{self._namespace(ref.owner, ref.tenant_id)}/{ref.sha256}"
            blob = gcs_bucket.blob(blob_name)
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=expires_in_seconds),
                method="GET",
            )
        except Exception:
            return None

    def export_to_sandbox(
        self,
        ref: ArtifactRef,
        *,
        owner: str,
        tenant_id: str | None,
        export_name: str | None = None,
        base_url: str = "http://127.0.0.1:8080",
        api_key: str = "",
    ) -> dict[str, Any]:
        """Stage artifact for AI client sandbox download with streaming URL and verification command."""
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        path = self.object_path(ref)
        if not path.is_file():
            raise DomainError("ARTIFACT_NOT_FOUND", f"Artifact at {ref.uri} does not exist")

        signed_url = self.generate_signed_url(ref, owner=owner, tenant_id=tenant_id)
        namespace = self._namespace(ref.owner, ref.tenant_id)
        base = base_url.rstrip("/")
        stream_url = f"{base}/artifacts/{namespace}/{ref.sha256}/download"
        download_url = signed_url or stream_url
        safe_name = export_name or f"artifact_{ref.sha256[:12]}.bin"

        auth_header = f' -H "Authorization: Bearer {api_key}"' if api_key and not signed_url else ""
        curl_cmd = f'curl -fSL{auth_header} "{download_url}" -o "{safe_name}"'
        python_snippet = (
            f"import urllib.request, shutil\n"
            f"url = '{download_url}'\n"
            f"headers = {{'Authorization': 'Bearer {api_key}'}} if '{api_key}' and not '{bool(signed_url)}' else {{}}\n"
            f"req = urllib.request.Request(url, headers=headers)\n"
            f"with urllib.request.urlopen(req) as resp, open('{safe_name}', 'wb') as f:\n"
            f"    shutil.copyfileobj(resp, f)\n"
            f"print('Successfully downloaded {safe_name}')"
        )
        return {
            "artifact_uri": ref.uri,
            "filename": safe_name,
            "size_bytes": ref.size_bytes,
            "size_mb": round(ref.size_bytes / (1024 * 1024), 2),
            "sha256": ref.sha256,
            "download_url": download_url,
            "is_signed_url": bool(signed_url),
            "sandbox_curl_command": curl_cmd,
            "python_snippet": python_snippet,
            "delivery_status": "staged_for_sandbox_delivery",
            "retention_policy": "Auto-cleanup scheduled in 24 hours via server GC",
        }

    def cleanup_storage(
        self,
        older_than_hours: int = 24,
        dry_run: bool = False,
        metadata_conn=None,
    ) -> dict[str, Any]:
        """Run garbage collection across temporary files and unreferenced/delivered blobs."""
        from marketing_mcp.storage.gc import StorageGarbageCollector

        gc = StorageGarbageCollector(self, metadata_conn=metadata_conn)
        return gc.cleanup(older_than_hours=older_than_hours, dry_run=dry_run)

    def probe(self) -> None:
        if not self.root.is_dir() or not os.access(self.root, os.R_OK | os.W_OK):
            raise DomainError("DEPENDENCY_UNAVAILABLE", "Artifact storage is unavailable")

    # Legacy local model-path API retained until all model records are migrated to ArtifactRef.
    def model_path(self, model_id: str) -> Path:
        safe_identifier(model_id, "model")
        return self.root / f"{model_id}.nc"

    def require(self, model_id: str) -> Path:
        path = self.model_path(model_id)
        if not path.exists():
            raise DomainError("BROKEN_ARTIFACT", "The fitted model artifact is missing")
        return path
