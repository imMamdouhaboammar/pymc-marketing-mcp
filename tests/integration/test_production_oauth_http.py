"""Real asymmetric JWKS verification through an HTTP MCP session."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx2
import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from marketing_mcp.app import Application
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.persistence import SQLitePersistenceBackend


async def _start_server(app) -> tuple[uvicorn.Server, asyncio.Task, int]:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, port


def test_production_oauth_asymmetric_jwks_mcp_session(tmp_path: Path) -> None:
    async def run() -> None:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
        jwk.update({"kid": "key-1", "use": "sig", "alg": "RS256"})
        jwks_app = Starlette(
            routes=[Route("/jwks", lambda _request: JSONResponse({"keys": [jwk]}))]
        )
        issuer_server, issuer_task, issuer_port = await _start_server(jwks_app)
        issuer = f"http://127.0.0.1:{issuer_port}"
        settings = Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
            security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
            oauth_issuer=issuer,
            oauth_audience="pymc-marketing-mcp",
            oauth_jwks_url=f"{issuer}/jwks",
            oauth_required_scopes=["marketing:read"],
            oauth_algorithms=["RS256"],
            oauth_tenant_claim="org_id",
        )
        persistence = SQLitePersistenceBackend(tmp_path / "test-persistence.db")
        application = Application(settings, persistence=persistence)
        mcp_app = create_http_app(application=application, settings=settings)
        mcp_server, mcp_task, mcp_port = await _start_server(mcp_app)
        token = jwt.encode(
            {
                "sub": "analyst",
                "org_id": "tenant-a",
                "scope": "marketing:read",
                "iss": issuer,
                "aud": "pymc-marketing-mcp",
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )
        try:
            url = f"http://127.0.0.1:{mcp_port}/mcp"
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client,
                streamable_http_client(url, http_client=client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert tools.tools

            async with httpx2.AsyncClient() as invalid_client:
                invalid = await invalid_client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}x"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
            assert invalid.status_code == 401
            assert "signature" not in invalid.text.lower()
        finally:
            mcp_server.should_exit = True
            issuer_server.should_exit = True
            await mcp_task
            await issuer_task
            persistence.close()

    asyncio.run(run())
