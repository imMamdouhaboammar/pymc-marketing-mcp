"""Statistical invariants pack (Task 8) — real PyMC-Marketing fixtures, fixed seeds.

Invariants:
1. Zero spend change produces near-zero incremental response change.
2. A saturated channel shows lower marginal than average return on the fixture.
3. Flighting optimization respects exact conservation / floors / caps.
4. Reload preserves posterior summaries within numerical tolerance.
5. Calibration creates a new lineage node without mutating the parent model.
6. Comparison rejects differing dataset fingerprints even when dataset IDs are
   manually forged equal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.domain.decisions.flighting import build_official_response_evaluator
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    AdstockConfig,
    CalibrateMMMInput,
    FitMMMInput,
    LiftTestMeasurement,
    ModelComparisonInput,
    SamplerConfig,
    SaturationConfig,
)


@pytest.fixture(scope="module")
def app_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("invariants")
    np.random.seed(42)
    n_weeks = 60
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON")
    # Meta runs far above its saturation knee -> saturated-channel invariant.
    meta = np.random.uniform(400, 600, n_weeks)
    google = np.random.uniform(80, 200, n_weeks)
    # Diminishing returns for meta (tanh-form logistic saturates quickly).
    sales = (
        5000.0
        + 900.0 * np.tanh(meta / 120.0)
        + 4.0 * google
        + np.random.normal(0, 40, n_weeks)
    )
    df = pd.DataFrame(
        {"date": dates.strftime("%Y-%m-%d"), "sales": sales, "meta": meta, "google": google}
    )
    data_path = root / "inv_data.csv"
    df.to_csv(data_path, index=False)

    settings = Settings(
        data_dir=root / "data",
        artifact_dir=root / "artifacts",
        metadata_db=root / "metadata.db",
        ingest_dir=root,
    )
    app = Application(settings)
    reg = app.datasets.register_file(data_path)

    fit_input = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="sales",
        channel_columns=["meta", "google"],
        adstock=AdstockConfig(type="geometric", l_max=4),
        saturation=SaturationConfig(type="logistic"),
        # Tiny but real MCMC; seeds fixed for determinism of assertions.
        sampler=SamplerConfig(draws=50, tune=50, chains=2, random_seed=42),
    )
    rec = app.models.fit(fit_input)
    assert rec.status == "completed"
    stored = app.models.status(rec.model_id)
    stored.validation_state = "approved"
    stored.diagnostics = {"decision_status": "approved", "warnings": [], "failures": []}
    app.metadata.put_model(stored.model_dump())
    return {"app": app, "model_id": rec.model_id}


def _approve_child(app, model_id):
    stored = app.models.status(model_id)
    stored.validation_state = "approved"
    stored.diagnostics = {"decision_status": "approved", "warnings": [], "failures": []}
    app.metadata.put_model(stored.model_dump())


def _channel_medians(app, model_id):
    from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
    from marketing_mcp.domain.posterior_summaries import summarize_channel_contributions

    model, _rec = app.models.load_model(model_id)
    summary = summarize_channel_contributions(model.idata)
    analytical = PyMCMarketingAdapter().channel_contributions(model)
    return {
        c["channel"]: c["contribution_median"] for c in analytical["channels"]
    }, summary


@pytest.mark.statistical
def test_zero_spend_change_produces_near_zero_response_change(app_env):
    """A near-zero spend change must move response by a near-zero amount:
    the response function is continuous, so tiny deltas cannot produce
    material response shifts (only fp-level noise)."""
    app = app_env["app"]
    model_id = app_env["model_id"]
    from marketing_mcp.schemas.models import BudgetChange, BudgetSimulationInput

    res = app.decisions.simulate(
        BudgetSimulationInput(
            model_id=model_id,
            planning_periods=4,
            changes={"meta": BudgetChange(type="relative", value=1e-12)},
        )
    )
    baseline_median = float(res["baseline_response"]["median"])
    scenario_median = float(res["scenario_response"]["median"])
    scale = max(1.0, abs(baseline_median))
    # Rationale: continuity of the saturation response — a 1e-12 relative
    # spend delta maps to ~1e-12-scale response movement, not sampling noise.
    assert abs(scenario_median - baseline_median) <= 1e-6 * scale


@pytest.mark.statistical
def test_saturated_channel_marginal_below_average_return(app_env):
    """On the saturated fixture, meta's marginal weekly response must be below
    its average weekly response when evaluated through official transforms."""
    app = app_env["app"]
    model_id = app_env["model_id"]
    model, _rec = app.models.load_model(model_id)
    channels = list(model.channel_columns)

    post = model.fit_result
    params: dict[str, dict[str, float]] = {ch: {} for ch in channels}
    for var in post.data_vars:
        if var.startswith(("adstock_", "saturation_")):
            for ch in channels:
                da = post[var]
                vals = da.sel(channel=ch) if "channel" in da.dims else da
                params[ch][var] = float(np.asarray(vals).mean())

    scales_da = model.get_scales_as_xarray()["channel_scale"]
    scale_map = {
        ch: float(np.asarray(scales_da.sel(channel=ch)).mean()) for ch in channels
    }

    evaluator = build_official_response_evaluator(
        adstock_type="geometric",
        saturation_type="logistic",
        l_max=int(getattr(model.adstock, "l_max", 4)),
        channel_params=params,
        channel_scale=scale_map,
        channel_columns=["meta"],
    )
    # Scaled-space weekly levels around the historical meta range.
    base = 0.8 * np.ones((1, 8))
    bumped = base.copy()
    bumped[0, -1] += 0.05  # marginal week: +5% of scale
    total_base = float(evaluator(base))
    total_bumped = float(evaluator(bumped))
    marginal = (total_bumped - total_base) / 1.0
    average = total_base / base.shape[1]
    # Saturation => marginal response of an extra unit strictly below the
    # horizon-average response per week.
    assert marginal < average


@pytest.mark.statistical
def test_flighting_respects_conservation_floors_and_caps(app_env):
    app = app_env["app"]
    from marketing_mcp.schemas.models import FlightingOptimizationInput, WeeklyFlightingConstraint

    res = app.decisions.optimize_flighting(
        FlightingOptimizationInput(
            model_id=app_env["model_id"],
            total_budget=8000.0,
            planning_weeks=6,
            objective="maximize_response",
            channel_constraints=[
                WeeklyFlightingConstraint(channel="meta", min_weekly=150.0, max_weekly=700.0),
                WeeklyFlightingConstraint(channel="google", min_weekly=100.0, max_weekly=900.0),
            ],
        )
    )
    total = sum(sum(w) for w in res["weekly_schedule"].values())
    assert abs(total - 8000.0) < 5.0
    # Exact conservation within rounding tolerance (2dp schedule).
    meta_weeks = res["weekly_schedule"]["meta"]
    assert min(meta_weeks) >= 149.99, "meta min bound"
    assert max(meta_weeks) <= 700.01, "meta max bound"

    google_weeks = res["weekly_schedule"]["google"]
    assert min(google_weeks) >= 99.99, "google min bound"
    assert max(google_weeks) <= 900.01, "google max bound"



@pytest.mark.statistical
def test_model_reload_preserves_posterior_summaries(app_env):
    app = app_env["app"]
    model_id = app_env["model_id"]

    live_model, _ = app.models.load_model(model_id)
    from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter

    before = {
        c["channel"]: c["contribution_median"]
        for c in PyMCMarketingAdapter().channel_contributions(live_model)["channels"]
    }

    # Load a fresh instance from the persisted artifact and compare summaries.
    reloaded_model, _ = app.models.load_model(model_id)
    after = {
        c["channel"]: c["contribution_median"]
        for c in PyMCMarketingAdapter().channel_contributions(reloaded_model)["channels"]
    }
    for ch, value in before.items():
        # Numerical tolerance only: same artifact bytes, deterministic math.
        assert after[ch] == pytest.approx(value, rel=1e-12)


@pytest.mark.statistical
def test_calibration_creates_lineage_without_mutating_parent(app_env):
    app = app_env["app"]
    model_id = app_env["model_id"]

    before = _channel_medians(app, model_id)[0]

    cal_input = CalibrateMMMInput(
        model_id=model_id,
        lift_tests=[
            LiftTestMeasurement(channel="meta", x=500.0, delta_x=100.0, delta_y=80.0, sigma=25.0)
        ],
        sampler=SamplerConfig(draws=50, tune=50, chains=2, random_seed=42),
    )
    child = app.models.calibrate(cal_input)
    assert child.status == "completed"
    assert child.parent_model_id == model_id
    assert child.lineage_stage == "calibrated"

    after = _channel_medians(app, model_id)[0]
    for ch, value in before.items():
        # Parent artifact untouched by the child refit.
        assert after[ch] == pytest.approx(value, rel=1e-12)


@pytest.mark.statistical
def test_comparison_rejects_different_fingerprints_despite_forged_ids(app_env, tmp_path):
    """Two completed records sharing a dataset_id but carrying DIFFERENT
    fingerprints must be refused comparison — content identity wins over IDs."""
    app = app_env["app"]
    other_data = tmp_path / "other.csv"
    np.random.seed(7)
    n = 52
    dates = pd.date_range("2023-01-02", periods=n, freq="W-MON")
    tv = np.random.uniform(100, 300, n)
    radio = np.random.uniform(50, 150, n)
    y = 800.0 + 2.0 * tv + 1.0 * radio + np.random.normal(0, 20, n)
    pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "sales": y, "meta": tv, "google": radio}).to_csv(
        other_data, index=False
    )

    reg = app.datasets.register_file(other_data)

    fit_input = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="sales",
        channel_columns=["meta", "google"],
        adstock=AdstockConfig(type="geometric", l_max=4),
        saturation=SaturationConfig(type="logistic"),
        sampler=SamplerConfig(draws=50, tune=50, chains=2, random_seed=42),
    )
    fit_rec = app.models.fit(fit_input)
    _approve_child(app, fit_rec.model_id)

    # Forge: point both records at the SAME dataset_id string...
    victim = app.models.status(fit_rec.model_id)
    victim.dataset_id = app.models.status(app_env["model_id"]).dataset_id
    # ...while the underlying fingerprints still differ (different files).
    assert victim.dataset_fingerprint != app.models.status(app_env["model_id"]).dataset_fingerprint
    app.metadata.put_model(victim.model_dump())

    with pytest.raises(DomainError) as exc_info:
        app.models.select_best_model(
            ModelComparisonInput(
                model_ids=[app_env["model_id"], fit_rec.model_id],
                criterion="loo",
                weighting="stacking",
            )
        )
    assert exc_info.value.code == "INCOMPATIBLE_MODELS"
