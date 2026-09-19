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
    LowerQuantileObjective,
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
        fa = FinancialAssumptions(
            kpi_unit="conversions", revenue_per_outcome=50.0, gross_margin_rate=1.0
        )
        result = obj.evaluate(samples, fa, spend=0.0)
        assert result == pytest.approx(500.0)  # 10 × 50 × 1.0


class TestLowerQuantileObjective:
    def test_satisfies_protocol(self):
        obj = LowerQuantileObjective()
        assert isinstance(obj, UtilityObjective)

    def test_name_and_metadata(self):
        obj = LowerQuantileObjective(quantile=0.05)
        assert obj.name == "lower_quantile"
        meta = obj.metadata()
        assert meta["objective"] == "lower_quantile"
        assert meta["quantile"] == 0.05
        assert "5%" in meta["description"]

    def test_zero_variance_matches_expected_net_profit(self):
        obj = LowerQuantileObjective(quantile=0.10)
        net_profit_obj = ExpectedNetProfitObjective()
        samples = np.array([100.0, 100.0, 100.0, 100.0])
        fa = FinancialAssumptions(gross_margin_rate=0.5)
        spend = 25.0

        val_lq = obj.evaluate(samples, fa, spend=spend)
        val_enp = net_profit_obj.evaluate(samples, fa, spend=spend)
        assert val_lq == pytest.approx(val_enp)
        assert val_lq == pytest.approx(100.0 * 0.5 - 25.0)

    def test_higher_variance_yields_strictly_lower_utility(self):
        obj = LowerQuantileObjective(quantile=0.10)
        fa = FinancialAssumptions(gross_margin_rate=1.0)
        spend = 0.0

        # Mean is identical (100.0), but spread differs
        low_risk_samples = np.linspace(95.0, 105.0, 101)  # mean 100, variance small
        high_risk_samples = np.linspace(50.0, 150.0, 101)  # mean 100, variance large

        val_low_risk = obj.evaluate(low_risk_samples, fa, spend=spend)
        val_high_risk = obj.evaluate(high_risk_samples, fa, spend=spend)

        assert val_high_risk < val_low_risk
        assert val_low_risk == pytest.approx(96.0, rel=1e-2)
        assert val_high_risk == pytest.approx(60.0, rel=1e-2)

    def test_linear_spend_deduction(self):
        obj = LowerQuantileObjective(quantile=0.20)
        samples = np.linspace(10.0, 100.0, 50)
        fa = FinancialAssumptions(gross_margin_rate=0.8)

        u1 = obj.evaluate(samples, fa, spend=10.0)
        u2 = obj.evaluate(samples, fa, spend=30.0)
        assert u1 - u2 == pytest.approx(20.0)

    def test_margin_and_revenue_scaling(self):
        obj = LowerQuantileObjective(quantile=0.10)
        samples = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        # revenue_per_outcome = 2.0, gross_margin = 0.5 -> effective multiplier = 1.0
        fa = FinancialAssumptions(revenue_per_outcome=2.0, gross_margin_rate=0.5)
        result = obj.evaluate(samples, fa, spend=5.0)
        expected = float(np.quantile(samples * 2.0 * 0.5 - 5.0, 0.10))
        assert result == pytest.approx(expected)

    def test_invalid_quantile_raises_value_error(self):
        with pytest.raises(ValueError, match="quantile must be strictly between 0 and 1"):
            LowerQuantileObjective(quantile=0.0)
        with pytest.raises(ValueError, match="quantile must be strictly between 0 and 1"):
            LowerQuantileObjective(quantile=1.0)
        with pytest.raises(ValueError, match="quantile must be strictly between 0 and 1"):
            LowerQuantileObjective(quantile=-0.1)

    def test_quantile_monotonicity(self):
        samples = np.linspace(10.0, 200.0, 100)
        fa = FinancialAssumptions(gross_margin_rate=1.0)
        spend = 10.0
        q10 = LowerQuantileObjective(quantile=0.10).evaluate(samples, fa, spend=spend)
        q50 = LowerQuantileObjective(quantile=0.50).evaluate(samples, fa, spend=spend)
        q90 = LowerQuantileObjective(quantile=0.90).evaluate(samples, fa, spend=spend)
        assert q10 < q50 < q90


class TestObjectiveRegistry:
    def test_resolves_expected_response(self):
        obj = get_objective("expected_response")
        assert obj.name == "expected_response"

    def test_resolves_expected_net_profit(self):
        obj = get_objective("expected_net_profit")
        assert obj.name == "expected_net_profit"

    def test_resolves_lower_quantile(self):
        obj = get_objective("lower_quantile")
        assert obj.name == "lower_quantile"
        assert isinstance(obj, LowerQuantileObjective)

    def test_unknown_name_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown objective"):
            get_objective("nonexistent_objective")

    def test_objective_names_includes_registered(self):
        names = objective_names()
        assert "expected_response" in names
        assert "expected_net_profit" in names
        assert "lower_quantile" in names

    def test_risk_aware_objectives_not_yet_registered(self):
        """Guard: unimplemented risk-aware objectives must not appear before their RFC + tests."""
        forbidden = {"cvar", "probability_exceed", "expected_regret"}
        current = set(objective_names())
        assert not current.intersection(forbidden), (
            f"Risk-aware objectives {current & forbidden} added without RFC + tests"
        )
