"""High-performance Rust acceleration bridge with zero-downtime Python fallback."""

from __future__ import annotations

import json
import math
import os
import warnings
from typing import Any

_rust_core: Any = None
_IS_RUST_AVAILABLE = False
_RUST_DISABLED = os.getenv("MARKETING_MCP_DISABLE_RUST", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _load_rust_core() -> Any:
    """Load the native module only when acceleration is enabled."""
    try:
        import marketing_mcp_fast

        return marketing_mcp_fast
    except ImportError:
        try:
            import importlib.util
            from _frozen_importlib_external import ExtensionFileLoader
            from pathlib import Path

            pkg_dir = Path(__file__).resolve().parent
            target_dir = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "crates"
                / "marketing_mcp_fast"
                / "target"
                / "release"
            )
            candidates = [
                pkg_dir / "marketing_mcp_fast.so",
                pkg_dir / "libmarketing_mcp_fast.so",
                pkg_dir / "libmarketing_mcp_fast.dylib",
                pkg_dir / "marketing_mcp_fast.dylib",
                target_dir / "libmarketing_mcp_fast.dylib",
                target_dir / "libmarketing_mcp_fast.so",
                target_dir / "marketing_mcp_fast.so",
            ]
            found = next((candidate for candidate in candidates if candidate.is_file()), None)
            if found is None:
                return None
            loader = ExtensionFileLoader("marketing_mcp_fast", str(found))
            spec = importlib.util.spec_from_file_location(
                "marketing_mcp_fast", found, loader=loader
            )
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except (ImportError, OSError, AttributeError, TypeError, ValueError):
            return None


if not _RUST_DISABLED:
    _rust_core = _load_rust_core()
    _IS_RUST_AVAILABLE = _rust_core is not None


def is_rust_accelerated() -> bool:
    """Return True if native Rust acceleration is active, False if using pure Python fallback."""
    return _IS_RUST_AVAILABLE


def get_engine_info() -> dict[str, Any]:
    """Return runtime accelerator information and active backend."""
    return {
        "rust_accelerated": _IS_RUST_AVAILABLE,
        "version": getattr(_rust_core, "get_version", lambda: "python-fallback")(),
        "backend": "rust-native" if _IS_RUST_AVAILABLE else "python-standard",
    }


def get_native_invocation_stats() -> dict[str, int]:
    """Return a snapshot of native invocation counters for observability and test verification.

    Counters are process-local and reset on process restart.
    Use these in integration tests to prove native hot paths actually ran.

    Example::
        stats = get_native_invocation_stats()
        assert stats["native_admission_calls_total"] > 0  # Rust admission was wired
    """
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "get_native_invocation_stats"):
        return dict(_rust_core.get_native_invocation_stats())
    # Python fallback: return zeros (native paths never ran in this process)
    return {
        "native_admission_calls_total": 0,
        "native_serialization_calls_total": 0,
        "native_range_parse_calls_total": 0,
        "native_job_admission_calls_total": 0,
        "native_cancellation_calls_total": 0,
        "native_fallback_calls_total": 0,
    }


def NATIVE_FALLBACK_COUNT_REF() -> None:
    """Signal that a native path fell back to Python unexpectedly.

    Called by NativeAdmissionMiddleware when the Rust extension throws during admission.
    Allows monitoring fallback rate without failing the request.
    """
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "increment_native_fallback_count"):
        _rust_core.increment_native_fallback_count()


# =========================================================================
# Pure Python Fallbacks (The /clean-code-guard and /ponytail Guarantee)
# =========================================================================


def _py_generate_sparkline(values: list[float]) -> str:
    finite = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    if not finite:
        return " " * len(values)
    min_v, max_v = min(finite), max(finite)
    rng = max_v - min_v
    blocks = " ▂▃▄▅▆▇█"
    out = []
    for v in values:
        if not (isinstance(v, (int, float)) and math.isfinite(v)):
            out.append(" ")
        elif rng <= 1e-12:
            out.append("▄")
        else:
            norm = max(0.0, min(1.0, (v - min_v) / rng))
            idx = min(7, round(norm * 7.0))
            out.append(blocks[idx])
    return "".join(out)


