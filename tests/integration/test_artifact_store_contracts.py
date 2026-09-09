"""Provider-neutral immutable blob-store contract using the local test adapter."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.storage.artifacts import LocalArtifactStore


def test_immutable_blob_round_trip_and_tenant_authorization(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "objects")
    ref = store.put_bytes(
        b"shared immutable bytes",
        content_type="text/csv",
        owner="analyst",
        tenant_id="tenant-a",
    )

    assert ref.sha256 == hashlib.sha256(b"shared immutable bytes").hexdigest()
    assert ref.size_bytes == len(b"shared immutable bytes")
    assert ref.version
    assert not Path(ref.uri).is_absolute()
    duplicate = store.put_bytes(
        b"shared immutable bytes",
        content_type="text/csv",
        owner="analyst",
        tenant_id="tenant-a",
    )
    assert duplicate == ref
    assert store.read_bytes(ref, owner="analyst", tenant_id="tenant-a") == b"shared immutable bytes"

    with pytest.raises(DomainError) as forbidden:
        store.read_bytes(ref, owner="attacker", tenant_id="tenant-b")
    assert forbidden.value.code == "AUTH_FORBIDDEN"


def test_blob_checksum_and_materialization_fail_closed(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "objects")
    ref = store.put_bytes(
        b"model-bytes",
        content_type="application/x-netcdf",
        owner="analyst",
        tenant_id="tenant-a",
    )
    object_path = store.object_path(ref)
    object_path.write_bytes(b"corrupt")

    with pytest.raises(DomainError) as broken:
        store.read_bytes(ref, owner="analyst", tenant_id="tenant-a")
    assert broken.value.code == "BROKEN_ARTIFACT"

    clean = store.put_bytes(
        b"fresh-model",
        content_type="application/x-netcdf",
        owner="analyst",
        tenant_id="tenant-a",
    )
    materialized: Path | None = None
    with store.materialize(clean, owner="analyst", tenant_id="tenant-a", suffix=".nc") as path:
        materialized = path
        assert path.read_bytes() == b"fresh-model"
        assert path.stat().st_mode & 0o077 == 0
    assert materialized is not None and not materialized.exists()
