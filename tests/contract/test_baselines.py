"""Tests verifying machine-readable baselines for PyMC-Dashboard-Adapter and pymc-marketing-mcp."""

from __future__ import annotations

import json
from pathlib import Path

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


def _load_json(filename: str) -> dict:
    target = BASELINES_DIR / filename
    assert target.is_file(), f"Baseline file missing: {target}"
    with open(target, encoding="utf-8") as f:
        return json.load(f)


def test_mcp_baseline_is_pinned():
    mcp_data = _load_json("mcp.json")
    assert mcp_data["repository"] == "imMamdouhaboammar/pymc-marketing-mcp"
    assert mcp_data["commit"] == "b2ad9fec341bc34f251c95f3b081909896e1ffb7"
    assert mcp_data["package_name"] == "pymc-marketing-mcp"
    assert mcp_data["version"] == "0.4.0"
    assert mcp_data["requires_python"] == ">=3.12,<3.14"
    assert len(mcp_data["stable_capabilities"]) > 0
    assert mcp_data["manifest_sha256"]["pyproject.toml"] == "991cbe796cd440910269f43be4903cba477c92c61bd3774fc0268733687f4782"
    assert mcp_data["manifest_sha256"]["uv.lock"] == "9a1686c209733ee00b606b50e68706c6131adb8ee7b5993f9a7a05d20db453f5"


def test_dashboard_baseline_is_pinned():
    dash_data = _load_json("dashboard.json")
    assert dash_data["repository"] == "imMamdouhaboammar/PyMC-Dashboard-Adapter"
    assert dash_data["commit"] == "ee98c8ec93aeb31e90a4388bea01b80c06d13ba4"
    assert dash_data["package_name"] == "echo-radio"
    assert "react" in dash_data["dependencies"]
    assert dash_data["dependencies"]["react"] == "^19.0.1"
    assert dash_data["manifest_sha256"]["package.json"] == "9f0444ba53959ee4915e689e91c956933d218cc1d87d992c9b79c625cf7299b8"
    assert dash_data["manifest_sha256"]["bun.lock"] == "c7eee4bd95436bce388a35d91e009f382b4ae6c78e07fcb5ec246f91a523f96c"


def test_unified_manifests_summary():
    manifests = _load_json("manifests.json")
    assert manifests["schema_version"] == "1.0"
    assert manifests["donor_repositories"]["mcp"]["commit"] == "b2ad9fec341bc34f251c95f3b081909896e1ffb7"
    assert manifests["donor_repositories"]["dashboard"]["commit"] == "ee98c8ec93aeb31e90a4388bea01b80c06d13ba4"
    assert manifests["invariants"]["no_rust_math"] is True
    assert manifests["invariants"]["postgres_durable_truth"] is True
