"""Currency detection and multi-currency consistency validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

KNOWN_CURRENCIES = {"USD", "EUR", "GBP", "SAR", "AED", "CAD", "AUD", "JPY", "CHF", "INR", "CNY"}


def infer_currencies(df: pd.DataFrame) -> list[str]:
    """Discovers currencies present in columns or column names."""
    currencies = set()

    # 1. Dedicated currency columns
    for col in df.columns:
        cl = col.lower()
        if cl in ("currency", "curr", "currency_code", "iso_currency"):
            vals = df[col].dropna().astype(str).str.upper().unique()
            for v in vals:
                if v in KNOWN_CURRENCIES or len(v) == 3:
                    currencies.add(v)

    # 2. Suffixes in column names
    for col in df.columns:
        cl = col.lower()
        for c in KNOWN_CURRENCIES:
            if cl.endswith(f"_{c.lower()}") or cl.startswith(f"{c.lower()}_"):
                currencies.add(c)
        if "local" in cl:
            currencies.add("local")

    return sorted(list(currencies))


def verify_fx_consistency(
    df: pd.DataFrame,
    local_col: str,
    norm_col: str,
    fx_col: str,
    tolerance: float = 0.05,
) -> tuple[bool, float]:
    """Validates whether local_col * fx_rate or local_col / fx_rate ≈ norm_col."""
    valid = df[[local_col, norm_col, fx_col]].dropna()
    if len(valid) == 0:
        return False, 1.0

    local_vals = valid[local_col].values
    norm_vals = valid[norm_col].values
    fx_vals = valid[fx_col].values

    # Test multiplication: local * fx ≈ norm
    diff_mult = np.abs((local_vals * fx_vals) - norm_vals) / np.maximum(1e-6, np.abs(norm_vals))
    mean_diff_mult = float(np.mean(diff_mult))

    # Test division: local / fx ≈ norm (e.g. SAR / 3.75 ≈ USD)
    diff_div = np.abs((local_vals / np.maximum(1e-6, fx_vals)) - norm_vals) / np.maximum(1e-6, np.abs(norm_vals))
    mean_diff_div = float(np.mean(diff_div))

    best_diff = min(mean_diff_mult, mean_diff_div)
    return (best_diff <= tolerance), round(best_diff, 4)
