"""Tests and benchmarks for Rust MCMC diagnostics and decision gates."""

from __future__ import annotations

import pytest

from marketing_mcp.accelerators import (
    fast_mcmc_diagnostics,
)


def test_fast_mcmc_diagnostics_approved():
    # 4 parameters, all good R-hat and ESS, 0 divergences
    rhats = [1.001, 1.005, 1.012, 1.003]
    esses = [1200.0, 850.0, 1500.0, 920.0]
    result = fast_mcmc_diagnostics(rhats, esses, divergences=0)

    assert result["decision_status"] == "approved"
    assert result["decision_tools_enabled"] is True
    assert result["divergences"] == 0
    assert result["max_rhat"] == pytest.approx(1.012)
    assert result["min_ess"] == pytest.approx(850.0)
    assert result["failures"] == []


def test_fast_mcmc_diagnostics_rejected_divergences():
    rhats = [1.001, 1.002]
    esses = [1000.0, 1200.0]
    result = fast_mcmc_diagnostics(rhats, esses, divergences=3)

    assert result["decision_status"] == "rejected"
    assert result["decision_tools_enabled"] is False
    assert result["divergences"] == 3
    assert any("divergent transition" in f for f in result["failures"])


def test_fast_mcmc_diagnostics_rejected_rhat():
    rhats = [1.001, 1.085]  # > 1.05
    esses = [800.0, 600.0]
    result = fast_mcmc_diagnostics(rhats, esses, divergences=0)

    assert result["decision_status"] == "rejected"
    assert result["decision_tools_enabled"] is False
    assert any("R-hat" in f for f in result["failures"])


def test_fast_mcmc_diagnostics_caution():
    rhats = [1.001, 1.025]  # between 1.02 and 1.05
    esses = [800.0, 350.0]  # between 100 and 400
    result = fast_mcmc_diagnostics(rhats, esses, divergences=0)

    assert result["decision_status"] == "caution"
    assert result["decision_tools_enabled"] is True
    assert len(result["warnings"]) > 0
    assert result["failures"] == []
