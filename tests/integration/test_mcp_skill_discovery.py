"""MCP-native discovery tests for the scientific Skill Pack."""

from __future__ import annotations

import asyncio
import json

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server


@pytest.fixture
def server(tmp_path):
    return create_server(
        Application(
            Settings(
                data_dir=tmp_path / "data",
                artifact_dir=tmp_path / "artifacts",
                metadata_db=tmp_path / "metadata.db",
                ingest_dir=tmp_path,
            )
        )
    )


def _text(resource_result) -> str:
    item = next(iter(resource_result))
    return item.content if isinstance(item.content, str) else item.content.decode()


def test_skill_discovery_surface(server):
    async def _run():
        tools = {tool.name for tool in await server.list_tools()}
        resources = {str(resource.uri) for resource in await server.list_resources()}
        templates = {template.uri_template for template in await server.list_resource_templates()}
        assert "get_skill_guidance" in tools
        assert "list_agentic_skills" in tools
        assert "get_skill_workflow_map" in tools
        assert "marketing://skills" in resources
        assert "marketing://skills/tool-map" in resources
        assert "marketing://skills/workflow-map" in resources
        assert "marketing://skills/decision-gates" in resources
        assert "marketing://skills/{skill_name}" in templates
        assert "marketing://skills/{skill_name}/manifest" in templates

    asyncio.run(_run())


def test_list_agentic_skills_and_workflow_map_tools(server):
    async def _run():
        skills_res = await server.call_tool("list_agentic_skills", {})
        skills_payload = json.loads(skills_res.content[0].text)
        assert skills_payload["summary"]["total_skills"] == 11
        skill_names = {s["name"] for s in skills_payload["evidence"]["skills"]}
        assert "pymc-mmm-workflow" in skill_names
        assert "pymc-budget-optimization" in skill_names
        assert "pymc-diagnostics-gate" in skill_names

        wf_res = await server.call_tool("get_skill_workflow_map", {})
        wf_payload = json.loads(wf_res.content[0].text)
        assert wf_payload["summary"]["total_workflows"] == 11
        assert "workflows" in wf_payload["evidence"]

    asyncio.run(_run())


def test_catalog_and_selected_skill_are_readable(server):
    async def _run():
        catalog = json.loads(_text(await server.read_resource("marketing://skills")))
        assert len(catalog["skills"]) == 11
        assert catalog["schema_version"] == "1"
        text = _text(await server.read_resource("marketing://skills/pymc-diagnostics-gate"))
        assert "# PyMC Diagnostics" in text
        manifest = json.loads(
            _text(await server.read_resource("marketing://skills/pymc-diagnostics-gate/manifest"))
        )
        assert manifest["name"] == "pymc-diagnostics-gate"

        contract_text = _text(
            await server.read_resource("marketing://skills/references/scientific-answer-contract")
        )
        assert "Scientific Answer Contract" in contract_text
        ledger_text = _text(
            await server.read_resource("marketing://skills/references/scientific-source-ledger")
        )
        assert "Scientific Source Ledger" in ledger_text

    asyncio.run(_run())


def test_model_callable_guidance_routes_and_fetches(server):
    async def _run():
        routed = await server.call_tool(
            "get_skill_guidance",
            {"task": "The fit timed out; recover the existing job after disconnect"},
        )
        payload = json.loads(routed.content[0].text)
        assert payload["summary"]["recommended_skill"] == "pymc-job-resilience"
        fetched = await server.call_tool(
            "get_skill_guidance",
            {"skill_name": "pymc-budget-optimization"},
        )
        fetched_payload = json.loads(fetched.content[0].text)
        assert fetched_payload["summary"]["skill_name"] == "pymc-budget-optimization"
        assert "optimize_budget" in fetched_payload["evidence"]["manifest"]["primary_tools"]

    asyncio.run(_run())


def test_unknown_skill_and_path_traversal_are_bounded(server):
    async def _run():
        for name in ("unknown", "../.env"):
            result = await server.call_tool("get_skill_guidance", {"skill_name": name})
            payload = json.loads(result.content[0].text)
            assert payload["error"]["code"] == "SKILL_NOT_FOUND"

    asyncio.run(_run())


def test_skill_delivery_requires_marketing_read_scope(tmp_path):
    from marketing_mcp.mcp.context import ExecutionContext
    from marketing_mcp.security.principal import Principal

    application = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    principal = Principal(
        subject="model-only",
        auth_type="oauth",
        scopes=frozenset({"marketing:model"}),
        tenant_id="tenant-a",
    )
    protected = create_server(
        application,
        context_provider=lambda: ExecutionContext(principal=principal, transport="http"),
    )

    async def _run():
        resource = json.loads(_text(await protected.read_resource("marketing://skills")))
        assert resource["error"]["code"] == "AUTH_FORBIDDEN"
        result = await protected.call_tool("get_skill_guidance", {"task": "fit my MMM"})
        payload = json.loads(result.content[0].text)
        assert payload["error"]["code"] == "AUTH_FORBIDDEN"

    asyncio.run(_run())


def test_skill_resources_do_not_expose_unknown_or_traversal_paths(server):
    async def _run():
        unknown = json.loads(_text(await server.read_resource("marketing://skills/unknown")))
        assert unknown["error"]["code"] == "SKILL_NOT_FOUND"
        from mcp.server.mcpserver.exceptions import ResourceNotFoundError

        with pytest.raises(ResourceNotFoundError):
            await server.read_resource("marketing://skills/%2e%2e%2f.env")

    asyncio.run(_run())
