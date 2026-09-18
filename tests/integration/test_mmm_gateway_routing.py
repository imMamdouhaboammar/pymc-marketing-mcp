"""Integration tests for UP-063: Route MMM fit/job/status tools to platform API with immediate job ticket return."""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from marketing_mcp.adapters.platform_client import PlatformClient
from marketing_mcp.config import Settings


@pytest.fixture
def client_with_org() -> PlatformClient:
    settings = Settings(
        gateway_url="http://127.0.0.1:8080",
        organization_id=str(uuid4()),
        principal_id=str(uuid4()),
        principal_role="analyst",
        platform_client_enabled=True,
    )
    return PlatformClient(settings)


@pytest.mark.anyio
async def test_dispatch_run_returns_immediate_job_ticket(client_with_org):
    """UP-063: Dispatching run returns immediate job_id and run_id without blocking for MCMC."""
    project_id = uuid4()
    model_spec_ver_id = uuid4()
    ds_ver_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/runs"
        assert request.headers.get("x-organization-id") == str(client_with_org.organization_id)
        assert request.headers.get("x-trace-id") == "trace-up063-dispatch"
        body = json.loads(request.content)
        assert body["project_id"] == str(project_id)
        assert body["model_spec_version_id"] == str(model_spec_ver_id)
        assert body["dataset_version_id"] == str(ds_ver_id)
        assert body["requested_via"] == "mcp"

        return httpx.Response(
            201,
            json={
                "run": {
                    "schema_version": "1.0",
                    "run_id": str(run_id),
                    "organization_id": str(client_with_org.organization_id),
                    "project_id": str(project_id),
                    "model_spec_version_id": str(model_spec_ver_id),
                    "dataset_version_id": str(ds_ver_id),
                    "status": "queued",
                    "decision_status": "not_evaluated",
                    "requested_via": "mcp",
                },
                "job": {
                    "schema_version": "1.0",
                    "job_id": str(job_id),
                    "run_id": str(run_id),
                    "organization_id": str(client_with_org.organization_id),
                    "project_id": str(project_id),
                    "status": "queued",
                    "stage": "validating",
                    "progress_percent": 0,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080") as http_c:
        client_with_org._http_client = http_c
        res = await client_with_org.dispatch_run(
            project_id=project_id,
            model_spec_version_id=model_spec_ver_id,
            dataset_version_id=ds_ver_id,
            requested_via="mcp",
            trace_id="trace-up063-dispatch",
        )

    assert res["run"]["run_id"] == str(run_id)
    assert res["job"]["job_id"] == str(job_id)
    assert res["job"]["status"] == "queued"
    assert res["job"]["stage"] == "validating"


@pytest.mark.anyio
async def test_get_run_status_polling(client_with_org):
    """UP-063: Polling run status from gateway returns current run state and decision status."""
    run_id = uuid4()
    project_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/runs/{run_id}"
        assert request.headers.get("x-organization-id") == str(client_with_org.organization_id)
        return httpx.Response(
            200,
            json={
                "schema_version": "1.0",
                "run_id": str(run_id),
                "organization_id": str(client_with_org.organization_id),
                "project_id": str(project_id),
                "status": "running",
                "decision_status": "not_evaluated",
                "requested_via": "mcp",
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080") as http_c:
        client_with_org._http_client = http_c
        status = await client_with_org.get_run_status(run_id)

    assert status["run_id"] == str(run_id)
    assert status["status"] == "running"
    assert status["decision_status"] == "not_evaluated"


@pytest.mark.anyio
async def test_get_job_status_polling(client_with_org):
    """UP-063: Polling job status from gateway returns stage and progress percent."""
    job_id = uuid4()
    run_id = uuid4()
    project_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/jobs/{job_id}"
        assert request.headers.get("x-organization-id") == str(client_with_org.organization_id)
        return httpx.Response(
            200,
            json={
                "schema_version": "1.0",
                "job_id": str(job_id),
                "run_id": str(run_id),
                "organization_id": str(client_with_org.organization_id),
                "project_id": str(project_id),
                "status": "running",
                "stage": "sampling",
                "progress_percent": 65,
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080") as http_c:
        client_with_org._http_client = http_c
        job_status = await client_with_org.get_job_status(job_id)

    assert job_status["job_id"] == str(job_id)
    assert job_status["stage"] == "sampling"
    assert job_status["progress_percent"] == 65


@pytest.mark.anyio
async def test_submit_fit_mmm_job_tool_routes_to_platform(tmp_path):
    """UP-063: submit_fit_mmm_job MCP tool dispatches run to gateway and returns immediate job ticket."""
    import pandas as pd

    from marketing_mcp.app import Application
    from marketing_mcp.mcp.server import create_server
    from marketing_mcp.schemas.models import FitMMMInput
    from marketing_mcp.security.principal import Principal

    org_id = uuid4()
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "meta.db",
        gateway_url="http://127.0.0.1:8080",
        organization_id=str(org_id),
        principal_id=str(uuid4()),
        platform_client_enabled=True,
    )
    app = Application(settings)

    # Register valid test dataset with >= 52 periods for MMM modeling
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=60, freq="W-MON"),
        "sales": [1000.0 + i * 10 for i in range(60)],
        "tv": [200.0 + i * 5 for i in range(60)],
    })
    csv_file = tmp_path / "data.csv"
    df.to_csv(csv_file, index=False)
    reg = app.datasets.register_file(csv_file)

    gateway_run_id = uuid4()
    gateway_job_id = uuid4()
    gateway_proj_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/runs":
            return httpx.Response(
                201,
                json={
                    "run": {
                        "schema_version": "1.0",
                        "run_id": str(gateway_run_id),
                        "organization_id": str(org_id),
                        "project_id": str(gateway_proj_id),
                        "model_spec_version_id": str(uuid4()),
                        "dataset_version_id": str(uuid4()),
                        "status": "queued",
                        "decision_status": "not_evaluated",
                        "requested_via": "mcp",
                    },
                    "job": {
                        "schema_version": "1.0",
                        "job_id": str(gateway_job_id),
                        "run_id": str(gateway_run_id),
                        "organization_id": str(org_id),
                        "project_id": str(gateway_proj_id),
                        "status": "queued",
                        "stage": "validating",
                        "progress_percent": 0,
                    },
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http_c = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080")
    app.platform_client._http_client = http_c

    class DummyContext:
        principal = Principal(
            subject="test-user",
            auth_type="api_key",
            scopes=frozenset(["*"]),
            tenant_id=str(org_id),
        )

    server = create_server(app, context_provider=lambda: DummyContext())

    fit_input = FitMMMInput(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="sales",
        channel_columns=["tv"],
    )

    res = await server.call_tool("submit_fit_mmm_job", {"config": fit_input.model_dump()})
    assert res is not None
    import json
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    data = json.loads(getattr(item, "text", "{}"))
    summary = data.get("summary", data)
    assert summary["job_id"] == str(gateway_job_id)
    assert summary["run_id"] == str(gateway_run_id)
    assert summary["status"] == "queued"
    assert summary["sse_topic_uri"] == f"/api/v1/projects/{gateway_proj_id}/events"
    assert summary["poll_url"] == f"/api/v1/runs/{gateway_run_id}"

    await http_c.aclose()


@pytest.mark.anyio
async def test_get_job_status_tool_routes_to_platform(tmp_path):
    """UP-063: get_job_status MCP tool queries gateway when job is unknown locally."""
    from marketing_mcp.app import Application
    from marketing_mcp.mcp.server import create_server
    from marketing_mcp.security.principal import Principal

    org_id = uuid4()
    remote_job_id = uuid4()
    remote_run_id = uuid4()
    remote_proj_id = uuid4()

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "meta.db",
        gateway_url="http://127.0.0.1:8080",
        organization_id=str(org_id),
        principal_id=str(uuid4()),
        platform_client_enabled=True,
    )
    app = Application(settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/v1/jobs/{remote_job_id}":
            return httpx.Response(
                200,
                json={
                    "schema_version": "1.0",
                    "job_id": str(remote_job_id),
                    "run_id": str(remote_run_id),
                    "organization_id": str(org_id),
                    "project_id": str(remote_proj_id),
                    "status": "running",
                    "stage": "sampling",
                    "progress_percent": 75,
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http_c = httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080")
    app.platform_client._http_client = http_c

    class DummyContext:
        principal = Principal(
            subject="test-user",
            auth_type="api_key",
            scopes=frozenset(["*"]),
            tenant_id=str(org_id),
        )

    server = create_server(app, context_provider=lambda: DummyContext())

    import json
    res = await server.call_tool("get_job_status", {"job_id": str(remote_job_id)})
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    data = json.loads(getattr(item, "text", "{}"))
    summary = data.get("summary", data)
    assert summary["job_id"] == str(remote_job_id)
    assert summary["stage"] == "sampling"
    assert summary["progress_percent"] == 75

    await http_c.aclose()

