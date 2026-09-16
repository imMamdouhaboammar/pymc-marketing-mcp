"""Contract tests verifying MCP discovery snapshot fidelity against baselines (UP-002)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


@pytest.fixture
def mcp_server(tmp_path):
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    return create_server(app)


def test_tools_snapshot_exact_match(mcp_server):
    with open(BASELINES_DIR / "mcp_tools_snapshot.json", encoding="utf-8") as f:
        snapshot = json.load(f)

    tools = asyncio.run(mcp_server.list_tools())
    assert len(tools) == snapshot["total"]

    expected_tool_names = {t["name"] for t in snapshot["tools"]}
    actual_tool_names = {t.name for t in tools}
    assert actual_tool_names == expected_tool_names

    # Verify input_schema properties for key baseline tools
    tool_map = {t.name: t for t in tools}
    for expected in snapshot["tools"]:
        tool = tool_map[expected["name"]]
        actual_schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", None))
        assert actual_schema is not None
        assert actual_schema.get("type") == "object"


def test_resources_snapshot_exact_match(mcp_server):
    with open(BASELINES_DIR / "mcp_resources_snapshot.json", encoding="utf-8") as f:
        snapshot = json.load(f)

    resources = asyncio.run(mcp_server.list_resource_templates())
    assert len(resources) == snapshot["total"]

    expected_uris = {r["uri_template"] for r in snapshot["resources"]}
    actual_uris = {str(r.uri_template) for r in resources}
    assert actual_uris == expected_uris
