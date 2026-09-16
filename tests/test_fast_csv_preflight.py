"""Tests and benchmarks for Rust SIMD CSV preflight engine."""

from __future__ import annotations

import time
import pytest

from marketing_mcp.accelerators import fast_sniff_and_validate_csv, is_rust_accelerated


def test_fast_sniff_valid_csv():
    csv_data = (
        b"date,sales,meta_spend,google_spend\n"
        b"2023-01-01,100.5,10.0,20.0\n"
        b"2023-01-08,120.0,15.0,25.0\n"
        b"2023-01-15,110.0,12.0,22.0\n"
        b"2023-01-22,130.0,18.0,28.0\n"
        b"2023-01-29,140.0,20.0,30.0\n"
        b"2023-02-05,150.0,22.0,32.0\n"
        b"2023-02-12,160.0,25.0,35.0\n"
        b"2023-02-19,155.0,24.0,34.0\n"
        b"2023-02-26,170.0,28.0,38.0\n"
        b"2023-03-05,180.0,30.0,40.0\n"
        b"2023-03-12,175.0,29.0,39.0\n"
        b"2023-03-19,190.0,32.0,42.0\n"
        b"2023-03-26,195.0,35.0,45.0\n"
        b"2023-04-02,200.0,38.0,48.0\n"
    )

    result = fast_sniff_and_validate_csv(
        csv_data,
        date_col="date",
        target_col="sales",
        channel_cols=["meta_spend", "google_spend"],
    )

    assert result["row_count"] == 14
    assert result["is_valid_for_modeling"] is True
    assert result["validation_errors"] == []
    assert result["date_min"] == "2023-01-01"
    assert result["date_max"] == "2023-04-02"
    assert "sales" in result["columns"]
    assert result["columns"]["sales"]["detected_type"] == "numeric"
    assert result["columns"]["sales"]["null_count"] == 0
    assert result["columns"]["sales"]["min"] == pytest.approx(100.5)


def test_fast_sniff_negative_spend_rejection():
    csv_data = (
        b"date,sales,spend\n"
        b"2023-01-01,100.0,-50.0\n"  # Invalid negative spend!
        b"2023-01-08,120.0,20.0\n"
    )
    result = fast_sniff_and_validate_csv(
        csv_data,
        date_col="date",
        target_col="sales",
        channel_cols=["spend"],
    )
    assert result["is_valid_for_modeling"] is False
    assert any("negative spend" in err for err in result["validation_errors"])


def test_fast_sniff_missing_columns():
    csv_data = b"date,spend\n2023-01-01,50.0\n"
    result = fast_sniff_and_validate_csv(
        csv_data,
        date_col="date",
        target_col="nonexistent_target",
        channel_cols=["nonexistent_channel"],
    )
    assert result["is_valid_for_modeling"] is False
    assert any("Missing target column" in err for err in result["validation_errors"])
    assert any("Missing channel column" in err for err in result["validation_errors"])


def test_benchmark_synthetic_large_csv():
    # Build 3000 rows x 10 columns
    lines = ["date,revenue,c1,c2,c3,c4,c5,c6,c7,c8"]
    for i in range(3000):
        lines.append(f"2023-01-01,{1000.0 + i},{i*1.0},{i*1.5},{i*2.0},{i*2.5},{i*3.0},{i*3.5},{i*4.0},{i*4.5}")
    big_csv = "\n".join(lines).encode("utf-8")

    t0 = time.perf_counter()
    result = fast_sniff_and_validate_csv(
        big_csv,
        date_col="date",
        target_col="revenue",
        channel_cols=["c1", "c2", "c3"],
    )
    elapsed = time.perf_counter() - t0

    assert result["row_count"] == 3000
    assert result["is_valid_for_modeling"] is True
    print(f"\n[Benchmark] 3000 rows x 10 columns validated in {elapsed*1000:.2f}ms (Rust active: {is_rust_accelerated()})")
    # Rust should comfortably process 3000 rows in < 25ms
    if is_rust_accelerated():
        assert elapsed < 0.05
