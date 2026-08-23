"""Capability inventory drift tests.

Slice 2.1 contract: every tool and resource template the MCP server actually exposes must have
exactly one capability record, and the registry must not claim capabilities the server does not
expose.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.capabilities import (
    CAPABILITY_KINDS,
    CAPABILITY_STATUSES,
    get_capability_inventory,
)
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server


@pytest.fixture(scope="module")
def discovered(tmp_path_factory) -> dict[str, set[str]]:
    """Discover tool and resource-template names from a real in-process MCP server."""
    tmp_path: Path = tmp_path_factory.mktemp("capability-discovery")
    server = create_server(
        Application(
            Settings(
                data_dir=tmp_path / "data",
                artifact_dir=tmp_path / "artifacts",
                metadata_db=tmp_path / "metadata.db",
                ingest_dir=tmp_path,
            )
        )
    )

    async def _discover() -> dict[str, set[str]]:
        tools = {tool.name for tool in await server.list_tools()}
        templates = {template.uri_template for template in await server.list_resource_templates()}
        static = {str(resource.uri) for resource in await server.list_resources()}
        return {"tool": tools, "resource": templates | static}

    return asyncio.run(_discover())


def test_inventory_covers_every_discovered_tool(discovered):
    registered = {c.name for c in get_capability_inventory() if c.kind == "tool"}
    missing = discovered["tool"] - registered
    assert not missing, f"tools exposed by the MCP server with no capability record: {sorted(missing)}"


def test_inventory_claims_no_tool_the_server_does_not_expose(discovered):
    registered = {c.name for c in get_capability_inventory() if c.kind == "tool"}
    phantom = registered - discovered["tool"]
    assert not phantom, f"capability records for tools the server does not expose: {sorted(phantom)}"


def test_inventory_covers_every_discovered_resource(discovered):
    registered = {c.name for c in get_capability_inventory() if c.kind == "resource"}
    assert registered == discovered["resource"]


def test_capability_names_are_unique():
    inventory = get_capability_inventory()
    names = [c.name for c in inventory]
    assert len(names) == len(set(names))


def test_capability_fields_use_the_declared_vocabulary():
    for capability in get_capability_inventory():
        assert capability.kind in CAPABILITY_KINDS
        assert capability.status in CAPABILITY_STATUSES
        assert capability.domain, f"{capability.name} has no domain"
        assert isinstance(capability.decision_gate_required, bool)


def test_decision_gate_flags_match_service_enforcement():
    """The registry must describe the gate the code enforces today, not the desired policy."""
    import inspect

    from marketing_mcp.services.decision_service import DecisionService

    source = inspect.getsource(DecisionService)
    gated_methods = {
        "optimize_budget": "def optimize(",
        "simulate_budget": "def simulate(",
        "optimize_flighting": "def optimize_flighting(",
    }
    by_name = {c.name: c for c in get_capability_inventory()}
    for tool, marker in gated_methods.items():
        body_start = source.index(marker)
        next_def = source.find("\n    def ", body_start + 1)
        body = source[body_start : next_def if next_def != -1 else len(source)]
        enforced = "_approved(" in body
        assert by_name[tool].decision_gate_required is enforced, (
            f"{tool}: registry says decision_gate_required="
            f"{by_name[tool].decision_gate_required} but code enforcement is {enforced}"
        )
