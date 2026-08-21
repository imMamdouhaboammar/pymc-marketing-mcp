from __future__ import annotations

import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset


def _panel():
    dates = pd.date_range("2024-01-01", periods=60, freq="W-MON")
    rows = []
    for geo_i, geo in enumerate(["riyadh", "jeddah"]):
        for i, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "geo": geo,
                    "revenue": 100 + i + geo_i,
                    "meta": 10 + (i % 7) + geo_i,
                }
            )
    return pd.DataFrame(rows)


def test_panel_allows_same_date_across_different_dimension_values():
    findings = validate_mmm_dataset(
        _panel(), "date", "revenue", ["meta"], [], dims=["geo"]
    )
    assert not any(f.code == "DUPLICATE_PERIOD" for f in findings)
    assert not any(f.code == "NON_RECTANGULAR_PANEL" for f in findings)


def test_panel_rejects_duplicate_date_dimension_key():
    df = _panel()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    findings = validate_mmm_dataset(
        df, "date", "revenue", ["meta"], [], dims=["geo"]
    )
    assert any(f.code == "DUPLICATE_PERIOD" for f in findings)


def test_panel_rejects_non_rectangular_dimension_grid():
    df = _panel()
    df = df[~((df["geo"] == "jeddah") & (df["date"] == df["date"].max()))]
    findings = validate_mmm_dataset(
        df, "date", "revenue", ["meta"], [], dims=["geo"]
    )
    assert any(f.code == "NON_RECTANGULAR_PANEL" for f in findings)
