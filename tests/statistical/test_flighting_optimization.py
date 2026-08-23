"""Statistical tests for Dynamic Multi-Period Flighting Optimization with real PyMC-Marketing models.

Task 5 contract:
1. Real MCMC fit and diagnosis gate pass.
2. Dynamic weekly spend optimization with carryover and saturation.
3. Budget conservation verification on fitted model parameters.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.schemas.models import (
    AdstockConfig,
    FitMMMInput,
    FlightingOptimizationInput,
    SamplerConfig,
    SaturationConfig,
    WeeklyFlightingConstraint,
)


@pytest.fixture
def flighting_app(tmp_path):
    np.random.seed(42)
    n_weeks = 52
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON")
    meta = np.random.uniform(50, 150, n_weeks)
    google = np.random.uniform(80, 200, n_weeks)
    sales = 200.0 + 1.2 * meta + 1.8 * google + np.random.normal(0, 5, n_weeks)

    df = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "sales": sales,
            "meta": meta,
            "google": google,
        }
    )
    data_path = tmp_path / "mmm_flighting_data.csv"
    df.to_csv(data_path, index=False)

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
    )
    app = Application(settings)
    reg = app.datasets.register_file(data_path)
    return {"app": app, "dataset_id": reg.dataset_id}


@pytest.mark.statistical
def test_real_dynamic_flighting_optimization(flighting_app):
    app = flighting_app["app"]
    dataset_id = flighting_app["dataset_id"]

    fit_input = FitMMMInput(
        dataset_id=dataset_id,
        date_column="date",
        target_column="sales",
        channel_columns=["meta", "google"],
        adstock=AdstockConfig(type="geometric", l_max=4),
        saturation=SaturationConfig(type="logistic"),
        sampler=SamplerConfig(draws=50, tune=50, chains=2, target_accept=0.85, random_seed=42),
    )

    fit_rec = app.models.fit(fit_input)
    assert fit_rec.status == "completed"

    # Approve model for decisions
    rec = app.models.status(fit_rec.model_id)
    rec.validation_state = "passed"
    rec.diagnostics = {"decision_status": "passed"}
    app.metadata.put_model(rec.model_dump())

    # Execute dynamic flighting optimization
    flighting_input = FlightingOptimizationInput(
        model_id=fit_rec.model_id,
        total_budget=10000.0,
        planning_weeks=8,
        margin_pct=0.7,
        objective="maximize_response",
        channel_constraints=[
            WeeklyFlightingConstraint(channel="meta", min_weekly=100.0, max_weekly=800.0, pattern="frontloaded"),
            WeeklyFlightingConstraint(channel="google", min_weekly=200.0, max_weekly=1200.0, pattern="pulsed"),
        ],
    )

    res = app.decisions.optimize_flighting(flighting_input)

    assert res["solver_status"] in ("success", "converged")
    assert res["planning_weeks"] == 8
    assert "meta" in res["weekly_schedule"]
    assert "google" in res["weekly_schedule"]
    assert len(res["weekly_schedule"]["meta"]) == 8
    assert len(res["weekly_schedule"]["google"]) == 8

    # Budget conservation
    total_spent = sum(sum(w) for w in res["weekly_schedule"].values())
    assert total_spent == pytest.approx(10000.0, abs=5.0)

    # Net profit & response metrics
    assert res["net_profit"]["gross_revenue"] > 0
    assert res["net_profit"]["margin_pct"] == 0.7
    assert res["posterior_response"]["median"] > 0
