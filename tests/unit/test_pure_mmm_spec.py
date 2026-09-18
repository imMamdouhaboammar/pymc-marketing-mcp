"""Tests for pure MMM modeling core driven by canonical MMMModelSpec."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.scientific.mmm import (
    MMMFitResult,
    build_mmm_from_spec,
    fit_mmm_from_spec,
)


def _make_sample_df(rows: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=rows, freq="W")
    tv = rng.uniform(100.0, 500.0, size=rows)
    search = rng.uniform(50.0, 250.0, size=rows)
    sales = 1000.0 + 1.5 * tv + 2.0 * search + rng.normal(0, 10, size=rows)
    return pd.DataFrame({
        "date": dates,
        "tv_spend": tv,
        "search_spend": search,
        "sales": sales,
    })


def test_build_mmm_from_spec_geometric_logistic():
    spec_dict = {
        "analysis_kind": "mmm",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "date_column": "date",
            "target_column": "sales",
            "channel_columns": ["tv_spend", "search_spend"],
            "control_columns": [],
            "yearly_seasonality": 2,
            "adstock": {"kind": "geometric", "l_max": 8},
            "saturation": {"kind": "logistic"},
            "sampler": {"draws": 100, "tune": 50, "chains": 2, "target_accept": 0.85},
        },
    }

    mmm = build_mmm_from_spec(spec_dict)
    assert mmm is not None
    assert mmm.date_column == "date"
    assert mmm.channel_columns == ["tv_spend", "search_spend"]
    assert mmm.adstock.__class__.__name__ == "GeometricAdstock"
    assert mmm.saturation.__class__.__name__ == "LogisticSaturation"
    assert mmm.adstock.l_max == 8
    assert mmm.yearly_seasonality == 2

def test_build_mmm_from_canonical_pydantic_model_spec():
    try:
        from packages.contracts.python.models import (
            AdstockConfig,
            MMMConfiguration,
            MMMModelSpec,
            SamplerConfig,
            SaturationConfig,
        )
    except ImportError:
        pytest.skip("packages.contracts not available on PYTHONPATH")

    spec = MMMModelSpec(
        dataset_version_id=uuid4(),
        random_seed=77,
        configuration=MMMConfiguration(
            date_column="date",
            target_column="sales",
            channel_columns=["tv_spend", "search_spend"],
            yearly_seasonality=1,
            adstock=AdstockConfig(kind="geometric", l_max=6),
            saturation=SaturationConfig(kind="logistic"),
            sampler=SamplerConfig(draws=100, tune=50, chains=2, target_accept=0.8),
        ),
    )

    mmm = build_mmm_from_spec(spec)
    assert mmm.date_column == "date"
    assert mmm.channel_columns == ["tv_spend", "search_spend"]
    assert mmm.target_column == "sales"
    assert mmm.adstock.__class__.__name__ == "GeometricAdstock"
    assert mmm.adstock.l_max == 6
    assert mmm.yearly_seasonality == 1


def test_build_mmm_from_spec_delayed_tanh():
    spec_dict = {
        "analysis_kind": "mmm",
        "dataset_version_id": str(uuid4()),
        "random_seed": 123,
        "configuration": {
            "date_column": "week_start",
            "target_column": "revenue",
            "channel_columns": ["meta", "google"],
            "control_columns": ["promo"],
            "adstock": {"kind": "delayed", "l_max": 4},
            "saturation": {"kind": "tanh"},
            "sampler": {"draws": 50, "tune": 50, "chains": 2},
        },
    }

    mmm = build_mmm_from_spec(spec_dict)
    assert mmm.date_column == "week_start"
    assert mmm.adstock.__class__.__name__ == "DelayedAdstock"
    assert mmm.saturation.__class__.__name__ == "TanhSaturation"
    assert mmm.adstock.l_max == 4
    assert mmm.control_columns == ["promo"]


def test_fit_mmm_from_spec_with_fake_adapter(tmp_path):
    class MockMMMInstance:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.built = False
            self.fit_called = False
            self.idata = None

        def build_model(self, X, y):
            self.built = True

        def add_original_scale_contribution_variable(self, var):
            pass

        def fit(self, X, y, **kwargs):
            self.fit_called = True
            self.fit_kwargs = kwargs

        def sample_posterior_predictive(self, X, **kwargs):
            pass

        def save(self, path):
            Path(path).touch()

    df = _make_sample_df(30)
    spec_dict = {
        "analysis_kind": "mmm",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "date_column": "date",
            "target_column": "sales",
            "channel_columns": ["tv_spend", "search_spend"],
            "sampler": {"draws": 200, "tune": 100, "chains": 2, "target_accept": 0.9},
        },
    }

    mock_mmm = MockMMMInstance()
    artifact_file = tmp_path / "model_artifact.nc"
    result = fit_mmm_from_spec(
        spec_dict,
        df,
        artifact_path=artifact_file,
        mmm_factory=lambda **kw: mock_mmm,
    )

    assert isinstance(result, MMMFitResult)
    assert mock_mmm.built is True
    assert mock_mmm.fit_called is True
    assert mock_mmm.fit_kwargs["draws"] == 200
    assert mock_mmm.fit_kwargs["tune"] == 100
    assert mock_mmm.fit_kwargs["chains"] == 2
    assert mock_mmm.fit_kwargs["target_accept"] == 0.9
    assert artifact_file.exists()


def test_statistical_validation_golden_dataset():
    candidates = [
        Path(__file__).resolve().parents[2] / "migration/baselines/golden_datasets/pymc_harsh_observed_daily_panel.csv",
        Path(__file__).resolve().parents[3] / "migration/baselines/golden_datasets/pymc_harsh_observed_daily_panel.csv",
    ]
    golden_path = next((p for p in candidates if p.exists()), candidates[0])
    if not golden_path.exists():
        pytest.skip(f"Golden dataset not found at {golden_path}")

    df = pd.read_csv(golden_path)
    df["date"] = pd.to_datetime(df["date"])
    weekly_df = df.resample("W-MON", on="date").agg({
        "meta": "sum",
        "google": "sum",
        "tiktok": "sum",
        "revenue": "sum",
    }).reset_index()

    test_slice = weekly_df.iloc[:16].copy()

    spec_dict = {
        "analysis_kind": "mmm",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": ["meta", "google", "tiktok"],
            "adstock": {"kind": "geometric", "l_max": 2},
            "saturation": {"kind": "logistic"},
            "sampler": {"draws": 20, "tune": 20, "chains": 2, "target_accept": 0.8},
        },
    }

    result = fit_mmm_from_spec(spec_dict, test_slice)
    assert isinstance(result, MMMFitResult)
    assert result.diagnostics is not None
    assert "max_rhat" in result.diagnostics
    assert "divergences" in result.diagnostics
    assert "min_bfmi" in result.diagnostics
    assert isinstance(result.parameter_estimates, dict)
    assert len(result.parameter_estimates) > 0
