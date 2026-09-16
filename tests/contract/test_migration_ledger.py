"""Tests verifying the migration capability ledger completeness (UP-008)."""

from __future__ import annotations

import json
from pathlib import Path

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


def test_migration_ledger_completeness():
    with open(BASELINES_DIR / "capability_migration_ledger.json", encoding="utf-8") as f:
        ledger = json.load(f)

    with open(BASELINES_DIR / "mcp_tools_snapshot.json", encoding="utf-8") as f:
        tools_snap = json.load(f)

    with open(BASELINES_DIR / "mcp_resources_snapshot.json", encoding="utf-8") as f:
        resources_snap = json.load(f)

    with open(BASELINES_DIR / "dashboard_critical_journeys.json", encoding="utf-8") as f:
        journeys_snap = json.load(f)

    # 1. Every tool in the snapshot is mapped to a target owner and cutover gate
    ledger_tool_names = {t["name"] for t in ledger["tools"]}
    expected_tool_names = {t["name"] for t in tools_snap["tools"]}
    assert ledger_tool_names == expected_tool_names
    for t in ledger["tools"]:
        assert t["target_owner"]
        assert t["cutover_gate"].startswith("G_")
        assert t["adapter_compatibility_required"] is True

    # 2. Every resource in the snapshot is mapped
    ledger_resources = {r["uri_template"] for r in ledger["resources"]}
    expected_resources = {r["uri_template"] for r in resources_snap["resources"]}
    assert ledger_resources == expected_resources

    # 3. Every dashboard route is mapped
    ledger_routes = {r["route"] for r in ledger["dashboard_routes"]}
    expected_routes = {j["endpoint"] for j in journeys_snap["journeys"]}
    assert ledger_routes == expected_routes

    # 4. Total count matches
    assert ledger["total_capabilities_tracked"] == len(expected_tool_names) + len(expected_resources) + len(expected_routes)
