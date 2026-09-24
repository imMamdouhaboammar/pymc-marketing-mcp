"""Integration tests for Authenticated Platform Client and Sub-Millisecond Handshake (UP-061)."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest

from marketing_mcp.adapters.platform_client import PlatformClient
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError


@pytest.fixture
def org_id() -> UUID:
    return uuid4()


@pytest.fixture
def principal_id() -> UUID:
    return uuid4()


@pytest.fixture
def platform_client(org_id, principal_id) -> PlatformClient:
    settings = Settings(
        gateway_url="http://127.0.0.1:8080",
        organization_id=str(org_id),
        principal_id=str(principal_id),
        principal_role="analyst",
    )
    return PlatformClient(settings)


def test_precached_tools_and_resources_sub_millisecond_handshake(platform_client):
    """UP-061 Acceptance: Pre-cached tools/list and resources/list must respond in < 1ms."""
    # Warmup
    _ = platform_client.get_cached_tools_list()

    t0 = time.perf_counter()
    tools = platform_client.get_cached_tools_list()
    t_tools = time.perf_counter() - t0

    t1 = time.perf_counter()
    resources = platform_client.get_cached_resources_list()
    t_resources = time.perf_counter() - t1

    assert t_tools < 0.001, f"tools/list took {t_tools*1000:.3f}ms, expected < 1.0ms"
    assert t_resources < 0.001, f"resources/list took {t_resources*1000:.3f}ms, expected < 1.0ms"

    assert len(tools) == 50, f"Expected 50 tools, got {len(tools)}"
    assert len(resources) == 16, f"Expected 16 resources, got {len(resources)}"


def test_header_propagation_and_trace_id(platform_client, org_id, principal_id):
    """UP-061 Acceptance: Client propagates organization, principal, role, and trace IDs."""
    headers = platform_client.build_headers(trace_id="trace-test-xyz-999")

    assert headers["x-organization-id"] == str(org_id)
    assert headers["x-principal-id"] == str(principal_id)
    assert headers["x-principal-role"] == "analyst"
    assert headers["x-trace-id"] == "trace-test-xyz-999"


def test_client_requires_organization_id_for_platform_calls():
    """Tenant isolation invariant: Client must refuse calls without organization_id."""
    settings = Settings(
        gateway_url="http://127.0.0.1:8080",
        organization_id=None,
    )
    client = PlatformClient(settings)

    with pytest.raises(DomainError) as exc_info:
        client.build_headers()
    assert exc_info.value.code == "AUTH_REQUIRED"


@pytest.mark.anyio
async def test_mock_gateway_roundtrip_with_headers(platform_client, org_id):
    """Verify async roundtrip with mock HTTP transport validating tenant headers."""
    import httpx

    captured_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        if request.url.path == "/health/ready":
            return httpx.Response(200, json={"status": "ready", "service": "pymc-gateway", "version": "0.1.0"})
        if request.url.path == "/api/v1/projects":
            if request.headers.get("x-organization-id") != str(org_id):
                return httpx.Response(401, json={"error": {"code": "AUTH_UNAUTHORIZED"}})
            return httpx.Response(200, json=[{"project_id": str(uuid4()), "name": "Default Project"}])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8080") as http_client:
        platform_client._http_client = http_client

        health = await platform_client.check_health()
        assert health["status"] == "ready"

        projects = await platform_client.list_projects(trace_id="trace-abc-123")
        assert len(projects) == 1
        assert projects[0]["name"] == "Default Project"
        assert captured_headers["x-organization-id"] == str(org_id)
        assert captured_headers["x-trace-id"] == "trace-abc-123"
