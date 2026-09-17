from __future__ import annotations

import asyncio
import json

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


class ContextState:
    current: ExecutionContext = ExecutionContext()


def _call(server, tool, args, context: ExecutionContext):
    ContextState.current = context
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.fixture
def multi_tenant_env(tmp_path):
    data_dir = tmp_path / "data"
    artifact_dir = tmp_path / "artifacts"
    metadata_db = tmp_path / "metadata.db"
    inbox_dir = tmp_path / "inbox"
    data_dir.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    inbox_dir.mkdir(parents=True)

    # Seed an inbox file
    (inbox_dir / "confidential_inbox.csv").write_text("date,revenue\n2026-01-01,100\n")

    settings = Settings(
        data_dir=data_dir,
        artifact_dir=artifact_dir,
        metadata_db=metadata_db,
        ingest_dir=inbox_dir,
        max_dataset_mb=10,
        auth_enabled=False,
    )
    app = Application(settings)
    server = create_server(app, context_provider=lambda: ContextState.current)

    # Seed dataset for Tenant A
    p_a = Principal(subject="user_a", auth_type="api_key", tenant_id="tenant_a", scopes=frozenset(["marketing:write"]))
    app.datasets.register_bytes(b"date,sales\n2026-01-01,10\n", filename="tenant_a.csv", principal=p_a)

    # Seed dataset for Tenant B
    p_b = Principal(subject="user_b", auth_type="api_key", tenant_id="tenant_b", scopes=frozenset(["marketing:write"]))
    app.datasets.register_bytes(b"date,sales\n2026-01-01,20\n", filename="tenant_b.csv", principal=p_b)

    # Seed dataset for Default Tenant
    p_def = Principal(subject="user_def", auth_type="api_key", tenant_id="default", scopes=frozenset(["marketing:write"]))
    app.datasets.register_bytes(b"date,sales\n2026-01-01,30\n", filename="default.csv", principal=p_def)

    return server, app


def test_tenant_a_cannot_see_other_tenants_or_inbox(multi_tenant_env):
    server, app = multi_tenant_env
    ctx_a = ExecutionContext(
        principal=Principal(subject="user_a", auth_type="api_key", tenant_id="tenant_a", scopes=frozenset(["marketing:read"]))
    )
    res = _call(server, "list_datasets", {}, ctx_a)

    # Tenant A must only see 1 dataset (its own)
    assert res["summary"]["total_registered"] == 1
    # Tenant A must NOT see server inbox files
    assert res["summary"]["total_inbox_files"] == 0
    assert len(res["evidence"]["inbox_files"]) == 0


def test_default_tenant_cannot_bypass_isolation(multi_tenant_env):
    server, app = multi_tenant_env
    ctx_def = ExecutionContext(
        principal=Principal(subject="user_def", auth_type="api_key", tenant_id="default", scopes=frozenset(["marketing:read"]))
    )
    res = _call(server, "list_datasets", {}, ctx_def)

    # Default tenant must only see 1 dataset (tenant_id == default), NOT tenant_a or tenant_b
    assert res["summary"]["total_registered"] == 1
    # Default tenant HTTP caller must NOT see server inbox files
    assert res["summary"]["total_inbox_files"] == 0


def test_admin_and_stdio_can_see_all_datasets_and_inbox(multi_tenant_env):
    server, app = multi_tenant_env
    # Stdio local caller
    ctx_stdio = ExecutionContext(
        principal=Principal(subject="local", auth_type="stdio", scopes=frozenset(["marketing:read"]))
    )
    res_stdio = _call(server, "list_datasets", {}, ctx_stdio)
    assert res_stdio["summary"]["total_registered"] == 3
    assert res_stdio["summary"]["total_inbox_files"] == 1

    # Admin HTTP caller
    ctx_admin = ExecutionContext(
        principal=Principal(subject="admin", auth_type="api_key", scopes=frozenset(["marketing:read", "marketing:admin"]))
    )
    res_admin = _call(server, "list_datasets", {}, ctx_admin)
    assert res_admin["summary"]["total_registered"] == 3
    assert res_admin["summary"]["total_inbox_files"] == 1
