"""Gate H2: Object and Resource Tenant Isolation.

Gate H2 contract:
1. Persisted datasets, models, lineage, and resources contain owner and tenant_id.
2. Direct MCP tool invocation across tenant boundaries is denied (AUTH_FORBIDDEN).
3. Direct MCP resource reads across tenant boundaries are denied (AUTH_FORBIDDEN).
4. Local stdio caller retains access to all records.
5. Administrative users with marketing:admin or wildcard scope can administer across objects.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager, create_jwt_token
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.security.principal import Principal


def test_h2_dataset_and_model_ownership_metadata(tmp_path: Path):
    """Verify owner and tenant_id are stored on dataset registration and model records."""
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    csv_path = tmp_path / "sample.csv"
    generate_synthetic_mmm(n=40).to_csv(csv_path, index=False)

    principal_a = Principal(
        subject="user_alice",
        auth_type="oauth",
        tenant_id="tenant_alpha",
        scopes=frozenset(["marketing:model", "marketing:read"]),
    )

    reg = app.datasets.register_file(csv_path, principal=principal_a)
    assert reg.owner == "user_alice"
    assert reg.tenant_id == "tenant_alpha"

    # Query from metadata DB
    rec = app.metadata.get_dataset(reg.dataset_id)
    assert rec["owner"] == "user_alice"
    assert rec["tenant_id"] == "tenant_alpha"


def test_h2_cross_tenant_denial_for_tools_and_resources(tmp_path: Path):
    """Verify cross-tenant tool execution and resource read are blocked over HTTP."""
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    # Seed model for Tenant Alpha
    app_instance.metadata.put_model(
        {
            "model_id": "mmm_alpha_model",
            "tenant_id": "tenant_alpha",
            "owner": "user_alice",
            "status": "completed",
            "diagnostics": {"r_hat_max": 1.01},
        }
    )

    jwt_secret = "h2-gate-secret-key-1234567890123456"
    auth_mgr = AuthManager(jwt_secret=jwt_secret, enabled=True)
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)

    async def _run():
        # Tenant Beta principal
        tenant_beta_token = create_jwt_token(
            secret=jwt_secret,
            client_id="user_bob",
            tenant_id="tenant_beta",
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
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {tenant_beta_token}"}) as client,
                streamable_http_client(url, http_client=client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # 1. Tenant Beta cannot get status of Tenant Alpha's model
                res = await session.call_tool("get_model_status", arguments={"model_id": "mmm_alpha_model"})
                payload = json.loads(res.content[0].text)
                assert "error" in payload
                assert payload["error"]["code"] == "AUTH_FORBIDDEN"

                # 2. Tenant Beta cannot read Tenant Alpha's model resource
                res_content = await session.read_resource("marketing://models/mmm_alpha_model")
                res_data = json.loads(res_content.contents[0].text)
                assert "error" in res_data
                assert res_data["error"]["code"] == "AUTH_FORBIDDEN"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
