"""Three-instance shared metadata and blob lifecycle."""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.process_worker import ProcessJobWorker
from marketing_mcp.jobs.worker_cli import build_fit_mmm_handler
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.principal import Principal
from tests.unit.test_model_artifact_storage import AdapterDouble
from tests.unit.test_plotting_service import _make_fake_model


def _settings(root: Path) -> Settings:
    return Settings(
        data_dir=root / "data",
        ingest_dir=root / "inbox",
        artifact_dir=root / "artifacts",
        metadata_db=root / "metadata.db",
    )


def _csv(path: Path) -> Path:
    pd.DataFrame(
        {
            "date": pd.date_range("2025-01-06", periods=60, freq="W-MON"),
            "sales": range(60),
            "search": range(60),
        }
    ).to_csv(path, index=False)
    return path


def test_api_worker_api_share_dataset_and_model_bytes(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    owner = Principal(subject="analyst", auth_type="oauth", tenant_id="tenant-a")
    source = _csv(tmp_path / "input.csv")

    api_a = Application(_settings(shared))
    registered = api_a.datasets.register_file(source, owner)
    api_a.job_repo.create_job(
        JobRecord(
            job_id="job-shared",
            job_type="fit_mmm",
            owner=owner.subject,
            tenant_id=owner.tenant_id,
            payload={
                "dataset_id": registered.dataset_id,
                "date_column": "date",
                "target_column": "sales",
                "channel_columns": ["search"],
            },
        )
    )
    assert not Path(registered.path).is_absolute()
    api_a.metadata.close()

    api_b = Application(_settings(shared))
    api_b.models.adapter_factory = AdapterDouble
    worker = ProcessJobWorker(
        api_b.job_repo,
        handlers={"fit_mmm": build_fit_mmm_handler(api_b)},
        worker_id="worker-b",
    )
    assert worker.execute_next_job() is True
    completed = api_b.job_repo.get_job("job-shared")
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.result is not None
    model_id = completed.result["model_id"]
    api_b.metadata.close()

    api_c = Application(_settings(shared))
    api_c.models.adapter_factory = AdapterDouble
    stored = api_c.metadata.get_model(model_id)
    assert stored["artifact_path"].startswith("blob://")
    assert stored["artifact_ref"]["sha256"]
    with api_c.models.materialized_model(model_id) as (model, record):
        assert model == b"immutable-model"
        assert record.tenant_id == "tenant-a"
    plots = api_c.plots.generate_all(
        _make_fake_model(), model_id, ["actual_vs_predicted"]
    )
    assert plots["actual_vs_predicted"]["success"] is True
    assert api_c.metadata.get_model(model_id)["plot_refs"]["actual_vs_predicted.png"][
        "sha256"
    ]
    attacker = Principal(subject="other", auth_type="oauth", tenant_id="tenant-b")
    with pytest.raises(DomainError) as forbidden:
        authorize_model(attacker, stored, action="read")
    assert forbidden.value.code == "AUTH_FORBIDDEN"
    api_c.metadata.close()


def test_restored_sqlite_and_blob_backup_reloads_dataset(tmp_path: Path) -> None:
    live = tmp_path / "live"
    backup = tmp_path / "backup"
    source = _csv(tmp_path / "input.csv")
    owner = Principal(subject="analyst", auth_type="oauth", tenant_id="tenant-a")

    original = Application(_settings(live))
    registered = original.datasets.register_file(source, owner)
    original.metadata.close()

    shutil.copytree(live, backup)
    shutil.rmtree(live)
    shutil.copytree(backup, live)

    restored = Application(_settings(live))
    frame = restored.datasets.load(registered.dataset_id)
    assert len(frame) == 60
    assert restored.datasets.inspect(registered.dataset_id).rows == 60
    restored.metadata.close()
