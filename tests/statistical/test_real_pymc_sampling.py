import numpy as np
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    CalibrateMMMInput,
    CrossValidateMMMInput,
    FitMMMInput,
    LiftTestMeasurement,
    PriorSensitivityInput,
)


@pytest.mark.statistical
def test_real_pymc_mmm_end_to_end_statistical_workflow(tmp_path):
    """Verify genuine PyMC-Marketing Bayesian sampling, contributions, iROAS, simulation, and optimization."""
    df, _truth = generate_synthetic_mmm(n=104, seed=42, return_truth=True)
    csv_path = tmp_path / "synthetic_mmm.csv"
    df.to_csv(csv_path, index=False)

    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    # 1. Dataset Registration & Validation
    reg = app.datasets.register_file(csv_path)
    assert reg.rows == 104
    assert len(reg.fingerprint) == 64

    validation = app.datasets.validate(
        reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
    )
    assert validation.valid_for_modeling is True

    # 2. Real Bayesian Fit (Smoke Profile)
    fit_input = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
        yearly_seasonality=2,
        sampler={
            "draws": 200,
            "tune": 200,
            "chains": 2,
            "target_accept": 0.9,
            "random_seed": 42,
        },
    )
    model_record = app.models.fit(fit_input)
    assert model_record.status == "completed"
    assert model_record.lineage_stage == "initial_fit"
    assert model_record.parent_model_id is None
    assert model_record.package_provenance.get("pymc-marketing") is not None

    # 3. Diagnostics
    diag = app.diagnostics.diagnose(model_record.model_id)
    assert diag.decision_tools_enabled is True
    assert "divergences" in diag.diagnostics
    assert "posterior_predictive_coverage_94" in diag.diagnostics
    assert diag.diagnostics["posterior_predictive_coverage_94"] > 0.60

    # 4. Channel Contributions Verification
    contrib = app.decisions.contributions(model_record.model_id)
    channels_found = {c["channel"] for c in contrib["channels"]}
    assert channels_found == {"meta", "google", "tiktok", "youtube"}

    for ch_info in contrib["channels"]:
        median = ch_info["contribution_median"]
        lower = ch_info["credible_interval"]["lower"]
        upper = ch_info["credible_interval"]["upper"]
        assert np.isfinite(median)
        assert np.isfinite(lower)
        assert np.isfinite(upper)
        assert lower <= median <= upper
        assert median > 0  # Plausible positive marketing contribution

    # 5. Total and Marginal iROAS Verification
    iroas = app.decisions.iroas(model_record.model_id)
    assert iroas["method"] == "pymc_marketing_incrementality"
    assert len(iroas["channels"]) == 4

    for ch_data in iroas["channels"]:
        total_summary = ch_data["total_iroas"]
        marginal_summary = ch_data["marginal_iroas"]

        assert total_summary["lower"] <= total_summary["median"] <= total_summary["upper"]
        assert 0.0 <= total_summary["probability_gt_1"] <= 1.0

        assert marginal_summary["lower"] <= marginal_summary["median"] <= marginal_summary["upper"]
        assert 0.0 <= marginal_summary["probability_gt_1"] <= 1.0

    # 6. Saturated Channel Distinction Test
    for ch_data in iroas["channels"]:
        total_med = ch_data["total_iroas"]["median"]
        marginal_med = ch_data["marginal_iroas"]["median"]
        assert total_med > 0
        assert marginal_med > 0

    # 7. Real Budget Scenario Simulation
    sim_input = BudgetSimulationInput(
        model_id=model_record.model_id,
        planning_periods=4,
        changes={
            "meta": {"type": "relative", "value": -0.20},
            "google": {"type": "relative", "value": 0.15},
        },
    )
    sim_result = app.decisions.simulate(sim_input)
    assert "baseline_response" in sim_result
    assert "scenario_response" in sim_result
    assert "comparison" in sim_result

    comp = sim_result["comparison"]
    assert "probability_scenario_beats_baseline" in comp
    assert 0.0 <= comp["probability_scenario_beats_baseline"] <= 1.0
    assert comp["lower"] <= comp["median"] <= comp["upper"]

    # 8. Real Budget Allocation Optimization
    opt_input = BudgetOptimizationInput(
        model_id=model_record.model_id,
        budget=200_000.0,
        planning_periods=4,
        constraints={
            "meta": {"min": 30_000.0, "max": 70_000.0},
            "google": {"min": 40_000.0, "max": 90_000.0},
        },
    )
    opt_result = app.decisions.optimize(opt_input)
    assert opt_result["optimizer_success"] is True
    recommended = opt_result["recommended_allocation"]
    assert 30_000.0 - 1e-3 <= recommended["meta"] <= 70_000.0 + 1e-3
    assert 40_000.0 - 1e-3 <= recommended["google"] <= 90_000.0 + 1e-3
    assert np.isclose(sum(recommended.values()), 200_000.0, rtol=1e-3)

    # 9. Extrapolation Risk Warning Verification
    extrap_input = BudgetSimulationInput(
        model_id=model_record.model_id,
        planning_periods=4,
        changes={
            "meta": {"type": "relative", "value": 4.0},
        },
    )
    extrap_res = app.decisions.simulate(extrap_input)
    assert len(extrap_res.get("warnings", [])) > 0
    extrap_codes = [w["code"] for w in extrap_res["warnings"]]
    assert "EXTRAPOLATION_RISK" in extrap_codes