def _py_compress_curve_lttb(
    xs: list[float], ys: list[float], max_points: int
) -> tuple[list[float], list[float]]:
    n = len(xs)
    if n <= max_points or max_points < 3 or n != len(ys):
        return list(xs), list(ys)

    every = (n - 2) / (max_points - 2)
    sampled_x = [xs[0]]
    sampled_y = [ys[0]]
    a_idx = 0

    for i in range(max_points - 2):
        c_start = min(n - 1, math.floor((i + 1) * every) + 1)
        c_end = min(n, math.floor((i + 2) * every) + 1)
        c_len = max(1, c_end - c_start)
        avg_x = sum(xs[c_start:c_end]) / c_len
        avg_y = sum(ys[c_start:c_end]) / c_len

        b_start = min(n - 1, math.floor(i * every) + 1)
        b_end = min(n, math.floor((i + 1) * every) + 1)

        ax = xs[a_idx]
        ay = ys[a_idx]
        max_area = -1.0
        next_a = b_start

        for j in range(b_start, b_end):
            area = abs((ax - avg_x) * (ys[j] - ay) - (ax - xs[j]) * (avg_y - ay)) * 0.5
            if area > max_area:
                max_area = area
                next_a = j

        sampled_x.append(xs[next_a])
        sampled_y.append(ys[next_a])
        a_idx = next_a

    sampled_x.append(xs[-1])
    sampled_y.append(ys[-1])
    return sampled_x, sampled_y


def _py_fast_compute_quantiles(values: list[float], quantiles: list[float]) -> dict[str, Any]:
    import numpy as np

    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {
            "mean": float("nan"),
            "std": float("nan"),
            "min": float("nan"),
            "max": float("nan"),
            "count": 0,
            "quantiles": [float("nan") for _ in quantiles],
        }
    qs = np.quantile(arr, quantiles).tolist()
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "count": len(arr),
        "quantiles": [float(q) for q in qs],
    }


def _py_fast_sniff_and_validate_csv(
    csv_bytes: bytes,
    date_col: str | None = None,
    target_col: str | None = None,
    channel_cols: list[str] | None = None,
) -> dict[str, Any]:
    from io import BytesIO

    import pandas as pd

    df = pd.read_csv(BytesIO(csv_bytes))
    column_names = df.columns.tolist()
    validation_errors = []

    if date_col and date_col not in df.columns:
        validation_errors.append(f"Missing date column: '{date_col}'")
    if target_col and target_col not in df.columns:
        validation_errors.append(f"Missing target column: '{target_col}'")
    if channel_cols:
        for ch in channel_cols:
            if ch not in df.columns:
                validation_errors.append(f"Missing channel column: '{ch}'")

    if len(df) < 14:
        validation_errors.append(
            f"Dataset has only {len(df)} rows; MMM modeling requires at least 14 rows"
        )

    cols_dict = {}
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        detected_type = "numeric" if is_numeric else ("date" if col == date_col else "string")
        min_v = float(df[col].min()) if is_numeric and len(df) > null_count else None
        max_v = float(df[col].max()) if is_numeric and len(df) > null_count else None
        mean_v = float(df[col].mean()) if is_numeric and len(df) > null_count else None

        if channel_cols and col in channel_cols and min_v is not None and min_v < 0:
            validation_errors.append(f"Channel column '{col}' contains negative spend: {min_v}")

        cols_dict[col] = {
            "name": col,
            "detected_type": detected_type,
            "null_count": null_count,
            "min": min_v,
            "max": max_v,
            "mean": mean_v,
        }

    date_min = None
    date_max = None
    if date_col and date_col in df.columns:
        dt_series = pd.to_datetime(df[date_col], errors="coerce")
        if not dt_series.isna().all():
            date_min = str(dt_series.min().date())
            date_max = str(dt_series.max().date())

    return {
        "row_count": len(df),
        "column_names": column_names,
        "is_valid_for_modeling": len(validation_errors) == 0,
        "validation_errors": validation_errors,
        "date_min": date_min,
        "date_max": date_max,
        "columns": cols_dict,
    }


