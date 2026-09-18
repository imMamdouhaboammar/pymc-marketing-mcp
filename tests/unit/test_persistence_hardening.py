from pathlib import Path

import pytest

from marketing_mcp.config import Settings
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.service import JobService
from marketing_mcp.persistence import SQLitePersistenceBackend
from marketing_mcp.security.principal import Principal


def test_settings_resolves_absolute_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(metadata_db=Path("relative/path/test_metadata.db"))
    assert settings.metadata_db.is_absolute()
    assert settings.metadata_db == (tmp_path / "relative/path/test_metadata.db").resolve()
    assert settings.metadata_db.parent.exists()

def test_tenant_scoping_none_and_default_reconciliation(tmp_path):
    db_path = tmp_path / "tenant_test.db"
    backend = SQLitePersistenceBackend(db_path)
    job_service = JobService(backend.jobs)

    # Job created with tenant_id=None (e.g. stdio or legacy)
    job_rec1 = JobRecord(
        job_id="job-none-1",
        job_type="fit_mmm",
        status=JobStatus.QUEUED,
        owner="local",
        tenant_id=None,
        payload={},
    )
    backend.jobs.create_job(job_rec1)

    # Job created with tenant_id="default"
    job_rec2 = JobRecord(
        job_id="job-def-2",
        job_type="fit_mmm",
        status=JobStatus.QUEUED,
        owner="user1",
        tenant_id="default",
        payload={},
    )
    backend.jobs.create_job(job_rec2)

    # Job created with tenant_id="tenant_abc"
    job_rec3 = JobRecord(
        job_id="job-abc-3",
        job_type="fit_mmm",
        status=JobStatus.QUEUED,
        owner="user2",
        tenant_id="tenant_abc",
        payload={},
    )
    backend.jobs.create_job(job_rec3)

    # When queried with default tenant, should see both None and 'default', but NOT 'tenant_abc'
    principal_default = Principal(subject="api-user", auth_type="api_key", scopes=frozenset(["*"]), tenant_id="default")
    jobs_default = job_service.list_jobs(principal=principal_default)
    job_ids_default = {j.job_id for j in jobs_default}
    assert "job-none-1" in job_ids_default
    assert "job-def-2" in job_ids_default
    assert "job-abc-3" not in job_ids_default

    # When queried with tenant_abc, should see only tenant_abc
    principal_abc = Principal(subject="user2", auth_type="api_key", scopes=frozenset(["*"]), tenant_id="tenant_abc")
    jobs_abc = job_service.list_jobs(principal=principal_abc)
    job_ids_abc = {j.job_id for j in jobs_abc}
    assert job_ids_abc == {"job-abc-3"}

    backend.close()

def test_authorize_resource_tenant_reconciliation():
    from marketing_mcp.errors import DomainError
    from marketing_mcp.security.ownership import authorize_resource

    rec_default = {"owner": "user1", "tenant_id": "default"}
    rec_none = {"owner": "user1", "tenant_id": None}
    rec_abc = {"owner": "user1", "tenant_id": "tenant_abc"}

    p_none = Principal(subject="user1", auth_type="api_key", scopes=frozenset(["*"]), tenant_id=None)
    p_default = Principal(subject="user1", auth_type="api_key", scopes=frozenset(["*"]), tenant_id="default")
    p_abc = Principal(subject="user1", auth_type="api_key", scopes=frozenset(["*"]), tenant_id="tenant_abc")

    # Accessing none/default should be mutually permitted for default/none principals
    authorize_resource(p_none, rec_none, "dataset", "read")
    authorize_resource(p_default, rec_default, "dataset", "read")
    authorize_resource(p_none, rec_default, "dataset", "read")
    authorize_resource(p_default, rec_none, "dataset", "read")

    # Cross-tenant access must be rejected
    with pytest.raises(DomainError) as exc:
        authorize_resource(p_none, rec_abc, "dataset", "read")
    assert exc.value.code == "AUTH_FORBIDDEN"

    with pytest.raises(DomainError) as exc:
        authorize_resource(p_default, rec_abc, "dataset", "read")
    assert exc.value.code == "AUTH_FORBIDDEN"

    with pytest.raises(DomainError) as exc:
        authorize_resource(p_abc, rec_default, "dataset", "read")
    assert exc.value.code == "AUTH_FORBIDDEN"

