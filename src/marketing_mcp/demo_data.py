from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _geometric_adstock(x: np.ndarray, alpha: float) -> np.ndarray:
    """Compute exact 1D geometric adstock transformation."""
    out = np.zeros_like(x, dtype=float)
    for i, v in enumerate(x):
        out[i] = v + (alpha * out[i - 1] if i > 0 else 0.0)
    return out


def _hill_saturation(x: np.ndarray, k: float) -> np.ndarray:
    """Compute Hill/Michaelis-Menten style saturation curve."""
    return x / (x + k)


def generate_synthetic_mmm(
    n: int = 156,
    seed: int = 42,
    return_truth: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, Any]]:
    """Generate realistic weekly marketing mix dataset with known simulated truth."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n, freq="W-MON")
    t = np.arange(n)

    # Controls
    discount = (rng.random(n) < 0.15).astype(float)
    seasonality = 250_000.0 * np.sin(2 * np.pi * t / 52)
    base_revenue = 2_000_000.0

    # Media spend (weekly)
    meta_spend = rng.gamma(5, 20_000.0, n)
    google_spend = rng.gamma(6, 18_000.0, n)
    tiktok_spend = rng.gamma(3, 13_000.0, n)
    youtube_spend = rng.gamma(4, 15_000.0, n)

    # True simulation parameters
    params = {
        "meta": {"alpha": 0.55, "k": 160_000.0, "beta": 1_100_000.0},
        "google": {"alpha": 0.25, "k": 130_000.0, "beta": 1_400_000.0},
        "tiktok": {"alpha": 0.35, "k": 110_000.0, "beta": 650_000.0},
        "youtube": {"alpha": 0.60, "k": 170_000.0, "beta": 800_000.0},
    }

    # True transformed contributions
    meta_adstocked = _geometric_adstock(meta_spend, params["meta"]["alpha"])
    google_adstocked = _geometric_adstock(google_spend, params["google"]["alpha"])
    tiktok_adstocked = _geometric_adstock(tiktok_spend, params["tiktok"]["alpha"])
    youtube_adstocked = _geometric_adstock(youtube_spend, params["youtube"]["alpha"])

    meta_contrib = params["meta"]["beta"] * _hill_saturation(meta_adstocked, params["meta"]["k"])
    google_contrib = params["google"]["beta"] * _hill_saturation(
        google_adstocked, params["google"]["k"]
    )
    tiktok_contrib = params["tiktok"]["beta"] * _hill_saturation(
        tiktok_adstocked, params["tiktok"]["k"]
    )
    youtube_contrib = params["youtube"]["beta"] * _hill_saturation(
        youtube_adstocked, params["youtube"]["k"]
    )

    noise = rng.normal(0, 120_000.0, n)
    media_total = meta_contrib + google_contrib + tiktok_contrib + youtube_contrib
    revenue = base_revenue + seasonality + 400_000.0 * discount + media_total + noise
    revenue = np.maximum(revenue, 1.0)

    df = pd.DataFrame(
        {
            "date": dates,
            "meta": meta_spend,
            "google": google_spend,
            "tiktok": tiktok_spend,
            "youtube": youtube_spend,
            "discount": discount,
            "revenue": revenue,
        }
    )

    if not return_truth:
        return df

    truth = {
        "parameters": params,
        "base_revenue": base_revenue,
        "discount_lift": 400_000.0,
        "total_true_contributions": {
            "meta": float(np.sum(meta_contrib)),
            "google": float(np.sum(google_contrib)),
            "tiktok": float(np.sum(tiktok_contrib)),
            "youtube": float(np.sum(youtube_contrib)),
        },
        "true_total_iroas": {
            "meta": float(np.sum(meta_contrib) / np.sum(meta_spend)),
            "google": float(np.sum(google_contrib) / np.sum(google_spend)),
            "tiktok": float(np.sum(tiktok_contrib) / np.sum(tiktok_spend)),
            "youtube": float(np.sum(youtube_contrib) / np.sum(youtube_spend)),
        },
    }
    return df, truth


def generate_synthetic_multidimensional_mmm(
    n: int = 104,
    geos: tuple[str, ...] = ("Riyadh", "Jeddah", "Dammam"),
    seed: int = 42,
    return_truth: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, Any]]:
    """Generate rectangular multidimensional panel dataset with date x geo dimensions."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n, freq="W-MON")

    geo_multipliers = {
        "Riyadh": 1.5,
        "Jeddah": 1.2,
        "Dammam": 0.8,
    }

    records = []
    cell_contributions: dict[tuple[str, str], float] = {}

    for geo in geos:
        mult = geo_multipliers.get(geo, 1.0)
        t = np.arange(n)
        discount = (rng.random(n) < 0.15).astype(float)
        seasonality = 150_000.0 * mult * np.sin(2 * np.pi * t / 52)
        base = 800_000.0 * mult

        meta_spend = rng.gamma(5, 12_000.0 * mult, n)
        google_spend = rng.gamma(6, 11_000.0 * mult, n)
        tiktok_spend = rng.gamma(3, 8_000.0 * mult, n)
        youtube_spend = rng.gamma(4, 9_000.0 * mult, n)

        meta_adstock = _geometric_adstock(meta_spend, 0.50)
        google_adstock = _geometric_adstock(google_spend, 0.25)
        tiktok_adstock = _geometric_adstock(tiktok_spend, 0.35)
        youtube_adstock = _geometric_adstock(youtube_spend, 0.55)

        meta_c = 600_000.0 * mult * _hill_saturation(meta_adstock, 100_000.0 * mult)
        google_c = 750_000.0 * mult * _hill_saturation(google_adstock, 80_000.0 * mult)
        tiktok_c = 350_000.0 * mult * _hill_saturation(tiktok_adstock, 60_000.0 * mult)
        youtube_c = 450_000.0 * mult * _hill_saturation(youtube_adstock, 90_000.0 * mult)

        cell_contributions[("meta", geo)] = float(np.sum(meta_c))
        cell_contributions[("google", geo)] = float(np.sum(google_c))
        cell_contributions[("tiktok", geo)] = float(np.sum(tiktok_c))
        cell_contributions[("youtube", geo)] = float(np.sum(youtube_c))

        noise = rng.normal(0, 60_000.0 * mult, n)
        revenue = (
            base
            + seasonality
            + 200_000.0 * discount
            + meta_c
            + google_c
            + tiktok_c
            + youtube_c
            + noise
        )
        revenue = np.maximum(revenue, 1.0)

        for i, d in enumerate(dates):
            records.append(
                {
                    "date": d,
                    "geo": geo,
                    "meta": float(meta_spend[i]),
                    "google": float(google_spend[i]),
                    "tiktok": float(tiktok_spend[i]),
                    "youtube": float(youtube_spend[i]),
                    "discount": float(discount[i]),
                    "revenue": float(revenue[i]),
                }
            )

    df = pd.DataFrame(records)
    if not return_truth:
        return df

    truth = {
        "geos": list(geos),
        "cell_contributions": cell_contributions,
    }
    return df, truth


def generate_synthetic_lift_test(
    channels: list[str] | None = None,
    geos: list[str] | None = None,
) -> pd.DataFrame:
    """Generate realistic lift test observations for model calibration."""
    target_channels = channels or ["meta", "google"]
    records = []
    if not geos:
        for ch in target_channels:
            records.append(
                {
                    "channel": ch,
                    "x": 60_000.0,
                    "delta_x": 15_000.0,
                    "delta_y": 35_000.0,
                    "sigma": 5_000.0,
                }
            )
    else:
        for geo in geos:
            for ch in channels:
                records.append(
                    {
                        "channel": ch,
                        "geo": geo,
                        "x": 40_000.0,
                        "delta_x": 10_000.0,
                        "delta_y": 24_000.0,
                        "sigma": 4_000.0,
                    }
                )
    return pd.DataFrame(records)
