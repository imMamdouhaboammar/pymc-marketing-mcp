"""Unit tests for posterior utility objective abstraction (T2).

Fast tests — no PyMC, no sampling required.
Coverage:
- ExpectedResponseObjective reproduces existing maximize_response behaviour
- ExpectedNetProfitObjective reproduces legacy maximize_net_profit behaviour
- Objective registry resolves by name; unknown name fails with clear error
- Blocked diagnostic state cannot invoke objectives (enforced by gate, not objective)
"""

from __future__ import annotations

import numpy as np
import pytest

from marketing_mcp.domain.decisions.financial import FinancialAssumptions
from marketing_mcp.domain.decisions.utility import (
    ExpectedNetProfitObjective,
    ExpectedResponseObjective,
    UtilityObjective,
    get_objective,
    objective_names,
)


class TestExpectedResponseObjective:
    def test_mean_of_samples(self):
        obj = ExpectedResponseObjective()
        samples = np.array([10.0, 20.0, 30.0])
        fa = FinancialAssumptions()
        assert obj.evaluate(samples, fa, spend=0.0) == pytest.approx(20.0)

    def test_single_sample(self):
        obj = ExpectedResponseObjective()
        samples = np.array([42.0])
        fa = FinancialAssumptions()
        assert obj.evaluate(samples, fa, spend=5.0) == pytest.approx(42.0)

    def test_satisfies_protocol(self):
        obj = ExpectedResponseObjective()
        assert isinstance(obj, UtilityObjective)

    def test_name_is_expected_response(self):
        assert ExpectedResponseObjective().name == "expected_response"

    def test_metadata_has_objective_key(self):
        meta = ExpectedResponseObjective().metadata()
        assert meta["objective"] == "expected_response"


class TestExpectedNetProfitObjective:
    def test_net_profit_with_margin(self):
        obj = ExpectedNetProfitObjective()
        samples = np.array([100.0, 100.0, 100.0])  # E[response] = 100
        fa = FinancialAssumptions.from_legacy(margin_pct=0.5)
        result = obj.evaluate(samples, fa, spend=30.0)
        # E[revenue × margin − spend] = 100 × 0.5 − 30 = 20
        assert result == pytest.approx(20.0)

    def test_full_margin_equals_expected_response_minus_spend(self):
        obj = ExpectedNetProfitObjective()
        samples = np.array([50.0, 50.0])
        fa = FinancialAssumptions(gross_margin_rate=1.0)
        result = obj.evaluate(samples, fa, spend=10.0)
        assert result == pytest.approx(50.0 - 10.0)

    def test_contribution_margin_takes_precedence(self):
        obj = ExpectedNetProfitObjective()
        samples = np.array([100.0])
        fa = FinancialAssumptions(gross_margin_rate=0.6, contribution_margin_rate=0.4)
        result = obj.evaluate(samples, fa, spend=0.0)
        assert result == pytest.approx(40.0)

    def test_revenue_per_outcome_scales_correctly(self):
        obj = ExpectedNetProfitObjective()
        samples = np.array([10.0])  # 10 conversions
        fa = FinancialAssumptions(kpi_unit="conversions", revenue_per_outcome=50.0, gross_margin_rate=1.0)
        result = obj.evaluate(samples, fa, spend=0.0)
        assert result == pytest.approx(500.0)  # 10 × 50 × 1.0


class TestObjectiveRegistry:
    def test_resolves_expected_response(self):
        obj = get_objective("expected_response")
        assert obj.name == "expected_response"

    def test_resolves_expected_net_profit(self):
        obj = get_objective("expected_net_profit")
        assert obj.name == "expected_net_profit"

    def test_unknown_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown objective"):
            get_objective("nonexistent_objective")

    def test_objective_names_includes_both_defaults(self):
        names = objective_names()
        assert "expected_response" in names
        assert "expected_net_profit" in names

    def test_risk_aware_objectives_not_yet_registered(self):
        """Guard: risk-aware objectives must not appear before their RFC + tests."""
        forbidden = {"cvar", "probability_exceed", "expected_regret", "lower_quantile"}
        current = set(objective_names())
        assert not current.intersection(forbidden), (
            f"Risk-aware objectives {current & forbidden} added without RFC + tests"
        )
