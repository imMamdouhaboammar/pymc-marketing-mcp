import asyncio
import json

import httpx2
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager, MCPAuthMiddleware, create_jwt_token, generate_api_key
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server


def test_auth_middleware_e2e(tmp_path):
    """End-to-end test of MCP Auth middleware with real HTTP requests and client sessions."""

    async def _run():
        app_instance = Application(
            Settings(
                data_dir=tmp_path / "data",
                artifact_dir=tmp_path / "artifacts",
                metadata_db=tmp_path / "metadata.db",
                ingest_dir=tmp_path,
            )
        )
        mcp_server = create_server(app_instance)
        asgi_app = mcp_server.streamable_http_app(host="127.0.0.1")

        valid_api_key = generate_api_key()
        jwt_secret = "test-jwt-secret-key-1234567890123456"
        auth_mgr = AuthManager(
            api_keys=[valid_api_key],
            jwt_secret=jwt_secret,
            enabled=True,
        )
        asgi_app.add_middleware(MCPAuthMiddleware, auth_manager=auth_mgr)

        async def health_check(_request):
            from starlette.responses import JSONResponse

            return JSONResponse({"status": "healthy"})

        asgi_app.add_route("/health", health_check, methods=["GET"])

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]

        try:
            base_url = f"http://127.0.0.1:{port}"

            async with httpx2.AsyncClient() as http_client:
                # 1. Health check is accessible without auth
                r = await http_client.get(f"{base_url}/health")
                assert r.status_code == 200
                assert r.json()["status"] == "healthy"

                # 2. Unauthenticated request to /mcp returns 401
                r = await http_client.post(
                    f"{base_url}/mcp",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code == 401
                assert "WWW-Authenticate" in r.headers
                assert r.json()["error"]["code"] == -32001

                # 3. Invalid key returns 401
                r = await http_client.post(
                    f"{base_url}/mcp",
                    headers={"Authorization": "Bearer invalid-key"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code == 401

                # 4. Valid API Key via X-API-Key header returns 200
                r = await http_client.post(
                    f"{base_url}/mcp",
                    headers={"X-API-Key": valid_api_key},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code in (200, 400)  # Accepted by auth middleware

                # 5. Valid JWT Bearer token returns 200
                jwt_token = create_jwt_token(secret=jwt_secret, client_id="chatgpt")
                r = await http_client.post(
                    f"{base_url}/mcp",
                    headers={"Authorization": f"Bearer {jwt_token}"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code in (200, 400)

                # 6. Valid key via Query Parameter ?token=
                r = await http_client.post(
                    f"{base_url}/mcp?token={valid_api_key}",
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
                )
                assert r.status_code in (200, 400)

            # 7. Full MCP Client Session with Authorization header
            mcp_url = f"{base_url}/mcp"
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {valid_api_key}"}) as client,
                streamable_http_client(mcp_url, http_client=client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) >= 15

                # Execute authenticated tool call
                res = await session.call_tool(
                    "recommend_next_measurement",
                    arguments={"model_id": "test_auth_model"},
                )
                err = json.loads(res.content[0].text)
                assert err["error"]["code"] == "MODEL_NOT_FOUND"

            # 8. Full MCP Client Session with JWT
            async with (
                httpx2.AsyncClient(headers={"Authorization": f"Bearer {jwt_token}"}) as client,
                streamable_http_client(mcp_url, http_client=client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) >= 15

            # 9. Full MCP Client Session with Query Parameter
            async with (
                streamable_http_client(f"{mcp_url}?token={valid_api_key}") as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) >= 15

        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
