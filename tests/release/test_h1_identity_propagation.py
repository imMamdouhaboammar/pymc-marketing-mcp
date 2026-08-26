"""Gate H1: Identity Propagation and Authorization Boundary.

Gate H1 contract:
1. HTTP authenticated principal propagates into tool and resource execution.
2. Remote HTTP requests NEVER fall back to trusted local stdio principal.
3. Unauthenticated or misconfigured context fails closed with AUTH_REQUIRED.
4. Scope enforcement occurs at tool execution time for the active request principal.
5. Local stdio transport remains fully supported with default admin scope.
"""

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
from marketing_mcp.errors import DomainError
from marketing_mcp.mcp.context import (
    ExecutionContext,
    RequestScopedContextProvider,
    reset_current_execution_context,
    set_current_execution_context,
    stdio_context_provider,
)
from marketing_mcp.security.policy import all_scopes
from marketing_mcp.security.principal import Principal


def test_h1_stdio_provider_has_all_scopes():
    """Verify local stdio provider creates a trusted principal with all scopes."""
    ctx = stdio_context_provider()
    assert ctx.transport == "stdio"
    assert ctx.principal is not None
    assert ctx.principal.auth_type == "stdio"
    assert ctx.principal.subject == "local-stdio"
    assert ctx.principal.scopes == all_scopes()


def test_h1_request_scoped_provider_fails_closed_when_empty():
    """Verify RequestScopedContextProvider raises AUTH_REQUIRED when context is absent."""
    provider = RequestScopedContextProvider()
    with pytest.raises(DomainError) as exc_info:
        provider()
    assert exc_info.value.code == "AUTH_REQUIRED"


def test_h1_request_scoped_provider_returns_active_context():
    """Verify RequestScopedContextProvider returns the active bound ExecutionContext."""
    principal = Principal(
        subject="test-user",
        auth_type="api_key",
        scopes=frozenset(["marketing:read"]),
        tenant_id="tenant_1",
    )
    exec_ctx = ExecutionContext(principal=principal, request_id="req-123", transport="http")
    token = set_current_execution_context(exec_ctx)
    try:
        provider = RequestScopedContextProvider()
        resolved = provider()
        assert resolved.principal == principal
        assert resolved.request_id == "req-123"
        assert resolved.transport == "http"
    finally:
        reset_current_execution_context(token)


def test_h1_http_scope_isolation_via_mcp_client(tmp_path: Path):
    """Verify through full HTTP transport that insufficient scopes are rejected at tool execution."""
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    jwt_secret = "h1-gate-test-secret-key-1234567890123456"
    auth_mgr = AuthManager(jwt_secret=jwt_secret, enabled=True)
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)

    async def _run():
        read_token = create_jwt_token(
            secret=jwt_secret,
            client_id="read-only-user",
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
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {read_token}"}) as client,
                streamable_http_client(url, http_client=client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # 1. Calling decision tool without marketing:decide scope returns AUTH_FORBIDDEN
                res = await session.call_tool(
                    "simulate_budget",
                    arguments={
                        "config": {
                            "model_id": "model_1",
                            "changes": {"tv": {"type": "absolute", "value": 500.0}},
                        }
                    },
                )
                payload = json.loads(res.content[0].text)
                assert "error" in payload
                assert payload["error"]["code"] == "AUTH_FORBIDDEN"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
