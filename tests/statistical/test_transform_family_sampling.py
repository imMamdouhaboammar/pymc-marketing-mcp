"""Real PyMC-Marketing statistical smoke test matrix for supported transform families.

Task 2 contract:
Validates that representative combinations from the adstock and saturation zoo
(geometric, delayed, weibull_cdf, none) x (logistic, hill, michaelis_menten, none)
build valid PyMC graphs and sample posteriors without error.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.schemas.models import (
    AdstockConfig,
    FitMMMInput,
    SamplerConfig,
    SaturationConfig,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    np.random.seed(42)
    n_weeks = 25
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON")
    tv = np.random.uniform(100, 500, n_weeks)
    search = np.random.uniform(50, 200, n_weeks)
    y = 1000 + 1.5 * tv + 2.0 * search + np.random.normal(0, 10, n_weeks)
    return pd.DataFrame({"date": dates, "tv": tv, "search": search, "revenue": y})


@pytest.mark.statistical
@pytest.mark.parametrize(
    ("adstock_type", "l_max", "saturation_type"),
    [
        ("geometric", 4, "logistic"),
        ("delayed", 4, "hill"),
        ("weibull_cdf", 4, "michaelis_menten"),
        ("none", 1, "none"),
    ],
)
def test_transform_matrix_sampling_smoke(sample_df, tmp_path, adstock_type, l_max, saturation_type):
    config = FitMMMInput(
        dataset_id="ds_smoke",
        date_column="date",
        target_column="revenue",
        channel_columns=["tv", "search"],
        adstock=AdstockConfig(type=adstock_type, l_max=l_max),
        saturation=SaturationConfig(type=saturation_type),
        sampler=SamplerConfig(draws=50, tune=50, chains=2, random_seed=42),
    )

    adapter = PyMCMarketingAdapter()
    artifact_path = tmp_path / f"model_{adstock_type}_{saturation_type}.nc"
    model = adapter.fit(sample_df, config, artifact_path)

    assert artifact_path.exists()
    assert hasattr(model, "idata")
    assert "posterior" in model.idata
    assert "channel_contribution" in model.idata.posterior
