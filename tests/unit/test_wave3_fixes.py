import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset


def test_validate_mmm_dataset_detects_daily_time_series_gaps():
    """Wave 3: validate_mmm_dataset must detect missing daily dates and surface MISSING_PERIODS."""
    # 243 calendar days but only 234 observed (9 days missing)
    full_dates = pd.date_range("2026-01-01", periods=243, freq="D")
    # Drop 9 dates
    drop_indices = [10, 25, 50, 75, 100, 125, 150, 175, 200]
    observed_dates = full_dates.delete(drop_indices)

    df = pd.DataFrame({
        "date": observed_dates,
        "revenue": [1000.0] * len(observed_dates),
        "channel_a": [100.0] * len(observed_dates),
        "control_a": [1.0] * len(observed_dates),
    })

    findings = validate_mmm_dataset(
        df=df,
        date_column="date",
        target_column="revenue",
        channel_columns=["channel_a"],
        control_columns=["control_a"],
    )

    missing_findings = [f for f in findings if f.code == "MISSING_PERIODS"]
    assert len(missing_findings) == 1, "Expected MISSING_PERIODS warning for 9 daily calendar gaps"
    f = missing_findings[0]
    assert f.evidence.get("missing_count") == 9
    assert f.evidence.get("frequency") == "daily"
    assert f.evidence.get("observed_periods") == 234
    assert f.evidence.get("expected_periods") == 243


def test_validate_dataset_exposes_temporal_summary_in_result(tmp_path):
    """Section 18: DatasetValidationResult exposes frequency, observed, expected, and missing period counts."""
    from marketing_mcp.app import Application
    from marketing_mcp.config import Settings

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path / "inbox",
        max_dataset_mb=10,
        auth_enabled=False,
    )
    app = Application(settings)

    full_dates = pd.date_range("2026-01-01", periods=243, freq="D")
    drop_indices = [10, 25, 50, 75, 100, 125, 150, 175, 200]
    observed_dates = full_dates.delete(drop_indices)
    df = pd.DataFrame({
        "date": observed_dates.strftime("%Y-%m-%d"),
        "revenue": [1000.0] * len(observed_dates),
        "channel_a": [100.0] * len(observed_dates),
    })
    csv_bytes = df.to_csv(index=False).encode()
    reg = app.datasets.register_bytes(csv_bytes, filename="panel.csv")

    val_res = app.datasets.validate(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["channel_a"],
        control_columns=[],
    )

    assert val_res.temporal_summary is not None
    assert val_res.temporal_summary["frequency"] == "daily"
    assert val_res.temporal_summary["observed_periods"] == 234
    assert val_res.temporal_summary["expected_periods"] == 243
    assert val_res.temporal_summary["missing_period_count"] == 9
