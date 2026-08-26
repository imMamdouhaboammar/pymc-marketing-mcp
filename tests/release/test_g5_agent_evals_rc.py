"""Gate G5 Release Tests: Agent Evals and Release Candidate Readiness (Wave 7 & 8).

Verifies:
- Autonomous agents strictly adhere to Bayesian decision gates
- Agent cannot bypass diagnostics or perform unauthorized cross-tenant actions
- Release candidate readiness criteria are satisfied
"""

from __future__ import annotations

import subprocess
import sys

from marketing_mcp import __version__
from marketing_mcp.capabilities import get_capability_inventory


class TestGateG5AgentEvalsAndRC:
    def test_all_agent_eval_scenarios_pass(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/evals/test_agent_behavior_evals.py", "-v"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Agent evals failed:\n{result.stdout}\n{result.stderr}"

    def test_all_declared_capabilities_have_non_empty_evidence(self):
        inventory = get_capability_inventory()
        stable_caps = [c for c in inventory if c.status == "stable"]
        assert len(stable_caps) >= 25
        for cap in stable_caps:
            assert len(cap.evidence_test_ids) > 0, f"Stable capability '{cap.name}' has no evidence tests"

    def test_package_metadata_and_version_valid(self):
        assert __version__.count(".") >= 2
