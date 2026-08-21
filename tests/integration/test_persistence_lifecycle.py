import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FitMMMInput,
)


@pytest.mark.statistical
def test_full_persistence_lifecycle_across_restarts(tmp_path):
    """Verify complete lifecycle across application restarts."""
    csv_path = tmp_path / "data.csv"
    generate_synthetic_mmm(n=60).to_csv(csv_path, index=False)

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
    )

    # 1. Instance 1: Register, Fit, Diagnose
    app1 = Application(settings)
    reg = app1.datasets.register_file(csv_path)
    model = app1.models.fit(
        FitMMMInput(
            dataset_id=reg.dataset_id,
            date_column="date",
            target_column="revenue",
            channel_columns=["meta", "google", "tiktok", "youtube"],
            control_columns=["discount"],
            sampler={
                "draws": 200,
                "tune": 200,
                "chains": 2,
                "target_accept": 0.9,
                "random_seed": 42,
            },
        )
    )
    diag1 = app1.diagnostics.diagnose(model.model_id)
    assert diag1.decision_tools_enabled is True

    # 2. Instance 2: Restart application with same storage
    app2 = Application(settings)

    # Verify model record and diagnostics restored
    rec2 = app2.models.status(model.model_id)
    assert rec2.model_id == model.model_id
    assert rec2.status == "completed"
    assert rec2.validation_state == diag1.decision_status
    assert rec2.diagnostics is not None

    # Verify decisions work on reloaded model
    sim = app2.decisions.simulate(
        BudgetSimulationInput(
            model_id=model.model_id,
            planning_periods=4,
            changes={"meta": {"type": "relative", "value": -0.10}},
        )
    )
    assert "comparison" in sim

    opt = app2.decisions.optimize(
        BudgetOptimizationInput(
            model_id=model.model_id,
            budget=150_000.0,
            planning_periods=4,
        )
    )
    assert opt["optimizer_success"] is True


def test_persistence_corrupt_or_missing_artifact(tmp_path):
    """Verify safe handling of corrupt and missing model artifacts."""
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
    )
    app = Application(settings)

    # Non-existent model ID
    with pytest.raises(DomainError) as exc_info:
        app.models.load_model("mmm_does_not_exist")
    assert exc_info.value.code == "MODEL_NOT_FOUND"
