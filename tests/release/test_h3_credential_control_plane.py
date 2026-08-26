"""Gate H3: Credential Control Plane and Verifier-Only Authority.

Gate H3 contract:
1. Dashboard and clients consume a backend credential authority; browser key generation is removed.
2. Raw secrets are shown exactly once at creation and never persisted at rest in plaintext.
3. Credentials stored in DB contain non-reversible salted verifiers only.
4. Public API endpoints and DTOs never leak secret or verifier.
5. Key revocation takes effect immediately in the MCP authentication layer.
6. Scopes and tenant identity propagate from the API key to tool execution.
7. Audit trail records credential lifecycle events without secret exposure.
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
from marketing_mcp.credentials.service import CredentialService
from marketing_mcp.credentials.sqlite_repository import SQLiteCredentialRepository


@pytest.fixture
def h3_app_setup(tmp_path: Path):
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    jwt_secret = "h3-gate-test-jwt-secret-key-1234567890123456"
    auth_mgr = AuthManager(jwt_secret=jwt_secret, enabled=True, credential_service=app_instance.credentials)
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)
    return asgi_app, jwt_secret, app_instance


def test_h3_verifier_only_storage_and_one_time_issuance(tmp_path: Path):
    """Verify backend stores salted verifier, not raw secret, and provides safe public view."""
    repo = SQLiteCredentialRepository(tmp_path / "creds.db")
    service = CredentialService(repo)

    issued = service.issue(
        tenant_id="tenant_prod",
        owner_subject="user_admin",
        name="Production Key",
        scopes=["marketing:read", "marketing:model"],
    )

    # Secret is returned once
    assert issued.secret.startswith("mcp_live_")

    # In DB, record contains verifier and salt, never raw secret
    db_rec = repo.get_by_id(issued.record.credential_id)
    assert db_rec is not None
    assert db_rec.verifier != issued.secret
    assert db_rec.salt
    assert issued.secret not in db_rec.verifier

    # Public dict is safe
    public_dict = issued.record.to_public_dict()
    assert "secret" not in public_dict
    assert "verifier" not in public_dict
    assert "salt" not in public_dict
    assert public_dict["scopes"] == ["marketing:model", "marketing:read"]


def test_h3_immediate_mcp_revocation_and_scope_propagation(h3_app_setup):
    """Verify end-to-end issuance, MCP scope enforcement, immediate revocation over HTTP."""
    asgi_app, jwt_secret, _ = h3_app_setup

    async def _run():
        admin_jwt = create_jwt_token(
            secret=jwt_secret,
            client_id="admin_user",
            tenant_id="tenant_x",
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
            # 1. Issue key with marketing:read only
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {admin_jwt}"}) as http_client:
                res = await http_client.post(
                    f"{base_url}/control/credentials",
                    json={"name": "Read Only Key", "scopes": ["marketing:read"]},
                )
                assert res.status_code == 201
                body = res.json()
                secret = body["secret"]
                cred_id = body["credential"]["credential_id"]

            # 2. Use key with MCP client
            mcp_url = f"{base_url}/mcp"
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {secret}"}) as mcp_client,
                streamable_http_client(mcp_url, http_client=mcp_client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # Allowed read tool
                r = await session.call_tool("get_model_status", arguments={"model_id": "nonexistent"})
                payload = json.loads(r.content[0].text)
                assert payload["error"]["code"] == "MODEL_NOT_FOUND"

                # Denied decision tool
                r = await session.call_tool(
                    "simulate_budget",
                    arguments={"config": {"model_id": "m1", "changes": {"tv": {"type": "absolute", "value": 10.0}}}},
                )
                payload = json.loads(r.content[0].text)
                assert payload["error"]["code"] == "AUTH_FORBIDDEN"

            # 3. Revoke key
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {admin_jwt}"}) as http_client:
                del_res = await http_client.delete(f"{base_url}/control/credentials/{cred_id}")
                assert del_res.status_code == 200

            # 4. Immediate rejection on subsequent MCP request
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {secret}"}) as mcp_client:
                r = await mcp_client.post(
                    f"{base_url}/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code == 401
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
