"""Separate-process acceptance for durable job execution."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.storage.migrations import MigrationRunner


def _repository(path: Path) -> SQLiteJobRepository:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    MigrationRunner(connection).apply_pending()
    return SQLiteJobRepository(connection)


def test_queued_job_completes_after_submitting_process_exits(tmp_path: Path) -> None:
    database = tmp_path / "shared-jobs.db"
    submitter = _repository(database)
    submitter.create_job(
        JobRecord(
            job_id="job-separate-process",
            job_type="test.echo",
            owner="analyst",
            tenant_id="tenant-a",
            payload={"value": "persisted"},
        )
    )
    submitter.conn.close()

    worker_code = """
import sqlite3
import sys
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.storage.migrations import MigrationRunner

connection = sqlite3.connect(sys.argv[1])
connection.row_factory = sqlite3.Row
MigrationRunner(connection).apply_pending()
repository = SQLiteJobRepository(connection)
worker = ProcessJobWorker(
    repository,
    handlers={"test.echo": lambda job: {"value": job.payload["value"], "tenant": job.tenant_id}},
    worker_id="worker-child",
)
raise SystemExit(0 if worker.execute_next_job() else 2)
"""
    result = subprocess.run(
        [sys.executable, "-c", worker_code, str(database)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    observer = _repository(database)
    completed = observer.get_job("job-separate-process")
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.result == {"value": "persisted", "tenant": "tenant-a"}
    assert completed.attempts == 1
    assert completed.lease_owner is None
    observer.conn.close()


def test_standalone_worker_cli_executes_real_job_lifecycle(tmp_path: Path) -> None:
    """Acceptance test verifying separate-process worker CLI handles compute jobs end-to-end."""
    import numpy as np
    import pandas as pd

    from marketing_mcp.app import Application
    from marketing_mcp.config import Settings
    from marketing_mcp.security.principal import Principal

    database = tmp_path / "metadata.db"
    data_dir = tmp_path / "data"
    artifact_dir = tmp_path / "artifacts"
    settings = Settings(
        metadata_db=database,
        data_dir=data_dir,
        artifact_dir=artifact_dir,
        ingest_dir=tmp_path,
        job_execution_mode="enqueue-only",
    )
    app = Application(settings)
    principal = Principal(
        subject="worker_analyst",
        tenant_id="tenant_worker",
        scopes=frozenset({"marketing:read", "marketing:model", "marketing:decide"}),
        auth_type="api_key",
    )

    # 1. Register raw panel dataset
    np.random.seed(42)
    n_weeks = 52
    dates = pd.date_range("2024-01-01", periods=n_weeks, freq="W-MON").strftime("%Y-%m-%d").tolist()
    records = []
    for country in ["US", "UK"]:
        for dt in dates:
            spend_m = float(np.random.uniform(100.0, 300.0))
            rev = float(500.0 + 2.0 * spend_m + np.random.normal(0, 1.0))
            records.append({
                "date": dt,
                "market": country,
                "channel_name": "Spend",
                "spend_amount": spend_m,
                "revenue_usd": rev,
            })
    df_raw = pd.DataFrame(records)
    raw_reg = app.datasets.register_bytes(df_raw.to_csv(index=False).encode(), "csv", principal=principal)

    # Helper to run separate worker process
    def _run_worker_once():
        cmd = [
            sys.executable,
            "-m",
            "marketing_mcp.jobs.worker_cli",
            "--db",
            str(database),
            "--data-dir",
            str(data_dir),
            "--artifact-dir",
            str(artifact_dir),
            "--once",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"Worker process failed: {res.stdout}\n{res.stderr}"

    # -------------------------------------------------------------------------
    # Test Job 1: transform_ad_export in separate process
    # -------------------------------------------------------------------------
    trans_job = app.jobs.submit_job(
        job_type="transform_ad_export",
        payload={
            "dataset_id": raw_reg.dataset_id,
            "date_column": "date",
            "channel_column": "channel_name",
            "spend_column": "spend_amount",
            "target_columns": ["revenue_usd"],
            "dimension_columns": ["market"],
            "frequency": "W-MON",
        },
        principal=principal,
    )
    _run_worker_once()
    trans_rec = app.jobs.get_job(trans_job.job_id, principal=principal)
    assert trans_rec.status == JobStatus.SUCCEEDED
    assert "transformed_dataset_id" in trans_rec.result
    transformed_dataset_id = trans_rec.result["transformed_dataset_id"]

    # -------------------------------------------------------------------------
    # Test Job 2: fit_mmm in separate process
    # -------------------------------------------------------------------------
    fit_job = app.jobs.submit_job(
        job_type="fit_mmm",
        payload={
            "dataset_id": transformed_dataset_id,
            "date_column": "date",
            "target_column": "revenue_usd",
            "channel_columns": ["spend_spend"],
            "dims": ["market"],
            "adstock": {"type": "geometric"},
            "saturation": {"type": "tanh"},
            "sampler": {"draws": 250, "tune": 250, "chains": 2, "target_accept": 0.9, "random_seed": 42},
        },
        principal=principal,
    )
    _run_worker_once()
    fit_rec = app.jobs.get_job(fit_job.job_id, principal=principal)
    assert fit_rec.status == JobStatus.SUCCEEDED, f"fit_mmm failed: {fit_rec.error}"
    assert "model_id" in fit_rec.result
    model_id = fit_rec.result["model_id"]

    # Run diagnostics on fitted model to approve it for downstream decisions
    diag_res = app.diagnostics.diagnose(model_id)
    assert diag_res.decision_status in ("approved", "approved_with_caution"), f"Diagnostics failed: {diag_res.failures}"

    # -------------------------------------------------------------------------
    # Test Job 3: budget_optimize in separate process
    # -------------------------------------------------------------------------
    opt_job = app.jobs.submit_job(
        job_type="budget_optimize",
        payload={
            "model_id": model_id,
            "budget": 5000.0,
            "planning_periods": 4,
        },
        principal=principal,
    )
    _run_worker_once()
    opt_rec = app.jobs.get_job(opt_job.job_id, principal=principal)
    assert opt_rec.status == JobStatus.SUCCEEDED, f"Budget optimize failed: {opt_rec.error}"
    assert "recommended_allocation" in opt_rec.result

    # -------------------------------------------------------------------------
    # Test Job 4: flighting_optimize in separate process
    # -------------------------------------------------------------------------
    flight_job = app.jobs.submit_job(
        job_type="flighting_optimize",
        payload={
            "model_id": model_id,
            "total_budget": 10000.0,
            "planning_weeks": 4,
            "objective": "maximize_response",
        },
        principal=principal,
    )
    _run_worker_once()
    flight_rec = app.jobs.get_job(flight_job.job_id, principal=principal)
    assert flight_rec.status == JobStatus.SUCCEEDED, f"Flighting failed: {flight_rec.error}"

    # -------------------------------------------------------------------------
    # Test Job 5: cross_validate_mmm in separate process
    # -------------------------------------------------------------------------
    cv_job = app.jobs.submit_job(
        job_type="cross_validate_mmm",
        payload={
            "model_id": model_id,
            "n_init": 50,
            "forecast_horizon": 2,
            "step_size": 2,
            "sampler": {"draws": 50, "tune": 50, "chains": 2, "random_seed": 42},
        },
        principal=principal,
    )
    _run_worker_once()
    cv_rec = app.jobs.get_job(cv_job.job_id, principal=principal)
    assert cv_rec.status == JobStatus.SUCCEEDED, f"CV failed: {cv_rec.error}"
    assert "mean_out_of_sample_rmse" in cv_rec.result

    # -------------------------------------------------------------------------
    # Test Job 6: prior_sensitivity in separate process
    # -------------------------------------------------------------------------
    sens_job = app.jobs.submit_job(
        job_type="prior_sensitivity",
        payload={
            "model_id": model_id,
        },
        principal=principal,
    )
    _run_worker_once()
    sens_rec = app.jobs.get_job(sens_job.job_id, principal=principal)
    assert sens_rec.status == JobStatus.SUCCEEDED
    assert sens_rec.result.get("model_id") == model_id

    app.metadata.close()

