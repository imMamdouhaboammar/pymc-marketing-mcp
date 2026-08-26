"""Integration tests for the Credential Control Plane API and immediate MCP auth enforcement."""

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


@pytest.fixture
def control_api_setup(tmp_path: Path):
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    jwt_secret = "control-plane-jwt-secret-key-1234567890123456"
    auth_mgr = AuthManager(jwt_secret=jwt_secret, enabled=True, credential_service=app_instance.credentials)
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)
    return asgi_app, jwt_secret, app_instance


def test_credential_control_lifecycle_and_mcp_auth(control_api_setup):
    """Verify backend issuance, listing, immediate MCP authentication, revocation, and rejection."""
    asgi_app, jwt_secret, _ = control_api_setup

    async def _run():
        admin_jwt = create_jwt_token(
            secret=jwt_secret,
            client_id="user_alice",
            tenant_id="tenant_alpha",
            scopes=["*"],
        )

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"

        try:
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {admin_jwt}"}) as http_client:
                # 1. List initially empty
                r = await http_client.get(f"{base_url}/control/credentials")
                assert r.status_code == 200
                assert r.json()["credentials"] == []

                # 2. Issue new API key with marketing:read scope
                create_res = await http_client.post(
                    f"{base_url}/control/credentials",
                    json={"name": "Alice Read Key", "scopes": ["marketing:read"]},
                )
                assert create_res.status_code == 201
                body = create_res.json()
                assert "secret" in body
                issued_secret = body["secret"]
                assert issued_secret.startswith("mcp_live_")
                cred_id = body["credential"]["credential_id"]
                assert body["credential"]["name"] == "Alice Read Key"

                # 3. List contains newly created key (verifier and secret NOT in list)
                list_res = await http_client.get(f"{base_url}/control/credentials")
                assert list_res.status_code == 200
                items = list_res.json()["credentials"]
                assert len(items) == 1
                assert items[0]["credential_id"] == cred_id
                assert "secret" not in items[0]
                assert "verifier" not in items[0]

            # 4. Use issued API key directly with MCP Client Session
            mcp_url = f"{base_url}/mcp"
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {issued_secret}"}) as mcp_http_client,
                streamable_http_client(mcp_url, http_client=mcp_http_client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # Call tool with read scope allowed (expect domain error since model doesn't exist, not auth error)
                status_res = await session.call_tool("get_model_status", arguments={"model_id": "nonexistent"})
                status_payload = json.loads(status_res.content[0].text)
                assert "error" in status_payload
                assert status_payload["error"]["code"] == "MODEL_NOT_FOUND"

                # Call decision tool (fails with AUTH_FORBIDDEN because key only has marketing:read)
                decide_res = await session.call_tool(
                    "simulate_budget",
                    arguments={
                        "config": {
                            "model_id": "m1",
                            "changes": {"tv": {"type": "absolute", "value": 100.0}},
                        }
                    },
                )
                decide_payload = json.loads(decide_res.content[0].text)
                assert "error" in decide_payload
                assert decide_payload["error"]["code"] == "AUTH_FORBIDDEN"

            # 5. Revoke key via Control Plane API
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {admin_jwt}"}) as http_client:
                del_res = await http_client.delete(f"{base_url}/control/credentials/{cred_id}")
                assert del_res.status_code == 200
                assert del_res.json()["credential"]["status"] == "revoked"

            # 6. Using revoked key is rejected immediately by auth middleware (401 Unauthorized)
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {issued_secret}"}) as mcp_http_client:
                rejected_res = await mcp_http_client.post(
                    f"{base_url}/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert rejected_res.status_code == 401
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
