"""Tests for the Rust accelerator bridge and fallback mechanism."""

from __future__ import annotations

import math

import pytest

from marketing_mcp.accelerators import (
    compress_curve_lttb,
    fast_compute_quantiles,
    fast_serialize_json,
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


def test_quantiles_edge_cases_and_numpy_parity():
    import numpy as np

    # 1. NaN and Inf handling
    data = [1.0, float("nan"), 2.0, float("inf"), float("-inf"), 3.0, 4.0, 5.0]
    qs = [0.0, 0.25, 0.5, 0.75, 1.0]
    res = fast_compute_quantiles(data, qs)
    assert res["count"] == 5  # Only finite values counted
    assert res["mean"] == pytest.approx(3.0)
    assert res["min"] == 1.0
    assert res["max"] == 5.0
    expected_qs = np.quantile([1.0, 2.0, 3.0, 4.0, 5.0], qs, method="linear").tolist()
    for observed, expected in zip(res["quantiles"], expected_qs):
        assert observed == pytest.approx(expected, abs=1e-5)

    # 2. Empty data
    empty_res = fast_compute_quantiles([], [0.5])
    assert empty_res["count"] == 0
    assert np.isnan(empty_res["mean"])
    assert np.isnan(empty_res["quantiles"][0])

    # 3. Constant array
    const_res = fast_compute_quantiles([42.0] * 10, [0.1, 0.5, 0.9])
    assert const_res["mean"] == pytest.approx(42.0)
    assert const_res["std"] == pytest.approx(0.0, abs=1e-9)
    assert const_res["quantiles"] == pytest.approx([42.0, 42.0, 42.0])

    # 4. Extreme values
    extreme_data = [1e-10, 2e-10, 5e-10, 1e-9]
    ext_res = fast_compute_quantiles(extreme_data, [0.5])
    assert ext_res["quantiles"][0] == pytest.approx(
        np.quantile(extreme_data, 0.5, method="linear"), rel=1e-5
    )


def test_lttb_edge_cases_and_parity():
    # Empty and sub-threshold inputs
    assert compress_curve_lttb([], [], max_points=10) == ([], [])
    assert compress_curve_lttb([1.0, 2.0], [3.0, 4.0], max_points=5) == ([1.0, 2.0], [3.0, 4.0])

    # Parity between Rust and fallback
    import marketing_mcp.accelerators as acc

    xs = [float(i) * 0.1 for i in range(200)]
    ys = [math.sin(x) + 0.1 * math.cos(x * 3) for x in xs]
    rust_x, rust_y = compress_curve_lttb(xs, ys, max_points=25)
    py_x, py_y = acc._py_compress_curve_lttb(xs, ys, max_points=25)
    assert len(rust_x) == 25
    assert len(py_x) == 25
    assert rust_x == pytest.approx(py_x, abs=1e-6)
    assert rust_y == pytest.approx(py_y, abs=1e-6)


def test_sparklines_edge_cases_and_parity():
    import marketing_mcp.accelerators as acc

    # Empty and all-NaN
    assert generate_sparkline([]) == ""
    assert generate_sparkline([float("nan"), float("inf")]) == "  "

    # Constant values
    assert generate_sparkline([10.0, 10.0, 10.0]) == "▄▄▄"

    # Parity
    vals = [-5.0, 0.0, 2.5, float("nan"), 10.0, 20.0, -10.0]
    assert generate_sparkline(vals) == acc._py_generate_sparkline(vals)


def test_fallback_mcmc_diagnostics_no_attribute_error(monkeypatch):
    """Verify that Python fallback in _py_fast_mcmc_diagnostics appends without AttributeError."""
    import marketing_mcp.accelerators as acc

    monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", False)

    # Trigger max_rhat > 1.05 failure branch
    with pytest.warns(UserWarning, match="NON-AUTHORITATIVE"):
        res = acc.fast_mcmc_diagnostics(rhats=[1.08, 1.02], esses=[500.0], divergences=0)
    assert res["decision_status"] == "rejected"
    assert res["decision_tools_enabled"] is False
    assert any("exceeds safety threshold" in f for f in res["failures"])


def test_disable_rust_environment_forces_real_fallback():
    """The fallback CI lane must disable native loading without monkeypatching."""
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env["MARKETING_MCP_DISABLE_RUST"] = "1"
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            (
                "from marketing_mcp.accelerators import get_engine_info; "
                "print(get_engine_info()['backend'])"
            ),
        ],
        env=env,
        text=True,
    )
    assert output.strip() == "python-standard"


