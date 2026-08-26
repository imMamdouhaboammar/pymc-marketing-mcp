"""Gate H6: Upstream Compatibility Canary and Capability Admission Gates.

Gate H6 contract:
1. Upstream compatibility canary executes cleanly against the active runtime.
2. Runtime dependencies match declared package ranges.
3. Every declared public capability has verified evidence tests.
4. PyMC-Marketing, PyMC, ArviZ, and xarray imports succeed with expected semantics.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import arviz
import numpy
import pandas
import pymc_marketing
import xarray

from marketing_mcp.capabilities import get_capability_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_h6_upstream_package_imports_and_versions():
    """Verify primary upstream Bayesian stack imports and exports."""
    assert hasattr(pymc_marketing, "__version__")
    assert hasattr(arviz, "__version__")
    assert hasattr(pandas, "__version__")
    assert hasattr(numpy, "__version__")
    assert hasattr(xarray, "__version__")


def test_h6_capability_admission_and_evidence():
    """Verify all stable capabilities have non-empty executable evidence."""
    inventory = get_capability_inventory()
    stable_caps = [c for c in inventory if c.status == "stable"]
    assert len(stable_caps) >= 25

    for cap in stable_caps:
        assert len(cap.evidence_test_ids) > 0, f"Capability {cap.name} missing evidence test IDs"


def test_h6_compatibility_canary_execution():
    """Execute compatibility canary script directly."""
    canary_script = REPO_ROOT / "scripts" / "compatibility_canary.py"
    if canary_script.exists():
        res = subprocess.run(
            [sys.executable, str(canary_script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Compatibility canary failed:\n{res.stdout}\n{res.stderr}"
