"""Integration tests for UP-062: Route dataset MCP tools to platform API with fast CSV preflight."""

from __future__ import annotations

import hashlib
from uuid import uuid4

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
    )
    return PlatformClient(settings)


def _make_csv(rows: int = 20, negative_spend: bool = False) -> bytes:
    lines = ["date,sales,tv,radio"]
    for i in range(rows):
        tv = -10.0 if (negative_spend and i == 5) else 20.0
        lines.append(f"2023-01-{i+1:02d},{100.0 + i},{tv},{5.0 + i}")
    return "\n".join(lines).encode()


@pytest.mark.anyio
async def test_preflight_blocks_negative_spend_before_gateway(client_with_org):
    """UP-062: Preflight must catch negative spend and report is_valid_for_modeling=False."""
    bad_csv = _make_csv(rows=20, negative_spend=True)
    result = await client_with_org.route_dataset_preflight(
        csv_bytes=bad_csv,
        date_col="date",
        target_col="sales",
        channel_cols=["tv", "radio"],
    )
    assert result["is_valid_for_modeling"] is False
    assert any("negative spend" in e for e in result["validation_errors"])


@pytest.mark.anyio
async def test_preflight_passes_valid_csv(client_with_org):
    """UP-062: Valid 20-row CSV with all columns present must pass preflight."""
    good_csv = _make_csv(rows=20)
    result = await client_with_org.route_dataset_preflight(
        csv_bytes=good_csv,
        date_col="date",
        target_col="sales",
        channel_cols=["tv", "radio"],
    )
    assert result["is_valid_for_modeling"] is True
    assert result["validation_errors"] == []
    assert result["row_count"] == 20


@pytest.mark.anyio
async def test_preflight_injects_trace_id(client_with_org):
    """UP-062: Preflight result must carry the provided trace_id."""
    good_csv = _make_csv(rows=14)
    result = await client_with_org.route_dataset_preflight(
        csv_bytes=good_csv,
        trace_id="trace-up062-test",
    )
    assert result["trace_id"] == "trace-up062-test"


@pytest.mark.anyio
async def test_preflight_auto_generates_trace_id(client_with_org):
    """UP-062: Preflight must generate a trace_id when none is provided."""
    good_csv = _make_csv(rows=14)
    result = await client_with_org.route_dataset_preflight(csv_bytes=good_csv)
    assert "trace_id" in result
    assert result["trace_id"].startswith("trace-")


@pytest.mark.anyio
async def test_preflight_blocks_too_small_dataset(client_with_org):
    """UP-062: Dataset with fewer than 14 rows is blocked at preflight layer."""
    tiny_csv = _make_csv(rows=5)
    result = await client_with_org.route_dataset_preflight(
        csv_bytes=tiny_csv,
        date_col="date",
        target_col="sales",
        channel_cols=["tv", "radio"],
    )
    assert result["is_valid_for_modeling"] is False
    assert any("14 rows" in e for e in result["validation_errors"])


@pytest.mark.anyio
async def test_register_dataset_via_gateway_sends_tenant_scoped_payload(client_with_org):
    """UP-062: register_dataset_via_gateway must pass tenant headers and finalize payload."""
    import httpx

    project_id = uuid4()
    dataset_id = uuid4()
    org_id = client_with_org.organization_id

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update({
            "path": request.url.path,
            "org_id": request.headers.get("x-organization-id"),
            "trace_id": request.headers.get("x-trace-id"),
            "body": _json.loads(request.content),
        })
        if request.url.path == "/api/v1/datasets/finalize":
            return httpx.Response(201, json={
                "dataset_id": str(dataset_id),
                "dataset_version_id": str(uuid4()),
                "organization_id": str(uuid4()),
                "name": "test-dataset",
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080") as http_c:
        client_with_org._http_client = http_c
        csv_bytes = _make_csv(rows=20)
        sha256 = hashlib.sha256(csv_bytes).hexdigest()

        resp = await client_with_org.register_dataset_via_gateway(
            project_id=project_id,
            dataset_id=dataset_id,
            name="test-dataset",
            sha256=sha256,
            size_bytes=len(csv_bytes),
            row_count=20,
            column_count=4,
            columns=[],
            storage_uri=f"s3://pymc-artifacts/tenants/{org_id}/datasets/{dataset_id}/data.csv",
            trace_id="trace-up062-gateway",
        )

    assert captured["path"] == "/api/v1/datasets/finalize"
    assert captured["org_id"] == str(org_id)
    assert captured["trace_id"] == "trace-up062-gateway"
    assert captured["body"]["sha256"] == sha256
    assert captured["body"]["row_count"] == 20
    assert resp["name"] == "test-dataset"
