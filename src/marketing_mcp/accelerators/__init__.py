"""High-performance Rust acceleration bridge with zero-downtime Python fallback."""

from __future__ import annotations

import json
import math
from typing import Any

_rust_core: Any = None
_IS_RUST_AVAILABLE = False

try:
    import marketing_mcp_fast as _rust_core  # type: ignore

    _IS_RUST_AVAILABLE = True
except ImportError:
    try:
        # Check if local release shared library is present
        import ctypes
        import importlib.util
        from pathlib import Path

        # Look in crate target release dir
        target_dir = Path(__file__).resolve().parent.parent.parent.parent / "crates" / "marketing_mcp_fast" / "target" / "release"
        dylib_candidates = [
            target_dir / "libmarketing_mcp_fast.dylib",
            target_dir / "libmarketing_mcp_fast.so",
            target_dir / "marketing_mcp_fast.so",
        ]
        found = next((p for p in dylib_candidates if p.is_file()), None)
        if found:
            spec = importlib.util.spec_from_file_location("marketing_mcp_fast", found)
            if spec and spec.loader:
                _rust_core = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(_rust_core)
                _IS_RUST_AVAILABLE = True
    except Exception:
        _rust_core = None
        _IS_RUST_AVAILABLE = False


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
            idx = min(7, int(round(norm * 7.0)))
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
        c_start = min(n - 1, int(math.floor((i + 1) * every)) + 1)
        c_end = min(n, int(math.floor((i + 2) * every)) + 1)
        c_len = max(1, c_end - c_start)
        avg_x = sum(xs[c_start:c_end]) / c_len
        avg_y = sum(ys[c_start:c_end]) / c_len

        b_start = min(n - 1, int(math.floor(i * every)) + 1)
        b_end = min(n, int(math.floor((i + 1) * every)) + 1)

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
        failures.push(f"Max R-hat ({max_rhat:.3f}) exceeds safety threshold (1.05)")
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
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_mcmc_diagnostics"):
        return _rust_core.fast_mcmc_diagnostics(rhats, esses, divergences)
    return _py_fast_mcmc_diagnostics(rhats, esses, divergences)


def fast_serialize_json(obj: Any) -> str:
    if _IS_RUST_AVAILABLE and hasattr(_rust_core, "fast_serialize_json"):
        return _rust_core.fast_serialize_json(obj)
    return _py_fast_serialize_json(obj)
