"""End-to-end integration test for Rust-accelerated MCP server tools."""

from __future__ import annotations

import pytest

from marketing_mcp.accelerators import get_engine_info, is_rust_accelerated
from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server


@pytest.fixture
def mcp_app(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
    )
    return Application(settings)


@pytest.mark.skipif(
    not is_rust_accelerated(),
    reason="Requires compiled marketing_mcp_fast Rust extension",
)
def test_rust_acceleration_active():
    info = get_engine_info()
    assert is_rust_accelerated() is True
    assert info["rust_accelerated"] is True
    assert info["backend"] == "rust-native"


def test_e2e_mcp_dataset_registration_with_rust(mcp_app):
    create_server(mcp_app)

    # Ingest a sample CSV via direct content payload
    sample_csv = (
        "date,revenue,facebook,google\n"
        "2023-01-01,1000.0,200.0,300.0\n"
        "2023-01-08,1100.0,220.0,310.0\n"
        "2023-01-15,1050.0,210.0,305.0\n"
        "2023-01-22,1200.0,250.0,350.0\n"
        "2023-01-29,1300.0,270.0,380.0\n"
        "2023-02-05,1250.0,260.0,360.0\n"
        "2023-02-12,1400.0,300.0,400.0\n"
        "2023-02-19,1350.0,290.0,390.0\n"
        "2023-02-26,1500.0,320.0,420.0\n"
        "2023-03-05,1600.0,350.0,450.0\n"
        "2023-03-12,1550.0,340.0,440.0\n"
        "2023-03-19,1700.0,380.0,480.0\n"
        "2023-03-26,1750.0,390.0,490.0\n"
        "2023-04-02,1800.0,400.0,500.0\n"
    )

    # Call register_dataset directly
    res = mcp_app.datasets.register_bytes(sample_csv.encode("utf-8"), format="csv")
    assert res.dataset_id is not None
    assert res.rows == 14
    assert res.format == "csv"

    # Inspect the dataset
    inspection = mcp_app.datasets.inspect(res.dataset_id)
    assert inspection.dataset_id == res.dataset_id
    assert inspection.rows == 14
    assert "revenue" in inspection.possible_targets
    assert "facebook" in inspection.possible_channels
    assert "google" in inspection.possible_channels
