from __future__ import annotations

import asyncio
import json

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


class ContextState:
    current: ExecutionContext = ExecutionContext()


def _call(server, tool, args, context: ExecutionContext):
    ContextState.current = context
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.fixture
def multi_tenant_harness(tmp_path):
    data_dir = tmp_path / "data"
    artifact_dir = tmp_path / "artifacts"
    metadata_db = tmp_path / "metadata.db"
    inbox_dir = tmp_path / "inbox"
    data_dir.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    inbox_dir.mkdir(parents=True)

    settings = Settings(
        data_dir=data_dir,
        artifact_dir=artifact_dir,
        metadata_db=metadata_db,
        ingest_dir=inbox_dir,
        max_dataset_mb=10,
        auth_enabled=False,
    )
    app = Application(settings)
    server = create_server(app, context_provider=lambda: ContextState.current)

    # Principals
    p_a = Principal(subject="alice", auth_type="api_key", tenant_id="tenant_a", scopes=frozenset(["marketing:admin", "marketing:write", "marketing:read"]))
    p_b = Principal(subject="bob", auth_type="api_key", tenant_id="tenant_b", scopes=frozenset(["marketing:admin", "marketing:write", "marketing:read"]))
    p_stdio = Principal(subject="local", auth_type="stdio", tenant_id=None, scopes=frozenset(["marketing:admin", "marketing:write", "marketing:read"]))

    return server, app, p_a, p_b, p_stdio


def test_adversarial_tenant_isolation_datasets(multi_tenant_harness):
    server, app, p_a, p_b, p_stdio = multi_tenant_harness

    # Tenant A registers a dataset
    reg_a = app.datasets.register_bytes(
        b"date,sales,google_spend\n2026-01-01,100,50\n2026-01-02,120,60\n",
        filename="tenant_a.csv",
        principal=p_a,
    )
    dataset_a_id = reg_a.dataset_id

    # 1. Database-level list scoping: metadata.list_datasets(tenant_id="tenant_b") must be empty
    datasets_b = app.metadata.list_datasets(tenant_id="tenant_b")
    assert len(datasets_b) == 0, "MetadataStore.list_datasets leaked Tenant A dataset to Tenant B"

    # 2. Database-level get scoping: metadata.get_dataset(dataset_a_id, tenant_id="tenant_b") must fail safely
    with pytest.raises(DomainError) as exc_info:
        app.metadata.get_dataset(dataset_a_id, tenant_id="tenant_b")
    assert exc_info.value.code == "DATASET_NOT_FOUND"
    # Verify no tenant name leakage in error message
    assert "tenant_a" not in str(exc_info.value.message)
    assert "tenant_a" not in str(exc_info.value.evidence)

    # 3. Tool-level adversarial access: Tenant B attempts to inspect Tenant A's dataset
    ctx_b = ExecutionContext(principal=p_b)
    res = _call(server, "inspect_dataset", {"dataset_id": dataset_a_id}, ctx_b)
    # Must fail with NOT_FOUND or safe forbidden that does not reveal tenant_a
    assert res.get("is_error") is True or "error" in res or res.get("code") in ("DATASET_NOT_FOUND", "AUTH_FORBIDDEN")
    res_str = json.dumps(res)
    assert "tenant_a" not in res_str, f"Leakage detected: 'tenant_a' was leaked in response: {res_str}"


def test_adversarial_tenant_isolation_jobs_and_recovery(multi_tenant_harness):
    server, app, p_a, p_b, p_stdio = multi_tenant_harness

    # Tenant A creates a job
    job_record_a = JobRecord(
        job_id="job_alice_12345",
        job_type="fit_mmm",
        status=JobStatus.QUEUED,
        owner=p_a.subject,
        tenant_id=p_a.tenant_id,
        idempotency_key="idemp_alice_999",
        payload={"dataset_id": "ds_a"},
    )
    app.jobs.repo.create_job(job_record_a)

    # 1. Tenant B lists jobs -> must not see Tenant A job
    jobs_b = app.jobs.repo.list_jobs(tenant_id="tenant_b")
    assert len(jobs_b) == 0

    # 2. Tenant B queries Tenant A job by ID directly -> must raise JOB_NOT_FOUND (not leak existence)
    with pytest.raises(DomainError) as exc_info:
        app.jobs.repo.get_job("job_alice_12345", tenant_id="tenant_b")
    assert exc_info.value.code == "JOB_NOT_FOUND"

    # 3. Tenant B attempts recovery via tool
    ctx_b = ExecutionContext(principal=p_b)
    res = _call(server, "recover_execution_state", {"job_id_or_key": "job_alice_12345"}, ctx_b)
    assert res.get("is_error") is True or res.get("code") == "JOB_NOT_FOUND" or "error" in res
    assert "tenant_a" not in json.dumps(res)

    # 4. Tenant B attempts recovery via idempotency key
    res_idemp = _call(server, "recover_execution_state", {"job_id_or_key": "idemp_alice_999"}, ctx_b)
    assert res_idemp.get("is_error") is True or res_idemp.get("code") == "JOB_NOT_FOUND" or "error" in res_idemp
    assert "tenant_a" not in json.dumps(res_idemp)