def _py_fast_mcmc_diagnostics(
    rhats: list[float], esses: list[float], divergences: int
) -> dict[str, Any]:
    finite_rhats = [r for r in rhats if math.isfinite(r)]
    finite_esses = [e for e in esses if math.isfinite(e)]
    max_rhat = max(finite_rhats) if finite_rhats else 1.0
    min_ess = min(finite_esses) if finite_esses else 1000.0

    failures = []
    warnings = []
    if divergences > 0:
        failures.append(f"Sampler had {divergences} divergent transition(s)")
    if max_rhat > 1.05:
        failures.append(f"Max R-hat ({max_rhat:.3f}) exceeds safety threshold (1.05)")
    elif max_rhat > 1.02:
        warnings.append(f"Max R-hat ({max_rhat:.3f}) shows mild convergence friction")

    if min_ess < 100.0:
        failures.append(f"Min Bulk-ESS ({min_ess:.1f}) is below critical floor (100.0)")
    elif min_ess < 400.0:
        warnings.append(f"Min Bulk-ESS ({min_ess:.1f}) is below recommended target (400.0)")

    if failures:
        status, enabled = "rejected", False
    elif warnings:
        status, enabled = "caution", True
    else:
        status, enabled = "approved", True

    return {
        "max_rhat": max_rhat,
        "min_ess": min_ess,
        "divergences": divergences,
        "decision_status": status,
        "decision_tools_enabled": enabled,
        "failures": failures,
        "warnings": warnings,
    }


def _py_fast_serialize_json(obj: Any) -> str:
    return json.dumps(obj)


# =========================================================================
# Public Dispatched API (Rust when available, else Python Fallback)
# =========================================================================


def generate_sparkline(values: list[float]) -> str:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "generate_sparkline"):
        return _rust_core.generate_sparkline(values)
    return _py_generate_sparkline(values)


def compress_curve_lttb(
    xs: list[float], ys: list[float], max_points: int = 30
) -> tuple[list[float], list[float]]:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "compress_curve_lttb"):
        return _rust_core.compress_curve_lttb(xs, ys, max_points)
    return _py_compress_curve_lttb(xs, ys, max_points)


def fast_compute_quantiles(values: list[float], quantiles: list[float]) -> dict[str, Any]:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_compute_quantiles"):
        return _rust_core.fast_compute_quantiles(values, quantiles)
    return _py_fast_compute_quantiles(values, quantiles)


def fast_sniff_and_validate_csv(
    csv_bytes: bytes,
    date_col: str | None = None,
    target_col: str | None = None,
    channel_cols: list[str] | None = None,
) -> dict[str, Any]:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_sniff_and_validate_csv"):
        return _rust_core.fast_sniff_and_validate_csv(csv_bytes, date_col, target_col, channel_cols)
    return _py_fast_sniff_and_validate_csv(csv_bytes, date_col, target_col, channel_cols)


def fast_mcmc_diagnostics(
    rhats: list[float], esses: list[float], divergences: int
) -> dict[str, Any]:
    """EXPERIMENTAL / BENCHMARK-ONLY MCMC diagnostic evaluator. NOT for production decisions.

    .. deprecated::
        NON-AUTHORITATIVE. Production statistical decision gate authority resides
        exclusively in ``marketing_mcp.domain.diagnostics.engine.diagnose_inferencedata``.
        Use this function ONLY for comparative benchmarks or parity tests.
        Calling this from production decision paths is a correctness bug.

    See also: ``marketing_mcp.accelerators.experimental`` for the clearly-labeled
    experimental re-exports.
    """
    warnings.warn(
        "fast_mcmc_diagnostics is NON-AUTHORITATIVE and must not be used for production "
        "statistical decisions. Use diagnose_inferencedata from the diagnostics engine instead.",
        stacklevel=2,
        category=UserWarning,
    )
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_mcmc_diagnostics"):
        return _rust_core.fast_mcmc_diagnostics(rhats, esses, divergences)
    return _py_fast_mcmc_diagnostics(rhats, esses, divergences)


def fast_serialize_json(obj: Any) -> str:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_serialize_json"):
        return _rust_core.fast_serialize_json(obj)
    return _py_fast_serialize_json(obj)


# Sentinel for detecting absent `id` field vs explicit null
_SENTINEL = object()


