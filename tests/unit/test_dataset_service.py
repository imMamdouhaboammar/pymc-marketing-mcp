import pandas as pd

from marketing_mcp.services.dataset_service import DatasetService
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
