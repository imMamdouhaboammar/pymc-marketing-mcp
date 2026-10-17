"""Prevent generated dependency and MCP security-floor inventory drift."""

import json
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_dependency_inventory_matches_manifest():
    manifest = json.loads((REPO_ROOT / "dashboard/package.json").read_text(encoding="utf-8"))
    catalog = (REPO_ROOT / "_docs/DEPENDENCIES.md").read_text(encoding="utf-8")
    npm_section = catalog.split("## npm — `dashboard/package.json`", 1)[1].split("\n---", 1)[0]

    dependencies = {**manifest["dependencies"], **manifest["devDependencies"]}
    assert f"**{len(dependencies)} packages**" in npm_section
    for name, version in dependencies.items():
        assert f"| `{name}` | `{version}` |" in npm_section, name


def test_mcp_dependency_security_floor_matches_lock_and_catalog():
    """Reject vulnerable locked MCP SDK versions and stale Python inventory claims."""
    manifest = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependency = next(d for d in manifest["project"]["dependencies"] if d.startswith("mcp[cli]>="))
    match = re.fullmatch(r"mcp\[cli\]>=(\d+\.\d+\.\d+),<3", dependency)
    assert match, dependency
    min_version = tuple(map(int, match.group(1).split(".")))
    assert min_version >= (2, 2, 0), "CVE-2026-59951 requires MCP >=2.2.0"

    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_mcp = next(pkg for pkg in lock["package"] if pkg["name"] == "mcp")
    locked_version = tuple(map(int, locked_mcp["version"].split(".")[:3]))
    assert locked_version >= min_version, "uv.lock contains a vulnerable MCP SDK version"

    catalog = (REPO_ROOT / "_docs/DEPENDENCIES.md").read_text(encoding="utf-8")
    python_section = catalog.split("## pyproject — `pyproject.toml`", 1)[1]
    assert f"| `mcp` | `>={match.group(1)},<3` |" in python_section
