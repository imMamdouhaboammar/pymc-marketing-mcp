from pathlib import Path

import pandas as pd
import pytest

from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.security.principal import Principal
from marketing_mcp.services.dataset_service import DatasetService
from marketing_mcp.storage.artifacts import LocalArtifactStore
from marketing_mcp.storage.metadata import SQLiteMetadataStore


def test_register_and_inspect_dataset(tmp_path):
    csv = tmp_path / "input.csv"
    pd.DataFrame(
        {
            "date": pd.date_range("2025-01-06", periods=60, freq="W-MON"),
            "revenue": range(60),
            "meta_spend": range(60),
            "discount": [0, 1] * 30,
        }
    ).to_csv(csv, index=False)
    store = SQLiteMetadataStore(tmp_path / "meta.db")
    service = DatasetService(store, tmp_path / "data", max_dataset_mb=10)
    registered = service.register_file(csv)
    inspection = service.inspect(registered.dataset_id)
    assert inspection.rows == 60
    assert "revenue" in inspection.possible_targets
    assert "meta_spend" in inspection.possible_channels


def test_dataset_bytes_are_shared_and_identity_is_tenant_scoped(tmp_path):
    csv = tmp_path / "input.csv"
    pd.DataFrame({"date": ["2026-01-01"], "sales": [1], "search": [2]}).to_csv(
        csv, index=False
    )
    metadata = SQLiteMetadataStore(tmp_path / "meta.db")
    blobs = LocalArtifactStore(tmp_path / "objects")
    first = DatasetService(metadata, blobs, max_dataset_mb=10)
    tenant_a = Principal(subject="analyst", auth_type="oauth", tenant_id="tenant-a")
    tenant_b = Principal(subject="analyst", auth_type="oauth", tenant_id="tenant-b")

    registered_a = first.register_file(csv, tenant_a)
    registered_b = first.register_file(csv, tenant_b)

    assert registered_a.dataset_id != registered_b.dataset_id
    assert not Path(registered_a.path).is_absolute()
    stored = metadata.get_dataset(registered_a.dataset_id)
    assert stored["blob"]["sha256"] == registered_a.fingerprint
    second = DatasetService(metadata, LocalArtifactStore(tmp_path / "objects"), max_dataset_mb=10)
    assert second.load(registered_a.dataset_id).to_dict("records") == [
        {"date": "2026-01-01", "sales": 1, "search": 2}
    ]

    ref = ArtifactRef(**stored["blob"])
    blobs.object_path(ref).write_bytes(b"tampered")
    with pytest.raises(Exception, match="integrity"):
        second.load(registered_a.dataset_id)
