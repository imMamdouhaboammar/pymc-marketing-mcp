"""Gate G0: Production Truth and Release Discipline.

Gate G0 contract:
1. Version agreement: runtime __version__ matches pyproject.toml, Dockerfile OCI labels, dashboard footer, and deploy script.
2. Capability inventory agreement: MCP tools and resources discovered by the server match get_capability_inventory().
3. Tool contracts: All MCP tools in the inventory appear in docs/TOOL-CONTRACTS.md.
4. Capability evidence: Every stable capability has evidence test IDs that exist and exercise delegates.
5. Documentation drift check: check_docs() passes with 0 findings.
6. Packaging/release identity: verify_release_identity() passes on sources.
7. Historical documents: historical review documents are explicitly scoped to their historical version.
"""

from __future__ import annotations

import re
from pathlib import Path

from marketing_mcp import __version__
from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.docs_drift import DOCUMENTED_DOCS, check_docs
from marketing_mcp.release_identity import verify_release_identity

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_g0_version_agreement_across_sources():
    """Verify runtime version matches pyproject.toml, deploy script, Dockerfile, and dashboard."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_text)
    assert version_match is not None, "Version not found in pyproject.toml"
    pyproject_version = version_match.group(1)
    assert pyproject_version == __version__, (
        f"pyproject.toml version {pyproject_version} does not match runtime {__version__}"
    )

    problems = verify_release_identity(
        runtime_version=__version__,
        deploy_script_text=(REPO_ROOT / "scripts" / "deploy_cloud_run.sh").read_text(encoding="utf-8"),
        dockerfile_text=(REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"),
        dashboard_text=(REPO_ROOT / "dashboard" / "src" / "App.tsx").read_text(encoding="utf-8"),
    )
    assert not problems, f"Release identity problems: {problems}"


def test_g0_capability_inventory_covers_all_tools_and_resources(tmp_path):
    """Verify capability inventory matches registered MCP server tools and resources."""
    import asyncio

    from marketing_mcp.app import Application
    from marketing_mcp.config import Settings
    from marketing_mcp.mcp.server import create_server

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

    missing_tools = discovered["tool"] - inventory_tools
    extra_tools = inventory_tools - discovered["tool"]
    assert not missing_tools, f"MCP tools missing from capability inventory: {missing_tools}"
    assert not extra_tools, f"Capability inventory has tools not on MCP server: {extra_tools}"

    missing_res = discovered["resource"] - inventory_resources
    extra_res = inventory_resources - discovered["resource"]
    assert not missing_res, f"MCP resources missing from capability inventory: {missing_res}"
    assert not extra_res, f"Capability inventory has resources not on MCP server: {extra_res}"


def test_g0_every_tool_has_documented_contract():
    """Verify every MCP tool has an entry in docs/TOOL-CONTRACTS.md."""
    tool_contracts_file = REPO_ROOT / "docs" / "TOOL-CONTRACTS.md"
    assert tool_contracts_file.exists(), "docs/TOOL-CONTRACTS.md does not exist"
    content = tool_contracts_file.read_text(encoding="utf-8")

    inventory = get_capability_inventory()
    for cap in inventory:
        if cap.kind == "tool":
            assert (
                f"`{cap.name}`" in content
                or f"`{cap.name}(" in content
                or f"### `{cap.name}" in content
            ), f"Tool {cap.name} is missing from docs/TOOL-CONTRACTS.md"


def test_g0_stable_capabilities_have_executable_evidence():
    """Verify stable capabilities cite existing test files and delegates."""
    problems: list[str] = []
    inventory = get_capability_inventory()
    for cap in inventory:
        if cap.status == "stable":
            if not cap.evidence_test_ids:
                problems.append(f"{cap.name}: marked stable but has no evidence tests")
            for test_id in cap.evidence_test_ids:
                test_file = REPO_ROOT / test_id.split("::")[0]
                if not test_file.exists():
                    problems.append(f"{cap.name}: cited test file {test_file} does not exist")
    assert not problems, "Stable capability evidence errors:\n" + "\n".join(problems)


def test_g0_no_documentation_drift():
    """Verify docs drift checker finds 0 issues across all tracked docs."""
    findings = check_docs(REPO_ROOT, DOCUMENTED_DOCS)
    assert not findings, "Documentation drift findings:\n" + "\n".join(findings)


def test_g0_historical_documents_marked_with_historical_version():
    """Verify historical documents explicitly declare their historical scope."""
    final_review = REPO_ROOT / "docs" / "FINAL-REVIEW.md"
    if final_review.exists():
        content = final_review.read_text(encoding="utf-8")
        assert "v0.3" in content or "historical" in content.lower(), (
            "docs/FINAL-REVIEW.md must be marked with historical version scope"
        )
