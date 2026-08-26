"""End-to-end integration tests for HTTP principal propagation, scope enforcement, and tenant isolation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager, create_jwt_token
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import RequestScopedContextProvider


@pytest.fixture
def http_app_setup(tmp_path: Path):
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    jwt_secret = "test-jwt-secret-key-1234567890123456"
    auth_mgr = AuthManager(
        jwt_secret=jwt_secret,
        enabled=True,
    )
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)
    return asgi_app, jwt_secret, app_instance


def test_http_read_scope_cannot_call_decision_tool(http_app_setup):
    """Test that an HTTP token with only marketing:read scope cannot invoke simulate_budget."""
    asgi_app, jwt_secret, _ = http_app_setup

    async def _run():
        read_token = create_jwt_token(
            secret=jwt_secret,
            client_id="read-only-analyst",
            scopes=["marketing:read"],
        )

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]

        try:
            url = f"http://127.0.0.1:{port}/mcp"

            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {read_token}"}) as http_client,
                streamable_http_client(url, http_client=http_client) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()

                result = await session.call_tool(
                    "simulate_budget",
                    arguments={
                        "config": {
                            "model_id": "model_1",
                            "changes": {"tv": {"type": "absolute", "value": 1000.0}},
                        }
                    },
                )
                assert result.content and len(result.content) > 0
                payload = json.loads(result.content[0].text)
                assert "error" in payload
                assert payload["error"]["code"] == "AUTH_FORBIDDEN"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())


def test_http_token_with_decision_scope_is_allowed(http_app_setup):
    """Test that an HTTP token with marketing:decide scope passes scope check."""
    asgi_app, jwt_secret, _ = http_app_setup

    async def _run():
        decide_token = create_jwt_token(
            secret=jwt_secret,
            client_id="decision-maker",
            scopes=["marketing:decide", "marketing:read"],
        )

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]

        try:
            url = f"http://127.0.0.1:{port}/mcp"

            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {decide_token}"}) as http_client,
                streamable_http_client(url, http_client=http_client) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()

                result = await session.call_tool(
                    "simulate_budget",
                    arguments={
                        "config": {
                            "model_id": "nonexistent_model",
                            "changes": {"tv": {"type": "absolute", "value": 1000.0}},
                        }
                    },
                )
                assert result.content and len(result.content) > 0
                payload = json.loads(result.content[0].text)
                # Should pass auth scope check, and fail on domain lookup (model not found), not AUTH_FORBIDDEN
                assert "error" in payload
                assert payload["error"]["code"] == "MODEL_NOT_FOUND"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())


def test_http_cross_tenant_resource_denial(http_app_setup):
    """Test that a tenant A token cannot read or mutate tenant B resources."""
    asgi_app, jwt_secret, app_instance = http_app_setup

    # Seed metadata for tenant_b
    app_instance.metadata.put_model(
        {
            "model_id": "mmm_tenant_b_secret",
            "tenant_id": "tenant_b",
            "owner": "user_tenant_b",
            "status": "completed",
            "diagnostics": {"r_hat_max": 1.01},
        }
    )

    async def _run():
        tenant_a_token = create_jwt_token(
            secret=jwt_secret,
            client_id="user_tenant_a",
            tenant_id="tenant_a",
            scopes=["marketing:read", "marketing:model"],
        )

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]

        try:
            url = f"http://127.0.0.1:{port}/mcp"

            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {tenant_a_token}"}) as http_client,
                streamable_http_client(url, http_client=http_client) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()

                # 1. Calling tool on tenant B model is denied
                res = await session.call_tool(
                    "diagnose_mmm",
                    arguments={"model_id": "mmm_tenant_b_secret"},
                )
                payload = json.loads(res.content[0].text)
                assert "error" in payload
                assert payload["error"]["code"] == "AUTH_FORBIDDEN"

                # 2. Reading resource of tenant B is denied
                res_content = await session.read_resource("marketing://models/mmm_tenant_b_secret")
                res_data = json.loads(res_content.contents[0].text)
                assert "error" in res_data
                assert res_data["error"]["code"] == "AUTH_FORBIDDEN"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())


def test_request_scoped_provider_fails_closed_without_context():
    """Verify that RequestScopedContextProvider raises AUTH_REQUIRED when no context is active."""
    provider = RequestScopedContextProvider()
    with pytest.raises(Exception) as exc_info:
        provider()
    assert exc_info.value.code == "AUTH_REQUIRED"
