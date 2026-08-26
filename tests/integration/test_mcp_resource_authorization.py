"""Integration test suite for MCP resource authorization across scopes and tenants."""

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
def resource_app_setup(tmp_path: Path):
    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    # Seed Tenant A resources
    app_instance.metadata.put_dataset(
        {
            "dataset_id": "ds_tenant_a",
            "tenant_id": "tenant_a",
            "owner": "user_a",
            "path": str(tmp_path / "data.csv"),
            "fingerprint": "fp_a",
            "format": "csv",
            "rows": 100,
            "created_at": "2026-08-26T00:00:00Z",
        }
    )
    app_instance.metadata.put_model(
        {
            "model_id": "mmm_tenant_a",
            "parent_model_id": None,
            "lineage_stage": "initial_fit",
            "dataset_id": "ds_tenant_a",
            "dataset_fingerprint": "fp_a",
            "semantic_config_hash": "hash_a",
            "status": "completed",
            "model_type": "MMM",
            "config": {},
            "package_provenance": {},
            "created_at": "2026-08-26T00:00:00Z",
            "updated_at": "2026-08-26T00:00:00Z",
            "diagnostics": {"r_hat_max": 1.01, "minimum_ess_bulk": 850.0},
            "tenant_id": "tenant_a",
            "owner": "user_a",
        }
    )
    app_instance.metadata.put_clv_model(
        {
            "model_id": "clv_tenant_a",
            "model_type": "bg_nbd",
            "dataset_id": "ds_tenant_a",
            "status": "completed",
            "config": {},
            "package_provenance": {},
            "created_at": "2026-08-26T00:00:00Z",
            "updated_at": "2026-08-26T00:00:00Z",
            "tenant_id": "tenant_a",
            "owner": "user_a",
        }
    )

    jwt_secret = "resource-auth-secret-key-1234567890123456"
    auth_mgr = AuthManager(jwt_secret=jwt_secret, enabled=True)
    asgi_app = create_http_app(application=app_instance, auth_manager=auth_mgr)
    return asgi_app, jwt_secret, app_instance


def test_resource_access_matrix(resource_app_setup):
    """Verify resource read access succeeds for same tenant and fails for cross-tenant."""
    asgi_app, jwt_secret, _ = resource_app_setup

    async def _run():
        token_tenant_a = create_jwt_token(
            secret=jwt_secret,
            client_id="user_a",
            tenant_id="tenant_a",
            scopes=["marketing:read"],
        )
        token_tenant_b = create_jwt_token(
            secret=jwt_secret,
            client_id="user_b",
            tenant_id="tenant_b",
            scopes=["marketing:read"],
        )
        token_no_read_scope = create_jwt_token(
            secret=jwt_secret,
            client_id="user_a",
            tenant_id="tenant_a",
            scopes=["marketing:model"],
        )

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/mcp"

        try:
            # 1. Tenant A reads own dataset, model, diagnostics, lineage, CLV
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {token_tenant_a}"}) as client_a,
                streamable_http_client(url, http_client=client_a) as (read_a, write_a),
                ClientSession(read_a, write_a) as session_a,
            ):
                await session_a.initialize()

                res = await session_a.read_resource("marketing://datasets/ds_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["dataset_id"] == "ds_tenant_a"

                res = await session_a.read_resource("marketing://models/mmm_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["model_id"] == "mmm_tenant_a"

                res = await session_a.read_resource("marketing://models/mmm_tenant_a/diagnostics")
                data = json.loads(res.contents[0].text)
                assert data["r_hat_max"] == 1.01

                res = await session_a.read_resource("marketing://models/mmm_tenant_a/lineage")
                data = json.loads(res.contents[0].text)
                assert data["model_id"] == "mmm_tenant_a"
                assert data["dataset_fingerprint"] == "fp_a"

                res = await session_a.read_resource("marketing://clv/clv_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["model_id"] == "clv_tenant_a"

            # 2. Tenant B (different tenant) is denied access
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {token_tenant_b}"}) as client_b,
                streamable_http_client(url, http_client=client_b) as (read_b, write_b),
                ClientSession(read_b, write_b) as session_b,
            ):
                await session_b.initialize()

                res = await session_b.read_resource("marketing://datasets/ds_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["error"]["code"] == "AUTH_FORBIDDEN"

                res = await session_b.read_resource("marketing://models/mmm_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["error"]["code"] == "AUTH_FORBIDDEN"

                res = await session_b.read_resource("marketing://clv/clv_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["error"]["code"] == "AUTH_FORBIDDEN"

            # 3. Caller lacking marketing:read scope is denied access
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {token_no_read_scope}"}) as client_c,
                streamable_http_client(url, http_client=client_c) as (read_c, write_c),
                ClientSession(read_c, write_c) as session_c,
            ):
                await session_c.initialize()

                res = await session_c.read_resource("marketing://models/mmm_tenant_a")
                data = json.loads(res.contents[0].text)
                assert data["error"]["code"] == "AUTH_FORBIDDEN"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
