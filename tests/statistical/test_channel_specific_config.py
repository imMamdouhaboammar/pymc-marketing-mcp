"""Real PyMC-Marketing statistical test for channel-specific configuration.

Task 1 contract:
1. Channel-specific prior configurations passed to MMM fit actually alter the PyMC model graph.
2. Distinct priors on different channels produce distinctly shifted posteriors on those channels.
3. No mocking of the statistical boundary.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.schemas.models import (
    AdstockConfig,
    ChannelPriorConfig,
    FitMMMInput,
    PriorDistributionConfig,
    SamplerConfig,
    SaturationConfig,
)


@pytest.mark.statistical
def test_real_channel_specific_adstock_priors(tmp_path):
    np.random.seed(42)
    n_weeks = 40
    dates = pd.date_range("2023-01-01", periods=n_weeks, freq="W-MON")
    meta_spend = np.random.uniform(500, 1500, n_weeks)
    search_spend = np.random.uniform(500, 1500, n_weeks)

    # Simulate carryover on meta (alpha=0.75) and immediate on search
    meta_adstocked = np.zeros(n_weeks)
    for t in range(n_weeks):
        meta_adstocked[t] = meta_spend[t] + 0.75 * (meta_adstocked[t - 1] if t > 0 else 0)

    sales = 5000 + 2.5 * meta_adstocked + 3.0 * search_spend + np.random.normal(0, 50, n_weeks)

    df = pd.DataFrame({
        "date": dates,
        "meta": meta_spend,
        "search": search_spend,
        "sales": sales,
    })

    # Channel-specific priors:
    # meta has strong adstock prior (Beta(8, 2), mean=0.8)
    # search has weak adstock prior (Beta(1, 5), mean~0.17)
    channel_priors = {
        "meta": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 8.0, "beta": 2.0}),
            }
        ),
        "search": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 1.0, "beta": 5.0}),
            }
        ),
    }

    config = FitMMMInput(
        dataset_id="ds_test",
        date_column="date",
        target_column="sales",
        channel_columns=["meta", "search"],
        adstock=AdstockConfig(type="geometric", l_max=4),
        saturation=SaturationConfig(type="logistic"),
        sampler=SamplerConfig(draws=100, tune=100, chains=2, random_seed=42),
        channel_priors=channel_priors,
    )

    adapter = PyMCMarketingAdapter()
    model = adapter.fit(df, config, tmp_path / "model.nc")
    idata = model.idata

    assert "adstock_alpha" in idata.posterior
    meta_alpha = float(idata.posterior["adstock_alpha"].sel(channel="meta").mean())
    search_alpha = float(idata.posterior["adstock_alpha"].sel(channel="search").mean())

    # meta alpha posterior mean should be substantially higher than search alpha
    assert meta_alpha > search_alpha, f"Expected meta_alpha ({meta_alpha:.3f}) > search_alpha ({search_alpha:.3f})"
    assert meta_alpha > 0.4
    assert search_alpha < 0.4
