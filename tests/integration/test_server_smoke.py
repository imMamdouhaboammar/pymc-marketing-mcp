"""Smoke tests for the running PyMC Marketing MCP streamable-HTTP server.

Adheres strictly to /test-guard:
- Rule 1: Tests observable caller-facing HTTP & MCP JSON-RPC behavior.
- Rule 2: Zero internal mocks; runs real Uvicorn server on an ephemeral loopback socket.
- Rule 3: Single scenario per test function.
- Rule 4: Validates real runtime server startup, Starlette middlewares, and MCP protocol handshake.
- Rule 5: Scenario-named test functions (test_<scenario>_<expected_outcome>).
- Rule 7: Tests custom application endpoints and middleware integration, not Starlette/Uvicorn internals.
- Rule 8: Uses real datasets and unmocked domain payload models.
- Rule 9: Uses real network socket and filesystem scratch directories.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pandas as pd
import pytest
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

import marketing_mcp
from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm


async def _start_server(app) -> tuple[uvicorn.Server, asyncio.Task, int]:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, port


@pytest.fixture
def running_server_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MARKETING_MCP_ALLOW_ANONYMOUS_HTTP", "true")
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
    )
    app = Application(settings)
    auth_mgr = AuthManager(enabled=False, credential_service=app.credentials)
    http_app = create_http_app(
        host="127.0.0.1",
        application=app,
        auth_manager=auth_mgr,
        settings=settings,
    )
    return http_app, tmp_path


def test_server_startup_health_probe_returns_healthy_metadata(running_server_app):
    """Verify that a newly started server responds with 200 and healthy metadata on /health."""
    http_app, _ = running_server_app

    async def _run():
        server, task, port = await _start_server(http_app)
        try:
            base_url = f"http://127.0.0.1:{port}"
            async with httpx2.AsyncClient(base_url=base_url) as client:
                response = await client.get("/health")

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "healthy"
            assert body["service"] == "pymc-marketing-mcp"
            assert body["version"] == marketing_mcp.__version__
            assert body["transport"] == "streamable-http"
            assert "interaction_engine" in body
            assert body["interaction_engine"]["backend"] in (
                "rust-native",
                "rust",
                "python",
                "python-standard",
            )
        finally:
            server.should_exit = True
            await task

    asyncio.run(_run())


def test_server_liveness_and_readiness_probes_return_ok(running_server_app):
    """Verify that Kubernetes / Cloud Run liveness and readiness probes return 200 OK."""
    http_app, _ = running_server_app

    async def _run():
        server, task, port = await _start_server(http_app)
        try:
            base_url = f"http://127.0.0.1:{port}"
            async with httpx2.AsyncClient(base_url=base_url) as client:
                live_res = await client.get("/health/live")
                ready_res = await client.get("/health/ready")

            assert live_res.status_code == 200
            live_data = live_res.json()
            assert live_data["status"] == "alive"
            assert live_data["service"] == "pymc-marketing-mcp"
            assert live_data["version"] == marketing_mcp.__version__

            assert ready_res.status_code == 200
            ready_data = ready_res.json()
            assert ready_data["status"] == "ready"
            assert ready_data["service"] == "pymc-marketing-mcp"
            assert ready_data["checks"]["database"]["status"] == "ok"
            assert ready_data["checks"]["artifact_storage"]["status"] == "ok"
        finally:
            server.should_exit = True
            await task

    asyncio.run(_run())


def test_well_known_mcp_descriptor_exposes_valid_schema(running_server_app):
    """Verify that the discovery endpoint /.well-known/mcp.json exposes valid server capabilities."""
    http_app, _ = running_server_app

    async def _run():
        server, task, port = await _start_server(http_app)
        try:
            base_url = f"http://127.0.0.1:{port}"
            async with httpx2.AsyncClient(base_url=base_url) as client:
                response = await client.get("/.well-known/mcp.json")

            assert response.status_code == 200
            body = response.json()
            assert body["name"] == "PyMC Marketing MCP"
            assert body["protocol_version"] == "2024-11-05"
            assert "/mcp" in body["mcp_endpoint"]
            assert body["capabilities"]["tools"] is True
            assert body["capabilities"]["resources"] is True
        finally:
            server.should_exit = True
            await task

    asyncio.run(_run())


def test_mcp_streamable_http_session_discovers_all_marketing_tools(running_server_app):
    """Verify that an MCP client session over streamable-HTTP initializes and discovers tools."""
    http_app, _ = running_server_app

    async def _run():
        server, task, port = await _start_server(http_app)
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            async with (
                httpx2.AsyncClient() as http_client,
                streamable_http_client(url, http_client=http_client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                tool_list = await session.list_tools()
                tool_names = {t.name for t in tool_list.tools}

                core_expected = {
                    "register_dataset",
                    "validate_dataset",
                    "inspect_dataset",
                    "fit_mmm",
                    "diagnose_mmm",
                    "get_channel_contributions",
                    "get_incremental_roas",
                    "optimize_budget",
                    "fit_clv_model",
                    "predict_customer_clv",
                }
                assert core_expected.issubset(tool_names)
        finally:
            server.should_exit = True
            await task

    asyncio.run(_run())


def test_mcp_streamable_http_executes_dataset_validation_workflow(running_server_app):
    """Verify end-to-end dataset registration and validation through streamable-HTTP MCP session."""
    http_app, tmp_path = running_server_app

    async def _run():
        csv_file = tmp_path / "smoke_mmm.csv"
        raw_data = generate_synthetic_mmm(n=60)
        assert isinstance(raw_data, pd.DataFrame)
        raw_data.to_csv(csv_file, index=False)

        server, task, port = await _start_server(http_app)
        try:
            url = f"http://127.0.0.1:{port}/mcp"
            async with (
                httpx2.AsyncClient() as http_client,
                streamable_http_client(url, http_client=http_client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # Register dataset
                reg_resp = await session.call_tool("register_dataset", arguments={"path": str(csv_file)})
                assert len(reg_resp.content) > 0
                first_reg = reg_resp.content[0]
                assert isinstance(first_reg, TextContent)
                reg_data = json.loads(first_reg.text)
                dataset_id = reg_data["summary"]["dataset_id"]
                assert dataset_id is not None

                # Validate dataset
                val_resp = await session.call_tool(
                    "validate_dataset",
                    arguments={
                        "dataset_id": dataset_id,
                        "date_column": "date",
                        "target_column": "revenue",
                        "channel_columns": ["meta", "google", "tiktok", "youtube"],
                        "control_columns": ["discount"],
                    },
                )
                assert len(val_resp.content) > 0
                first_val = val_resp.content[0]
                assert isinstance(first_val, TextContent)
                val_data = json.loads(first_val.text)
                assert val_data["summary"]["valid_for_modeling"] is True
        finally:
            server.should_exit = True
            await task

    asyncio.run(_run())
