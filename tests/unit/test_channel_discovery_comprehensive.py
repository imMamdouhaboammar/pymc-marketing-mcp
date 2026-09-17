import pandas as pd
import pytest
from marketing_mcp.scientific.datasets import inspect_dataset_frame

def test_channel_discovery_detects_all_six_platforms():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="D"),
        "revenue_usd": [100.0] * 60,
        "google": [10.0] * 60,
        "meta": [12.0] * 60,
        "tiktok": [8.0] * 60,
        "linkedin": [5.0] * 60,
        "snapchat": [7.0] * 60,
        "x": [6.0] * 60,
    })
    inspection = inspect_dataset_frame(df, dataset_id="test_all_channels")
    channels = set(inspection.possible_channels)
    assert {"google", "meta", "tiktok", "linkedin", "snapchat", "x"}.issubset(channels), f"Discovered channels: {channels}"

def test_long_form_dataset_detection():
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="D").repeat(6),
        "platform": ["Google Ads", "Meta Ads", "TikTok Ads", "LinkedIn Ads", "Snapchat Ads", "X Ads"] * 60,
        "market": ["Canada", "Egypt", "Saudi Arabia", "UAE", "Qatar", "UAE"] * 60,
        "spend_usd": [10.0] * 360,
        "revenue_usd": [20.0] * 360,
    })
    inspection = inspect_dataset_frame(df, dataset_id="test_long_form")
    assert inspection.is_long_form is True
    assert "platform" in inspection.detected_dimensions or "market" in inspection.detected_dimensions
    assert any("Google Ads" in ch for ch in inspection.detected_categorical_channels)

def test_dataset_service_inspect_uses_comprehensive_channel_and_long_form(tmp_path):
    from marketing_mcp.storage.metadata import SQLiteMetadataStore
    from marketing_mcp.storage.artifacts import LocalArtifactStore
    from marketing_mcp.services.dataset_service import DatasetService

    csv = tmp_path / "all_channels.csv"
    pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=60, freq="D"),
        "revenue_usd": [100.0] * 60,
        "google": [10.0] * 60,
        "meta": [12.0] * 60,
        "tiktok": [8.0] * 60,
        "linkedin": [5.0] * 60,
        "snapchat": [7.0] * 60,
        "x": [6.0] * 60,
    }).to_csv(csv, index=False)

    metadata = SQLiteMetadataStore(tmp_path / "meta.db")
    blobs = LocalArtifactStore(tmp_path / "objects")
    service = DatasetService(metadata, blobs, max_dataset_mb=10)
    registered = service.register_file(csv)
    inspection = service.inspect(registered.dataset_id)

    channels = set(inspection.possible_channels)
    assert {"google", "meta", "tiktok", "linkedin", "snapchat", "x"}.issubset(channels), f"Discovered channels: {channels}"

