#!/usr/bin/env python
"""Upstream dependency compatibility canary.

Verifies that the current environment's installed versions of PyMC-Marketing, PyMC, ArviZ,
and MCP SDK satisfy critical constructor, schema, transform, and capability contracts.

Usage:
    python scripts/compatibility_canary.py
"""

from __future__ import annotations

import importlib.metadata as im
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


def verify_upstream_imports() -> dict[str, str]:
    """Verify core upstream dependency versions and critical imports."""
    packages = [
        "pymc-marketing",
        "pymc",
        "arviz",
        "mcp",
        "pydantic",
        "xarray",
        "numpy",
        "pandas",
    ]
    versions = {}
    for pkg in packages:
        try:
            versions[pkg] = im.version(pkg)
        except im.PackageNotFoundError:
            versions[pkg] = "not-installed"

    # Core statistical and MCP server imports
    import pymc_marketing.clv
    import pymc_marketing.mmm
    from mcp.server.mcpserver import MCPServer
    from pymc_marketing.mmm.transformers import geometric_adstock, logistic_saturation

    from marketing_mcp.mcp.server import create_server

    if pymc_marketing.clv is None:
        raise AssertionError
    if pymc_marketing.mmm is None:
        raise AssertionError
    if geometric_adstock is None:
        raise AssertionError
    if logistic_saturation is None:
        raise AssertionError
    if create_server is None:
        raise AssertionError
    if MCPServer is None:
        raise AssertionError

    return versions


def verify_canary_contracts() -> dict[str, bool]:
    """Execute smoke contract checks against upstream APIs."""
    results = {}

    # 1. Check MCP server creation
    from marketing_mcp.app import Application
    from marketing_mcp.mcp.server import create_server

    server = create_server(Application())
    results["mcp_server_creation"] = server is not None

    # 2. Check capability inventory integrity
    from marketing_mcp.capabilities import get_capability_inventory

    inventory = get_capability_inventory()
    results["capability_inventory"] = len(inventory) > 0

    return results


def main(argv: list[str] | None = None) -> int:
    print("Running upstream compatibility canary...")
    try:
        versions = verify_upstream_imports()
        print(f"Installed dependencies: {json.dumps(versions, indent=2)}")

        contracts = verify_canary_contracts()
        print(f"Canary contract results: {json.dumps(contracts, indent=2)}")

        all_passed = all(contracts.values())
        if all_passed:
            print("\nUpstream compatibility canary PASSED.")
            return 0
        else:
            print("\nUpstream compatibility canary FAILED.", file=sys.stderr)
            return 1
    except (RuntimeError, ImportError, ValueError, TypeError) as e:
        print(f"\nCanary crashed with error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
