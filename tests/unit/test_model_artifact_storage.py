"""Shared immutable MMM artifact publication and materialization."""

from pathlib import Path
from types import SimpleNamespace

from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.principal import Principal
from marketing_mcp.services.modeling_service import ModelingService
from marketing_mcp.storage.artifacts import LocalArtifactStore
from marketing_mcp.storage.metadata import SQLiteMetadataStore


class DatasetDouble:
    def validate(self, *args, **kwargs):
        return SimpleNamespace(valid_for_modeling=True, findings=[])

    def load(self, dataset_id):
        return {"dataset_id": dataset_id}


class AdapterDouble:
    def versions(self):
        return {"adapter": "test"}

    def fit(self, dataframe, config, path, lift_df=None):
        Path(path).write_bytes(b"immutable-model")

    def load(self, path):
        return Path(path).read_bytes()


def test_model_uploads_shared_ref_and_materializes_for_load(tmp_path):
    metadata = SQLiteMetadataStore(tmp_path / "metadata.db")
    metadata.put_dataset({"dataset_id": "dataset-1", "fingerprint": "fp"})
    blobs = LocalArtifactStore(tmp_path / "objects")
    first = ModelingService(metadata, blobs, DatasetDouble(), AdapterDouble)
    config = FitMMMInput(
        dataset_id="dataset-1",
        date_column="date",
        target_column="sales",
        channel_columns=["search"],
    )
    record = first.fit(
        config,
        Principal(subject="analyst", auth_type="oauth", tenant_id="tenant-a"),
    )

    stored = metadata.get_model(record.model_id)
    assert stored["artifact_ref"]["sha256"]
    assert stored["artifact_path"].startswith("blob://")
    second = ModelingService(
        metadata,
        LocalArtifactStore(tmp_path / "objects"),
        DatasetDouble(),
        AdapterDouble,
    )
    with second.materialized_model(record.model_id) as (model, reloaded):
        assert model == b"immutable-model"
        assert reloaded.tenant_id == "tenant-a"
