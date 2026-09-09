"""Production-profile agent safety: gates stay closed without weakening policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.persistence import SQLitePersistenceBackend
from marketing_mcp.schemas.models import BudgetOptimizationInput
from marketing_mcp.security.ownership import authorize_model
from marketing_mcp.security.principal import Principal


def test_rejected_and_undiagnosed_models_cannot_optimize(tmp_path: Path) -> None:
    persistence = SQLitePersistenceBackend(tmp_path / "metadata.db")
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
            security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
            oauth_issuer="https://issuer.example.com/",
            oauth_audience="pymc-marketing-mcp",
        ),
        persistence=persistence,
    )
    app.metadata.put_model(
        {
            "model_id": "rejected-child",
            "dataset_id": "d1",
            "parent_model_id": "approved-parent",
            "lineage_stage": "calibrated",
            "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
            "created_at": "2026-09-08T00:00:00Z",
            "updated_at": "2026-09-08T00:00:00Z",
            "validation_state": "not_diagnosed",
            "diagnostics": None,
        }
    )
    with pytest.raises(DomainError) as undiagnosed:
        app.decisions.optimize(
            BudgetOptimizationInput(model_id="rejected-child", budget=1000.0, planning_periods=4)
        )
    assert undiagnosed.value.code == "MODEL_NOT_DIAGNOSED"

    app.metadata.put_model(
        {
            "model_id": "rejected-child",
            "dataset_id": "d1",
            "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
            "created_at": "2026-09-08T00:00:00Z",
            "updated_at": "2026-09-08T00:00:00Z",
            "validation_state": "rejected",
            "diagnostics": {"failures": [{"code": "DIVERGENCES"}]},
        }
    )
    with pytest.raises(DomainError) as rejected:
        app.decisions.optimize(
            BudgetOptimizationInput(model_id="rejected-child", budget=1000.0, planning_periods=4)
        )
    assert rejected.value.code == "MODEL_NOT_VALIDATED"
    persistence.close()


def test_cross_tenant_and_missing_provider_credentials_do_not_green_gates(
    tmp_path: Path,
) -> None:
    persistence = SQLitePersistenceBackend(tmp_path / "metadata.db")
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
            security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
            oauth_issuer="https://issuer.example.com/",
            oauth_audience="pymc-marketing-mcp",
        ),
        persistence=persistence,
    )
    record = {
        "model_id": "mmm_tenant_a",
        "tenant_id": "tenant-a",
        "owner": "analyst",
        "status": "completed",
    }
    app.metadata.put_model(record)
    attacker = Principal(subject="other", auth_type="oauth", tenant_id="tenant-b")
    with pytest.raises(DomainError) as forbidden:
        authorize_model(attacker, record, action="read")
    assert forbidden.value.code == "AUTH_FORBIDDEN"
    assert app.settings.persistence_backend == "sqlite"
    assert "release_authorized" not in record
    persistence.close()