@pytest.mark.statistical
def test_real_pymc_lift_test_calibration_and_lineage(tmp_path):
    """Verify model calibration using experimental lift tests and lineage tracking."""
    df = generate_synthetic_mmm(n=60, seed=42)
    csv_path = tmp_path / "synthetic_mmm.csv"
    df.to_csv(csv_path, index=False)

    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    reg = app.datasets.register_file(csv_path)
    base_model = app.models.fit(
        FitMMMInput(
            dataset_id=reg.dataset_id,
            date_column="date",
            target_column="revenue",
            channel_columns=["meta", "google", "tiktok", "youtube"],
            control_columns=["discount"],
            sampler={"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
        )
    )

    cal_input = CalibrateMMMInput(
        model_id=base_model.model_id,
        lift_tests=[
            LiftTestMeasurement(
                channel="meta",
                x=50_000.0,
                delta_x=15_000.0,
                delta_y=35_000.0,
                sigma=4_000.0,
                description="Meta Q2 Incrementality Test",
            ),
            LiftTestMeasurement(
                channel="google",
                x=60_000.0,
                delta_x=20_000.0,
                delta_y=45_000.0,
                sigma=5_000.0,
                description="Google Search Geo Holdout",
            ),
        ],
        sampler={"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
    )
    cal_record = app.models.calibrate(cal_input)
    assert cal_record.status == "completed"
    assert cal_record.lineage_stage == "calibrated"
    assert cal_record.parent_model_id == base_model.model_id

    comparison = app.models.compare_models([base_model.model_id, cal_record.model_id])
    assert comparison["model_count"] == 2
    assert comparison["models"][0]["model_id"] == base_model.model_id
    assert comparison["models"][1]["parent_model_id"] == base_model.model_id


@pytest.mark.statistical
def test_real_pymc_time_slice_cross_validation_and_prior_sensitivity(tmp_path):
    """Verify rolling TimeSliceCrossValidator and prior sensitivity workflows."""
    df = generate_synthetic_mmm(n=60, seed=42)
    csv_path = tmp_path / "synthetic_mmm.csv"
    df.to_csv(csv_path, index=False)

    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    reg = app.datasets.register_file(csv_path)
    model = app.models.fit(
        FitMMMInput(
            dataset_id=reg.dataset_id,
            date_column="date",
            target_column="revenue",
            channel_columns=["meta", "google", "tiktok", "youtube"],
            control_columns=["discount"],
            sampler={"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
        )
    )

    cv_res = app.diagnostics.cross_validate(
        CrossValidateMMMInput(
            model_id=model.model_id,
            n_init=40,
            forecast_horizon=10,
            step_size=10,
            sampler={"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
        )
    )
    assert cv_res["folds"] >= 1
    assert cv_res["mean_out_of_sample_rmse"] > 0
    assert "metrics" in cv_res

    sens_res = app.diagnostics.prior_sensitivity(PriorSensitivityInput(model_id=model.model_id))
    assert "baseline_ranks" in sens_res
    assert "alternative_ranks" in sens_res
    assert sens_res["prior_stability"] in {"robust", "sensitive"}
