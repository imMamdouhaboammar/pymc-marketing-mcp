"""Prevent generated npm dependency inventory from drifting from the manifest."""

import json
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