def _py_fast_admit_request(
    raw_bytes: bytes, max_size: int | None = None, tenant_id: str | None = None
) -> dict[str, Any]:
    """Python fallback for fast_admit_request. Matches Rust engine behavior exactly."""
    import time
    import uuid

    # Align limit with Rust engine.rs DEFAULT_MAX_REQUEST_SIZE (10 MB)
    limit = 10 * 1024 * 1024 if max_size is None else max_size
    if len(raw_bytes) > limit:
        return {
            "admitted": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "category": "transport",
                "message": f"Payload size ({len(raw_bytes)} bytes) exceeds maximum limit ({limit} bytes)",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }
    if not raw_bytes:
        return {
            "admitted": False,
            "error": {
                "code": "EMPTY_REQUEST",
                "category": "protocol",
                "message": "Request body is empty",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }
    try:
        obj = json.loads(raw_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return {
            "admitted": False,
            "error": {
                "code": "MALFORMED_JSON_RPC",
                "category": "protocol",
                "message": f"Malformed JSON payload: {e}",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }
    if not isinstance(obj, dict):
        return {
            "admitted": False,
            "error": {
                "code": "INVALID_JSON_RPC",
                "category": "protocol",
                "message": "JSON-RPC payload must be a JSON object, not an array or scalar",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }

    # jsonrpc field MUST be present and MUST be "2.0"
    jsonrpc_val = obj.get("jsonrpc")
    if "jsonrpc" not in obj:
        return {
            "admitted": False,
            "error": {
                "code": "MISSING_JSONRPC_VERSION",
                "category": "protocol",
                "message": "JSON-RPC request is missing required 'jsonrpc' field",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }
    if jsonrpc_val != "2.0":
        return {
            "admitted": False,
            "error": {
                "code": "INVALID_JSONRPC_VERSION",
                "category": "protocol",
                "message": f"jsonrpc version must be '2.0', got '{jsonrpc_val}'",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }

    # A JSON-RPC notification is identified only by an absent id field.
    # A present null id is discouraged, but it is still a request.
    id_val = obj.get("id") if "id" in obj else _SENTINEL
    is_notification = id_val is _SENTINEL
    if id_val is _SENTINEL or id_val is None:
        req_id = None
    elif isinstance(id_val, str) or (isinstance(id_val, int) and not isinstance(id_val, bool)) or isinstance(id_val, float) and math.isfinite(id_val):
        req_id = id_val
    else:
        return {
            "admitted": False,
            "error": {
                "code": "INVALID_REQUEST_ID",
                "category": "protocol",
                "message": "JSON-RPC id must be a string, number, or null",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": None,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
            },
        }

    method_val = obj.get("method")
    if not isinstance(method_val, str) or not method_val:
        return {
            "admitted": False,
            "error": {
                "code": "MISSING_METHOD",
                "category": "protocol",
                "message": "JSON-RPC request is missing a non-empty string 'method' field",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": req_id,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
                "is_notification": is_notification,
            },
        }
    method = method_val

    params = obj.get("params", _SENTINEL)
    if params is not _SENTINEL and not isinstance(params, (dict, list)):
        return {
            "admitted": False,
            "error": {
                "code": "INVALID_PARAMS",
                "category": "protocol",
                "message": "JSON-RPC params must be an object or array",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "request_id": req_id,
                "tenant_id": tenant_id,
                "retryable": False,
                "actionable": True,
                "is_notification": is_notification,
            },
        }

    tool_name = None
    if method == "tools/call":
        candidate = params.get("name") if isinstance(params, dict) else None
        if not isinstance(candidate, str) or not candidate:
            return {
                "admitted": False,
                "error": {
                    "code": "INVALID_TOOL_CALL",
                    "category": "protocol",
                    "message": "MCP tools/call requires params.name as a non-empty string",
                    "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                    "request_id": req_id,
                    "tenant_id": tenant_id,
                    "retryable": False,
                    "actionable": True,
                    "is_notification": is_notification,
                },
            }
        tool_name = candidate
    return {
        "admitted": True,
        "request_id": req_id,
        "jsonrpc": "2.0",
        "method": method,
        "tool_name": tool_name,
        "payload_size": len(raw_bytes),
        "is_notification": is_notification,
        "error": None,
    }


def fast_serialize_json_bytes(obj: Any) -> bytes:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_serialize_json_bytes"):
        return bytes(_rust_core.fast_serialize_json_bytes(obj))
    return _py_fast_serialize_json(obj).encode("utf-8")


def fast_admit_request(
    raw_bytes: bytes, max_size: int | None = None, tenant_id: str | None = None
) -> dict[str, Any]:
    """Admit and validate raw MCP request using Rust native engine when available."""
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_admit_request"):
        return _rust_core.fast_admit_request(raw_bytes, max_size, tenant_id)
    return _py_fast_admit_request(raw_bytes, max_size, tenant_id)


def _py_fast_parse_range_header(header: str, file_size: int) -> tuple[int, int, int] | None:
    if file_size <= 0:
        return None
    trimmed = header.strip()
    if not trimmed.startswith("bytes="):
        return None
    spec = trimmed[6:]
    parts = spec.split("-", 1)
    if len(parts) != 2:
        return None
    start_str, end_str = parts[0].strip(), parts[1].strip()
    try:
        if not start_str:
            suffix_len = int(end_str)
            if suffix_len <= 0:
                return None
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = int(start_str)
            end = file_size - 1 if not end_str else min(int(end_str), file_size - 1)
        if start >= file_size or start > end:
            return None
        return start, end, end - start + 1
    except ValueError:
        return None


def fast_parse_range_header(header: str, file_size: int) -> tuple[int, int, int] | None:
    """Fast HTTP Range request header parsing using Rust native engine when available."""
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_parse_range_header"):
        return _rust_core.fast_parse_range_header(header, file_size)
    return _py_fast_parse_range_header(header, file_size)


def _py_fast_admit_job(
    payload_size: int, max_size: int | None = None, tenant_id: str | None = None
) -> dict[str, Any]:
    """Python fallback for fast_admit_job. Uses admission_id (NOT job_id) — matches Rust semantics."""
    import time
    import uuid

    # Align limit with Rust engine.rs DEFAULT_MAX_REQUEST_SIZE (10 MB)
    limit = 10 * 1024 * 1024 if max_size is None else max_size
    if payload_size > limit:
        return {
            "admitted": False,
            "error": {
                "code": "PAYLOAD_TOO_LARGE",
                "category": "transport",
                "message": f"Job submission payload ({payload_size} bytes) exceeds limit ({limit} bytes)",
                "error_id": f"err-{int(time.time() * 1_000_000):x}-{uuid.uuid4().hex[:8]}",
                "retryable": False,
                "actionable": True,
            },
        }
    now = int(time.time())
    # `admission_id` is the INTERACTION-LEVEL token only.
    # The canonical persistent job ID is created by Python's job service AFTER this check.
    admission_id = f"adm-{uuid.uuid4().hex[:16]}"
    return {
        "admitted": True,
        "admission_id": admission_id,
        "status": "accepted",
        "admitted_at": now,
        "recommended_poll_interval_ms": 1000,
        "error": None,
    }


def _py_fast_acknowledge_cancellation(job_id: str, in_process: bool = True) -> dict[str, Any]:
    """Python fallback for fast_acknowledge_cancellation.

    Status reflects interaction-level state only. The Python worker state is authoritative.
    - in_process=True → "cancelling" (signal sent, worker may still be running)
    - in_process=False → "cancellation_requested" (queued job, not yet started)
    """
    import time

    trimmed = job_id.strip()
    if not trimmed:
        return {
            "acknowledged": False,
            "error": {
                "code": "INVALID_JOB_ID",
                "category": "validation",
                "message": "Job ID cannot be empty",
            },
        }
    return {
        "acknowledged": True,
        "job_id": trimmed,
        # Match Rust engine status strings exactly
        "status": "cancelling" if in_process else "cancellation_requested",
        "acknowledged_at": int(time.time()),
        "fence_triggered": True,
        "error": None,
    }


def fast_admit_job(
    payload_size: int, max_size: int | None = None, tenant_id: str | None = None
) -> dict[str, Any]:
    """Sub-millisecond job admission token generation using Rust native engine when available."""
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_admit_job"):
        return _rust_core.fast_admit_job(payload_size, max_size, tenant_id)
    return _py_fast_admit_job(payload_size, max_size, tenant_id)


def fast_acknowledge_cancellation(job_id: str, in_process: bool = True) -> dict[str, Any]:
    """Fast truthful cancellation acknowledgment using Rust native engine when available."""
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_acknowledge_cancellation"):
        return _rust_core.fast_acknowledge_cancellation(job_id, in_process)
    return _py_fast_acknowledge_cancellation(job_id, in_process)
