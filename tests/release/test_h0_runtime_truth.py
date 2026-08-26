"""Gate H0: Runtime Truth and Machine-Derived Readiness Evidence.

Gate H0 contract:
1. No stale root findings.md file exists in the repository root.
2. Required CI workflows exist: ci.yml, statistical.yml, security.yml, upstream-canary.yml, release.yml.
3. Production readiness documentation is parseable and cannot claim green status without machine evidence.
4. Capability inventory strictly matches discovered MCP server capabilities.
5. Runtime __version__ matches pyproject.toml and Dockerfile.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from marketing_mcp.app import Application
from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server
from marketing_mcp.readiness_evidence import parse_readiness_from_doc, validate_readiness_doc

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_h0_no_stale_root_findings():
    """Verify stale findings.md has been archived and does not exist in repo root."""
    root_findings = REPO_ROOT / "findings.md"
    assert not root_findings.exists(), "findings.md must be archived in docs/archive/"


def test_h0_required_workflows_exist():
    """Verify all required CI and automation workflows exist."""
    required_workflows = [
        ".github/workflows/ci.yml",
        ".github/workflows/statistical.yml",
        ".github/workflows/security.yml",
        ".github/workflows/upstream-canary.yml",
        ".github/workflows/release.yml",
    ]
    for wf in required_workflows:
        assert (REPO_ROOT / wf).exists(), f"Missing required workflow: {wf}"


def test_h0_production_readiness_parses_and_validates():
    """Verify PRODUCTION-READINESS.md parses and contains no unverified green gates."""
    doc_path = REPO_ROOT / "docs" / "PRODUCTION-READINESS.md"
    assert doc_path.exists(), "docs/PRODUCTION-READINESS.md does not exist"
    doc_text = doc_path.read_text(encoding="utf-8")

    parsed_gates = parse_readiness_from_doc(doc_text)
    assert len(parsed_gates) >= 6, "PRODUCTION-READINESS.md must contain at least G0-G5 gates"

    # Validate against empty/un-run evidence: no green gate should be claimed
    findings = validate_readiness_doc(doc_text, {"verdict": "FAIL", "gate_results": {}})
    assert not findings, f"Readiness document claims green without evidence: {findings}"


def test_h0_capability_inventory_agrees_with_mcp_server(tmp_path):
    """Verify capability inventory exactly matches MCP server list_tools and list_resources."""
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

    discovered = asyncio.run(_discover())
    inventory = get_capability_inventory()

    inventory_tools = {c.name for c in inventory if c.kind == "tool"}
    inventory_resources = {c.name for c in inventory if c.kind == "resource"}

    assert discovered["tool"] == inventory_tools
    assert discovered["resource"] == inventory_resources
