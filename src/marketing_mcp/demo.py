from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.schemas.models import (
    BudgetOptimizationInput,
    BudgetSimulationInput,
    FitMMMInput,
)


def main():
    parser = argparse.ArgumentParser(description="PyMC Marketing MCP local demonstration")
    parser.add_argument(
        "--fast", action="store_true", help="Use fewer posterior draws for a local smoke demo"
    )
    args = parser.parse_args()

    work = Path(".demo-runtime")
    work.mkdir(exist_ok=True)
    csv_path = work / "synthetic_mmm.csv"
    generate_synthetic_mmm().to_csv(csv_path, index=False)

    app = Application(
        Settings(
            data_dir=work / "data",
            artifact_dir=work / "artifacts",
            metadata_db=work / "metadata.db",
            ingest_dir=work,
        )
    )

    reg = app.datasets.register_file(csv_path)
    print("1. Register Dataset:", reg.model_dump())

    insp = app.datasets.inspect(reg.dataset_id)
    print("2. Inspect Dataset candidate:", insp.mmm_candidate)

    val = app.datasets.validate(
        reg.dataset_id,
        "date",
        "revenue",
        ["meta", "google", "tiktok", "youtube"],
        ["discount"],
    )
    print("3. Validate Dataset:", val.valid_for_modeling)

    cfg = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta", "google", "tiktok", "youtube"],
        control_columns=["discount"],
        yearly_seasonality=2,
        sampler={
            "draws": 200 if args.fast else 1000,
            "tune": 200 if args.fast else 1000,
            "chains": 2 if args.fast else 4,
            "target_accept": 0.9,
            "random_seed": 42,
        },
    )
    model = app.models.fit(cfg)
    print("4. Fitted Model ID:", model.model_id)

    diag = app.diagnostics.diagnose(model.model_id)
    print("5. Diagnostic Status:", diag.decision_status)

    contrib = app.decisions.contributions(model.model_id)
    print("6. Channel Contributions:", json.dumps(contrib["channels"][:2], indent=2))

    iroas = app.decisions.iroas(model.model_id)
    print("7. Incremental ROAS:", json.dumps(iroas["channels"][:2], indent=2))

    sim = app.decisions.simulate(
        BudgetSimulationInput(
            model_id=model.model_id,
            planning_periods=8,
            changes={
                "meta": {"type": "relative", "value": -0.20},
                "google": {"type": "relative", "value": 0.15},
            },
        )
    )
    print("8. Budget Simulation:", json.dumps(sim["comparison"], indent=2))

    opt = app.decisions.optimize(
        BudgetOptimizationInput(
            model_id=model.model_id,
            budget=2_500_000.0,
            planning_periods=8,
        )
    )
    print("9. Budget Optimization:", json.dumps(opt["recommended_allocation"], indent=2))
    print("10. Completed! Decisions conditional on Bayesian posterior with uncertainty bounds.")


if __name__ == "__main__":
    main()
