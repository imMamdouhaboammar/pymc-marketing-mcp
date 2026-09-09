"""Provider-neutral persistence composition and local multi-instance contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord
from marketing_mcp.persistence import SQLitePersistenceBackend


def test_production_never_silently_falls_back_to_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "must-not-exist.db"
    settings = Settings(
        metadata_db=database,
        security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
        oauth_issuer="https://issuer.example.com/",
        oauth_audience="pymc-marketing-mcp",
    )

    with pytest.raises(DomainError) as invalid:
        Application(settings)
    assert invalid.value.code == "CONFIG_INVALID"
    assert not database.exists()


def test_unconfigured_shared_sql_backend_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(DomainError) as missing_url:
        Settings(persistence_backend="shared-sql")
    assert missing_url.value.code == "CONFIG_INVALID"

    settings = Settings(
        persistence_backend="shared-sql",
        shared_sql_url="postgresql://example.invalid/marketing",
    )
    with pytest.raises(DomainError) as unavailable:
        Application(settings)
    assert unavailable.value.code == "DEPENDENCY_UNAVAILABLE"
    assert not (tmp_path / "metadata.db").exists()


def test_two_local_backend_instances_share_metadata_jobs_and_probe(tmp_path: Path) -> None:
    database = tmp_path / "shared.db"
    first = SQLitePersistenceBackend(database)
    second = SQLitePersistenceBackend(database)
    try:
        first.metadata.put_dataset({"dataset_id": "d1", "owner": "analyst"})
        assert second.metadata.get_dataset("d1")["owner"] == "analyst"
        first.jobs.create_job(JobRecord(job_id="j1", job_type="test.echo"))
        assert second.jobs.claim_next_job(worker_id="worker-b") is not None
        first.probe()
        second.probe()
    finally:
        first.close()
        second.close()
