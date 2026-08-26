"""Integration test for upstream compatibility canary contracts."""

from __future__ import annotations

from scripts.compatibility_canary import verify_canary_contracts, verify_upstream_imports


def test_upstream_imports_succeed():
    versions = verify_upstream_imports()
    assert versions["pymc-marketing"] != "not-installed"
    assert versions["mcp"] != "not-installed"
    assert versions["pydantic"] != "not-installed"


def test_canary_contracts_pass():
    contracts = verify_canary_contracts()
    assert contracts.get("mcp_server_creation") is True
    assert contracts.get("capability_inventory") is True
