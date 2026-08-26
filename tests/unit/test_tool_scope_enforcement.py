"""Scope enforcement at tool execution (Wave 3 Task 5).

Contract:
- Every tool handler resolves its required scope from the policy map and
  enforces it against the request's principal BEFORE doing any work.
- A read-only principal gets AUTH_FORBIDDEN on decision tools.
- An anonymous principal (None) gets AUTH_REQUIRED.
- The trusted stdio provider grants everything, keeping local flows frictionless.
"""

from __future__ import annotations

import asyncio

from marketing_mcp.app import Application
from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.policy import TOOL_SCOPES
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
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


class TestExecutionScopeEnforcement:
    def test_read_only_principal_blocked_on_decision_tool(self, tmp_path):
        server = create_server(
            _app(tmp_path),
            context_provider=_provider_for(
                Principal(
                    subject="analyst",
                    auth_type="oauth",
                    scopes=frozenset(["marketing:read"]),
                )
            ),
        )
        payload = _call(
            server,
            "simulate_budget",
            {
                "config": {
                    "model_id": "x",
                    "planning_periods": 4,
                    "changes": {"meta": {"type": "relative", "value": 0.1}},
                }
            },
        )
        assert payload["error"]["code"] == "AUTH_FORBIDDEN"

    def test_anonymous_principal_rejected_auth_required(self, tmp_path):
        server = create_server(_app(tmp_path), context_provider=_provider_for(None))
        payload = _call(server, "get_model_status", {"model_id": "x"})
        assert payload["error"]["code"] == "AUTH_REQUIRED"

    def test_read_principal_can_call_read_tool(self, tmp_path):
        server = create_server(
            _app(tmp_path),
            context_provider=_provider_for(
                Principal(
                    subject="analyst",
                    auth_type="oauth",
                    scopes=frozenset(["marketing:read"]),
                )
            ),
        )
        payload = _call(server, "get_model_status", {"model_id": "does-not-exist"})
        # Gate passed: failure is domain-level, not authorization.
        assert payload["error"]["code"] != "AUTH_FORBIDDEN"
        assert payload["error"]["code"] != "AUTH_REQUIRED"

    def test_stdio_default_grants_everything(self, tmp_path):
        server = create_server(_app(tmp_path))
        payload = _call(
            server,
            "simulate_budget",
            {
                "config": {
                    "model_id": "nope",
                    "planning_periods": 4,
                    "changes": {"meta": {"type": "relative", "value": 0.1}},
                }
            },
        )
        assert payload["error"]["code"] not in ("AUTH_FORBIDDEN", "AUTH_REQUIRED")


class TestScopeMapCompleteness:
    def test_every_inventory_tool_has_a_policy_entry(self):
        inventory_tools = {
            cap.name
            for cap in get_capability_inventory()
            if cap.kind == "tool" and cap.status != "deprecated"
        }
        missing = inventory_tools - set(TOOL_SCOPES)
        assert not missing, f"Tools without scope mapping: {sorted(missing)}"

    def test_every_mapped_scope_is_in_catalog(self):
        from marketing_mcp.security.policy import SCOPE_CATALOG

        unknown = set(TOOL_SCOPES.values()) - SCOPE_CATALOG
        assert not unknown
