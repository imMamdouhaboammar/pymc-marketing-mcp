import numpy as np
import pandas as pd
import pytest

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset
from marketing_mcp.domain.decisions.allocation import build_budget_bounds
from marketing_mcp.errors import DomainError
from marketing_mcp.security import safe_identifier, safe_ingest_path, safe_source_path


def test_failure_insufficient_history():
    """Dataset with fewer than 52 weeks must produce INSUFFICIENT_DATA error."""
    dates = pd.date_range("2023-01-01", periods=30, freq="W-MON")
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": np.random.uniform(100, 200, 30),
            "meta": np.random.uniform(10, 20, 30),
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    codes = [f.code for f in findings]
    assert "INSUFFICIENT_DATA" in codes
    f = next(f for f in findings if f.code == "INSUFFICIENT_DATA")
    assert f.severity == "error"
    assert f.evidence["time_periods"] == 30


def test_failure_invalid_dates():
    """Dataset with non-date strings must produce INVALID_DATE error."""
    df = pd.DataFrame(
        {
            "date": ["not_a_date"] * 60,
            "revenue": np.random.uniform(100, 200, 60),
            "meta": np.random.uniform(10, 20, 60),
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    assert any(f.code == "INVALID_DATE" for f in findings)


def test_failure_duplicate_period():
    """Duplicate dates in single-dimensional dataset must produce DUPLICATE_PERIOD error."""
    base_dates = list(pd.date_range("2023-01-01", periods=59, freq="W-MON"))
    dates = base_dates + [base_dates[0]]
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": np.random.uniform(100, 200, 60),
            "meta": np.random.uniform(10, 20, 60),
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    assert any(f.code == "DUPLICATE_PERIOD" for f in findings)


def test_failure_negative_media_spend():
    """Negative media spend values must produce NEGATIVE_MEDIA error."""
    dates = pd.date_range("2023-01-01", periods=60, freq="W-MON")
    meta = np.random.uniform(10, 20, 60)
    meta[5] = -50.0
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": np.random.uniform(100, 200, 60),
            "meta": meta,
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    assert any(f.code == "NEGATIVE_MEDIA" for f in findings)


def test_failure_constant_channel_variance():
    """Channel with zero spend variance must produce NO_SPEND_VARIATION error."""
    dates = pd.date_range("2023-01-01", periods=60, freq="W-MON")
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": np.random.uniform(100, 200, 60),
            "meta": [100.0] * 60,
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    assert any(f.code == "NO_SPEND_VARIATION" for f in findings)


def test_failure_extreme_channel_correlation():
    """Collinear channels (corr >= 0.90) must produce HIGH_CHANNEL_CORRELATION warning."""
    dates = pd.date_range("2023-01-01", periods=60, freq="W-MON")
    meta = np.random.uniform(10, 100, 60)
    google = meta * 1.5 + np.random.normal(0, 0.01, 60)
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": np.random.uniform(100, 200, 60),
            "meta": meta,
            "google": google,
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta", "google"], [])
    assert any(f.code == "HIGH_CHANNEL_CORRELATION" for f in findings)


def test_failure_bad_target():
    """Target with <= 2 unique values must produce BAD_TARGET error."""
    dates = pd.date_range("2023-01-01", periods=60, freq="W-MON")
    df = pd.DataFrame(
        {
            "date": dates,
            "revenue": [1.0, 2.0] * 30,
            "meta": np.random.uniform(10, 20, 60),
        }
    )
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [])
    assert any(f.code == "BAD_TARGET" for f in findings)


def test_failure_non_rectangular_panel():
    """Multidimensional panel with missing dates for a dimension must produce NON_RECTANGULAR_PANEL error."""
    dates1 = pd.date_range("2023-01-01", periods=60, freq="W-MON")
    dates2 = pd.date_range("2023-01-01", periods=55, freq="W-MON")  # missing 5 dates
    df1 = pd.DataFrame({"date": dates1, "geo": "Riyadh", "revenue": 100, "meta": 10})
    df2 = pd.DataFrame({"date": dates2, "geo": "Jeddah", "revenue": 100, "meta": 10})
    df = pd.concat([df1, df2], ignore_index=True)
    findings = validate_mmm_dataset(df, "date", "revenue", ["meta"], [], dims=["geo"])
    assert any(f.code == "NON_RECTANGULAR_PANEL" for f in findings)


def test_failure_impossible_budget_constraints():
    """Constraints where min > budget must fail validation."""

    class FakeModel:
        def __init__(self):
            self.channel_columns = ["meta", "google"]
            self.dims = ()

    with pytest.raises(DomainError) as exc_info:
        build_budget_bounds(
            FakeModel(),
            budget=100_000.0,
            channel_constraints={"meta": {"min": 80_000.0}, "google": {"min": 30_000.0}},
            cell_constraints=[],
        )
    assert exc_info.value.code == "INVALID_CONSTRAINT"


def test_failure_security_path_traversal(tmp_path):
    """Path traversal attempts outside ingest root must be rejected."""
    ingest = tmp_path / "inbox"
    ingest.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("a,b\n1,2")

    with pytest.raises(DomainError) as exc_info:
        safe_ingest_path(outside, ingest, max_bytes=10_000_000)
    assert exc_info.value.code == "PATH_NOT_ALLOWED"


def test_failure_security_invalid_identifier():
    """Identifiers with special characters or path separators must be rejected."""
    with pytest.raises(DomainError) as exc_info:
        safe_identifier("../../../etc/passwd", "model")
    assert exc_info.value.code == "INVALID_IDENTIFIER"


def test_failure_security_unsupported_file_extension(tmp_path):
    """Non CSV/Parquet files must be rejected."""
    bad_file = tmp_path / "model.pkl"
    bad_file.write_text("fake pickle")
    with pytest.raises(DomainError) as exc_info:
        safe_source_path(bad_file, max_bytes=10_000_000)
    assert exc_info.value.code == "UNSUPPORTED_DATASET_FORMAT"