def test_fast_admit_request_native_and_fallback(monkeypatch):
    import marketing_mcp.accelerators as acc

    raw_valid = b'{"jsonrpc": "2.0", "id": "req-1", "method": "tools/call", "params": {"name": "simulate_budget"}}'
    raw_large = b"x" * 500

    for is_rust in [True, False]:
        monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", is_rust)
        res = acc.fast_admit_request(raw_valid)
        assert res["admitted"] is True
        assert res["request_id"] == "req-1"
        assert res["method"] == "tools/call"
        assert res["tool_name"] == "simulate_budget"
        assert res["error"] is None

        err = acc.fast_admit_request(raw_large, max_size=100, tenant_id="tenant-1")
        assert err["admitted"] is False
        assert err["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert err["error"]["tenant_id"] == "tenant-1"


def test_python_admission_protocol_validation_matches_native():
    import marketing_mcp.accelerators as acc

    null_id = acc._py_fast_admit_request(
        b'{"jsonrpc":"2.0","id":null,"method":"tools/list","params":{}}'
    )
    assert null_id["admitted"] is True
    assert null_id["request_id"] is None
    assert null_id["is_notification"] is False

    numeric_id = acc._py_fast_admit_request(
        b'{"jsonrpc":"2.0","id":42,"method":"tools/list","params":{}}'
    )
    assert numeric_id["admitted"] is True
    assert numeric_id["request_id"] == 42

    null_version = acc._py_fast_admit_request(
        b'{"jsonrpc":null,"id":1,"method":"tools/list"}'
    )
    assert null_version["admitted"] is False
    assert null_version["error"]["code"] == "INVALID_JSONRPC_VERSION"

    zero_limit = acc._py_fast_admit_request(
        b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
        max_size=0,
    )
    assert zero_limit["admitted"] is False
    assert zero_limit["error"]["code"] == "PAYLOAD_TOO_LARGE"

    invalid_cases = [
        (b'{"jsonrpc":"2.0","id":true,"method":"tools/list"}', "INVALID_REQUEST_ID"),
        (b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":"bad"}', "INVALID_PARAMS"),
        (
            b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"arguments":{}}}',
            "INVALID_TOOL_CALL",
        ),
    ]
    for raw, expected_code in invalid_cases:
        result = acc._py_fast_admit_request(raw)
        assert result["admitted"] is False
        assert result["error"]["code"] == expected_code


def test_range_parser_rejects_extra_delimiters_in_both_backends(monkeypatch):
    import marketing_mcp.accelerators as acc

    for is_rust in [True, False]:
        monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", is_rust)
        assert acc.fast_parse_range_header("bytes=0-1-2", 100) is None


def test_fast_admit_job_native_and_fallback(monkeypatch):
    import marketing_mcp.accelerators as acc

    for is_rust in [True, False]:
        monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", is_rust)

        ok = acc.fast_admit_job(1024, max_size=10000, tenant_id="tenant-1")
        assert ok["admitted"] is True
        assert ok["status"] == "accepted"
        assert ok["admission_id"].startswith("adm-")
        assert "job_id" not in ok
        assert ok["recommended_poll_interval_ms"] == 1000
        assert ok["error"] is None

        overflow = acc.fast_admit_job(20000, max_size=10000, tenant_id="tenant-1")
        assert overflow["admitted"] is False
        assert overflow["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_fast_acknowledge_cancellation_native_and_fallback(monkeypatch):
    import marketing_mcp.accelerators as acc

    for is_rust in [True, False]:
        monkeypatch.setattr(acc, "_IS_RUST_AVAILABLE", is_rust)

        in_proc = acc.fast_acknowledge_cancellation("job-12345", in_process=True)
        assert in_proc["acknowledged"] is True
        assert in_proc["job_id"] == "job-12345"
        assert in_proc["status"] == "cancelling"
        assert in_proc["fence_triggered"] is True

        distributed = acc.fast_acknowledge_cancellation("job-12345", in_process=False)
        assert distributed["acknowledged"] is True
        assert distributed["status"] == "cancellation_requested"

        invalid = acc.fast_acknowledge_cancellation("   ", in_process=True)
        assert invalid["acknowledged"] is False
        assert invalid["error"]["code"] == "INVALID_JOB_ID"
