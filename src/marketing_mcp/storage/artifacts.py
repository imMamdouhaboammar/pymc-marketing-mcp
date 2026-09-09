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
            temporary.chmod(0o600)
            try:
                os.link(temporary, destination)
            except FileExistsError:
                self._verify_path(destination, ref)
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
        return self.put_bytes(
            Path(source).read_bytes(),
            content_type=content_type,
            owner=owner,
            tenant_id=tenant_id,
        )

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
    def _verify_path(path: Path, ref: ArtifactRef) -> bytes:
        if not path.is_file():
            raise DomainError("BROKEN_ARTIFACT", "The artifact is missing")
        data = path.read_bytes()
        if len(data) != ref.size_bytes or hashlib.sha256(data).hexdigest() != ref.sha256:
            raise DomainError("BROKEN_ARTIFACT", "Artifact integrity verification failed")
        return data

    @staticmethod
    def _authorize(ref: ArtifactRef, *, owner: str, tenant_id: str | None) -> None:
        if ref.owner != owner or ref.tenant_id != tenant_id:
            raise DomainError("AUTH_FORBIDDEN", "Artifact access is not permitted")

    def read_bytes(self, ref: ArtifactRef, *, owner: str, tenant_id: str | None) -> bytes:
        self._authorize(ref, owner=owner, tenant_id=tenant_id)
        return self._verify_path(self.object_path(ref), ref)

    @contextmanager
    def materialize(
        self,
        ref: ArtifactRef,
        *,
        owner: str,
        tenant_id: str | None,
        suffix: str = "",
    ) -> Iterator[Path]:
        data = self.read_bytes(ref, owner=owner, tenant_id=tenant_id)
        with tempfile.TemporaryDirectory(prefix="marketing-mcp-artifact-") as directory:
            path = Path(directory) / f"artifact{suffix}"
            path.write_bytes(data)
            path.chmod(0o600)
            yield path

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
