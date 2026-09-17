"""Unit tests for record_agent_insight and get_agent_insights MCP tools."""

from __future__ import annotations

import asyncio
import json
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


def _app(tmp_path):
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )


def _provider_for(principal):
    return lambda: ExecutionContext(principal=principal)


def _call(server, tool, args):
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def test_insight_tools_mcp_flow(tmp_path):
    app = _app(tmp_path)
    principal = Principal(
        subject="user_123",
        auth_type="api_key",
        tenant_id="tenant_alpha",
        scopes=frozenset({"marketing:read", "marketing:model"}),
    )
    server = create_server(app, context_provider=_provider_for(principal))

    # 1. Record an insight
    record_payload = {
        "category": "eda_finding",
        "summary": "Target KPI exhibits heavy right skew",
        "details": "Recommend log transform or Student-t likelihood to handle extreme holiday spikes.",
        "dataset_id": "raw_sales_data",
        "severity": "info",
        "tags": ["eda", "sales", "distribution"],
    }
    rec_res = _call(server, "record_agent_insight", record_payload)
    assert "summary" in rec_res
    summary = rec_res["summary"]
    assert summary["insight_id"].startswith("ins_")
    assert summary["tenant_id"] == "tenant_alpha"
    assert summary["category"] == "eda_finding"
    assert "get_agent_insights" in rec_res.get("next_actions", [])

    # 2. Query insights back
    query_res = _call(server, "get_agent_insights", {"category": "eda_finding"})
    assert "summary" in query_res
    insights = query_res["summary"]["insights"]
    assert len(insights) == 1
    assert insights[0]["insight_id"] == summary["insight_id"]
    assert insights[0]["summary"] == "Target KPI exhibits heavy right skew"
    assert insights[0]["tags"] == ["eda", "sales", "distribution"]


def test_insight_tools_forbidden_without_model_scope(tmp_path):
    app = _app(tmp_path)
    read_only_principal = Principal(
        subject="user_ro",
        auth_type="api_key",
        tenant_id="tenant_alpha",
        scopes=frozenset({"marketing:read"}),
    )
    server = create_server(app, context_provider=_provider_for(read_only_principal))

    # Recording requires marketing:model scope
    res = _call(server, "record_agent_insight", {
        "category": "general_note",
        "summary": "Testing read only permission",
    })
    # Must return AUTH_FORBIDDEN in errors or envelope
    assert "error" in res or res.get("status") == "error" or "AUTH_FORBIDDEN" in str(res)
