from marketing_mcp.storage.metadata import SQLiteMetadataStore


def test_metadata_survives_reopen(tmp_path):
    db = tmp_path / "metadata.db"
    s = SQLiteMetadataStore(db)
    s.put_dataset(
        {
            "dataset_id": "dataset_1",
            "path": "x.csv",
            "fingerprint": "abc",
            "format": "csv",
            "rows": 10,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    s.close()
    s2 = SQLiteMetadataStore(db)
    assert s2.get_dataset("dataset_1")["fingerprint"] == "abc"
