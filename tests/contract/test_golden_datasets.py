"""Statistical golden dataset invariants verification (UP-003)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines" / "golden_datasets"


def _sha256(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_mmm_golden_dataset_invariants():
    with open(GOLDEN_DIR / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)

    mmm_meta = meta["datasets"]["mmm_synthetic"]
    csv_path = GOLDEN_DIR / mmm_meta["file"]
    assert csv_path.is_file()
    assert _sha256(csv_path) == mmm_meta["sha256"]

    df = pd.read_csv(csv_path)
    assert len(df) == mmm_meta["row_count"]
    assert list(df.columns) == mmm_meta["columns"]

    # Invariant: non-negative spend across all media channels
    for ch in mmm_meta["channels"]:
        assert (df[ch] >= 0.0).all(), f"Channel {ch} contains negative spend"
        assert df[ch].sum() > 0.0, f"Channel {ch} has zero total spend"

    # Invariant: strictly positive target revenue
    assert (df[mmm_meta["target_column"]] > 0.0).all()

    # Invariant: monotonic weekly dates
    dates = pd.to_datetime(df["date"])
    diffs = dates.diff().dropna()
    assert (diffs == pd.Timedelta(days=7)).all(), "Dates must be strictly contiguous weekly intervals"


def test_clv_rfm_golden_dataset_invariants():
    with open(GOLDEN_DIR / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)

    rfm_meta = meta["datasets"]["clv_rfm_synthetic"]
    csv_path = GOLDEN_DIR / rfm_meta["file"]
    assert csv_path.is_file()
    assert _sha256(csv_path) == rfm_meta["sha256"]

    df = pd.read_csv(csv_path)
    assert len(df) == rfm_meta["row_count"]

    # Invariants:
    # 1. recency <= T for every customer
    assert (df["recency"] <= df["T"]).all()
    # 2. non-negative frequency, recency, T
    assert (df["frequency"] >= 0).all()
    assert (df["recency"] >= 0).all()
    assert (df["T"] > 0).all()
    # 3. customers with frequency == 0 must have recency == 0
    assert (df[df["frequency"] == 0]["recency"] == 0.0).all()
    # 4. repeat customers have positive monetary_value
    repeat = df[df["frequency"] > 0]
    assert (repeat["monetary_value"] > 0.0).all()


def test_clv_contractual_golden_dataset_invariants():
    with open(GOLDEN_DIR / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)

    c_meta = meta["datasets"]["clv_contractual_synthetic"]
    csv_path = GOLDEN_DIR / c_meta["file"]
    assert csv_path.is_file()
    assert _sha256(csv_path) == c_meta["sha256"]

    df = pd.read_csv(csv_path)
    assert len(df) == c_meta["row_count"]

    # Invariant: last_period <= max_period
    assert (df["last_period"] <= df["max_period"]).all()
    assert (df["last_period"] >= 1).all()
