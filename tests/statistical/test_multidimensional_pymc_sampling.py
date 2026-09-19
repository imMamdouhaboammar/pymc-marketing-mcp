import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_multidimensional_mmm
from marketing_mcp.schemas.models import (
    BudgetCellConstraint,
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FitMMMInput,
)


@pytest.mark.statistical
def test_real_multidimensional_mmm_panel_sampling(tmp_path):
    """Verify real Bayesian sampling on a rectangular panel with Riyadh, Jeddah, Dammam."""
    df, _truth = generate_synthetic_multidimensional_mmm(
        n=104, geos=("Riyadh", "Jeddah", "Dammam"), seed=42, return_truth=True
    )
    csv_path = tmp_path / "panel_mmm.csv"
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
    assert reg.rows == 104 * 3

    # Validate rectangular panel
    val = app.datasets.validate(
        reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
        dims=["geo"],
    )
    assert val.valid_for_modeling is True

    # Fit multidimensional MMM
    fit_input = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
        dims=["geo"],
        adstock={"l_max": 4},
        sampler={"draws": 400, "tune": 400, "chains": 2, "target_accept": 0.95, "random_seed": 42},
    )
    model_record = app.models.fit(fit_input)
    assert model_record.status == "completed"

    # Diagnose
    diag = app.diagnostics.diagnose(model_record.model_id)
    assert diag.decision_tools_enabled is True

    # Channel contributions (4 channels)
    contrib = app.decisions.contributions(model_record.model_id)
    assert len(contrib["channels"]) == 4

    # iROAS (12 channel x geo combinations)
    iroas = app.decisions.iroas(model_record.model_id)
    assert len(iroas["channels"]) == 12

    # Multidimensional cell-specific scenario simulation
    sim_input = BudgetSimulationInput(
        model_id=model_record.model_id,
        planning_periods=4,
        cell_changes=[
            {
                "channel": "meta",
                "dimensions": {"geo": "Riyadh"},
                "type": "relative",
                "value": -0.25,
            },
            {
                "channel": "google",
                "dimensions": {"geo": "Jeddah"},
                "type": "relative",
                "value": 0.30,
            },
        ],
    )
    sim_res = app.decisions.simulate(sim_input)
    assert "baseline_response" in sim_res
    assert "scenario_response" in sim_res
    assert "comparison" in sim_res

    # Multidimensional cell-specific budget optimization
    opt_input = BudgetOptimizationInput(
        model_id=model_record.model_id,
        budget=300_000.0,
        planning_periods=4,
        cell_constraints=[
            BudgetCellConstraint(
                channel="meta",
                dimensions={"geo": "Riyadh"},
                min=10_000.0,
                max=50_000.0,
            ),
            BudgetCellConstraint(
                channel="google",
                dimensions={"geo": "Jeddah"},
                min=15_000.0,
                max=60_000.0,
            ),
        ],
    )
    opt_res = app.decisions.optimize(opt_input)
    assert opt_res["optimizer_success"] is True
    assert len(opt_res["recommended_allocation"]["cells"]) == 12
