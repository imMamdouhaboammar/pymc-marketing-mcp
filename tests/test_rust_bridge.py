"""Tests for the Rust accelerator bridge and fallback mechanism."""

from __future__ import annotations

import pytest

from marketing_mcp.accelerators import (
    compress_curve_lttb,
    fast_compute_quantiles,
    fast_mcmc_diagnostics,
    fast_serialize_json,
    fast_sniff_and_validate_csv,
    generate_sparkline,
    get_engine_info,
    is_rust_accelerated,
)


def test_engine_info():
    info = get_engine_info()
    assert isinstance(info, dict)
    assert "rust_accelerated" in info
    assert "version" in info
    assert info["rust_accelerated"] == is_rust_accelerated()


def test_sparkline_generation():
    values = [1.0, 2.5, 5.0, 8.0, 10.0, 4.0, 1.0]
    spark = generate_sparkline(values)
    assert isinstance(spark, str)
    assert len(spark) == len(values)
    # Ensure standard unicode block elements are used
    assert all(c in " ▂▃▄▅▆▇█" for c in spark)


def test_quantiles_computation():
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    qs = [0.03, 0.5, 0.97]
    result = fast_compute_quantiles(data, qs)
    assert "mean" in result
    assert "quantiles" in result
    assert len(result["quantiles"]) == 3
    assert result["quantiles"][1] == pytest.approx(5.5, abs=0.5)


def test_curve_lttb_compression():
    # 100 points compressed to 10 points
    xs = [float(i) for i in range(100)]
    ys = [float(i * 2) for i in range(100)]
    downsampled_x, downsampled_y = compress_curve_lttb(xs, ys, max_points=10)
    assert len(downsampled_x) == 10
    assert len(downsampled_y) == 10
    assert downsampled_x[0] == 0.0
    assert downsampled_x[-1] == 99.0


def test_fast_serialize_json():
    payload = {"status": "ok", "count": 42, "channels": ["meta", "google"]}
    serialized = fast_serialize_json(payload)
    assert isinstance(serialized, str)
    assert '"status":"ok"' in serialized or '"status": "ok"' in serialized
    assert '"count":42' in serialized or '"count": 42' in serialized


def test_pure_python_fallback_parity(monkeypatch):
    import marketing_mcp.accelerators as acc

    # Force Python fallback
    monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", False)

    # 1. Info reflects fallback
    info = acc.get_engine_info()
    assert info["rust_accelerated"] is False
    assert info["backend"] == "python-standard"

    # 2. Sparkline parity
    values = [1.0, 2.5, 5.0, 8.0, 10.0, 4.0, 1.0]
    spark = acc.generate_sparkline(values)
    assert len(spark) == len(values)
    assert all(c in " ▂▃▄▅▆▇█" for c in spark)

    # 3. Quantiles parity
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    res = acc.fast_compute_quantiles(data, [0.03, 0.5, 0.97])
    assert "mean" in res
    assert len(res["quantiles"]) == 3
    assert res["quantiles"][1] == pytest.approx(5.5, abs=0.5)

    # 4. LTTB parity
    xs = [float(i) for i in range(100)]
    ys = [float(i * 2) for i in range(100)]
    down_x, down_y = acc.compress_curve_lttb(xs, ys, max_points=10)
    assert len(down_x) == 10
    assert len(down_y) == 10
