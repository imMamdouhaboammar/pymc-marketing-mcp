from __future__ import annotations

import asyncio
import base64
import json
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server


def _call(server, tool, args):
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.fixture
def test_app(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path / "inbox",
        max_dataset_mb=10,
        auth_enabled=False,
    )
    app = Application(settings)
    server = create_server(app)
    return server, app


def test_html_content_rejected_as_invalid_dataset(test_app):
    server, _ = test_app
    html_payload = "<!DOCTYPE html><html><body><h1>404 Not Found</h1></body></html>"
    b64 = base64.b64encode(html_payload.encode()).decode()
    res = _call(server, "register_dataset", {"content_base64": b64, "filename": "error.csv"})

    assert "error" in res
    assert res["error"]["code"] == "INVALID_DATASET_CONTENT"
    assert "HTML" in res["error"]["message"]


def test_json_content_rejected_as_invalid_dataset(test_app):
    server, _ = test_app
    json_payload = '{"error": "Unauthorized", "status_code": 401}'
    b64 = base64.b64encode(json_payload.encode()).decode()
    res = _call(server, "register_dataset", {"content_base64": b64, "filename": "data.csv"})

    assert "error" in res
    assert res["error"]["code"] == "INVALID_DATASET_CONTENT"
    assert "JSON" in res["error"]["message"]
