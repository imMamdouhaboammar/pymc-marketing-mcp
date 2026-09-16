"""Consistency between plot summaries and analytical contribution summaries.

Task 6 contract: plots render ONLY summaries from the tested domain layer, and
those summaries agree with the analytical contribution tool on a real fitted
model (real MCMC, no mocks).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
from marketing_mcp.domain.posterior_summaries import summarize_channel_contributions
from marketing_mcp.services.plotting_service import PlottingService


@pytest.fixture
def fitted_model(tmp_path):
    np.random.seed(42)
    n_weeks = 52
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON")
    meta = np.random.uniform(50, 150, n_weeks)
    google = np.random.uniform(80, 200, n_weeks)
    sales = 200.0 + 1.2 * meta + 1.8 * google + np.random.normal(0, 5, n_weeks)

    df = pd.DataFrame(
        {"date": dates.strftime("%Y-%m-%d"), "sales": sales, "meta": meta, "google": google}
    )

    cfg = {
        "date_column": "date",
        "channel_columns": ["meta", "google"],
        "target_column": "sales",
        "adstock": {"type": "geometric", "l_max": 4},
        "saturation": {"type": "logistic"},
        "sampler": {"draws": 50, "tune": 50, "chains": 2, "target_accept": 0.85, "random_seed": 42},
    }
    adapter = PyMCMarketingAdapter()
    artifact = tmp_path / "plot_consistency.nc"
    model = adapter.fit(df, cfg, artifact)
    return model


@pytest.mark.statistical
def test_plot_summary_matches_analytical_contribution_summary(fitted_model):
    summary = summarize_channel_contributions(fitted_model.idata)
    analytical = PyMCMarketingAdapter().channel_contributions(fitted_model)

    by_channel = {c["channel"]: c for c in analytical["channels"]}
    assert set(by_channel) == set(summary.coords["channel"].values.tolist())

    for ch, rec in by_channel.items():
        plot_median = float(summary["median"].sel(channel=ch).values)
        assert plot_median == pytest.approx(rec["contribution_median"], rel=1e-9)
        ci = rec["credible_interval"]
        assert float(summary["lower"].sel(channel=ch).values) == pytest.approx(
            ci["lower"], rel=1e-9
        )
        assert float(summary["upper"].sel(channel=ch).values) == pytest.approx(
            ci["upper"], rel=1e-9
        )


@pytest.mark.statistical
@pytest.mark.parametrize(
    "plot_type",
    ["waterfall_decomposition", "actual_vs_predicted", "channel_contribution_share", "saturation_curves"],
)
def test_plots_render_against_real_datatree_idata(fitted_model, tmp_path, plot_type):
    service = PlottingService(artifacts_dir=tmp_path / "plots")
    payload = service.generate_plot(fitted_model, "model_plot", plot_type, fmt="png")
    assert len(payload) > 0
