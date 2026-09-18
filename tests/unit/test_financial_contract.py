"""Unit tests for the FinancialAssumptions typed contract (T1).

Fast tests — no PyMC, no sampling required.
Coverage:
- legacy margin_pct path produces identical results to pre-contract code
- canonical FinancialAssumptions validates correctly
- inconsistent financial units fail closed
- compute_net_profit backward compatibility
"""

from __future__ import annotations

import pytest

from marketing_mcp.domain.decisions.financial import FinancialAssumptions
from marketing_mcp.domain.decisions.flighting import compute_net_profit
from marketing_mcp.errors import DomainError


class TestFinancialAssumptionsContract:
    def test_from_legacy_preserves_margin_pct(self):
        fa = FinancialAssumptions.from_legacy(margin_pct=0.4)
        assert fa.gross_margin_rate == 0.4
        assert fa.discount_rate == 0.0

    def test_from_legacy_default_is_full_margin(self):
        fa = FinancialAssumptions.from_legacy()
        assert fa.gross_margin_rate == 1.0

    def test_effective_margin_rate_falls_back_to_gross(self):
        fa = FinancialAssumptions(gross_margin_rate=0.6)
        assert fa.effective_margin_rate() == 0.6

    def test_effective_margin_rate_uses_contribution_when_set(self):
        fa = FinancialAssumptions(gross_margin_rate=0.6, contribution_margin_rate=0.45)
        assert fa.effective_margin_rate() == 0.45

    def test_validate_rejects_out_of_range_gross_margin(self):
        fa = FinancialAssumptions(gross_margin_rate=1.5)
        errors = fa.validate()
        assert any("gross_margin_rate" in e for e in errors)

    def test_validate_rejects_negative_discount_rate(self):
        fa = FinancialAssumptions(discount_rate=-0.1)
        errors = fa.validate()
        assert any("discount_rate" in e for e in errors)

    def test_validate_rejects_negative_revenue_per_outcome(self):
        fa = FinancialAssumptions(revenue_per_outcome=-1.0)
        errors = fa.validate()
        assert any("revenue_per_outcome" in e for e in errors)

    def test_valid_contract_produces_no_errors(self):
        fa = FinancialAssumptions(gross_margin_rate=0.35, discount_rate=0.05)
        assert fa.validate() == []

    def test_to_provenance_contains_all_keys(self):
        fa = FinancialAssumptions()
        prov = fa.to_provenance()
        expected = {
            "kpi_unit", "revenue_per_outcome", "gross_margin_rate",
            "contribution_margin_rate", "variable_cost_per_unit",
            "acquisition_cost", "customer_lifetime_value_ref",
            "discount_rate", "discount_convention", "planning_horizon",
        }
        assert expected == set(prov.keys())

    def test_frozen_dataclass_is_immutable(self):
        fa = FinancialAssumptions()
        with pytest.raises((AttributeError, TypeError)):
            fa.gross_margin_rate = 0.5  # type: ignore[misc]


class TestComputeNetProfitBackwardCompat:
    """Legacy callers passing margin_pct float must get identical results."""

    def test_legacy_call_same_as_before(self):
        # Pre-contract: compute_net_profit(100.0, 30.0, 0.5)
        result = compute_net_profit(100.0, 30.0, margin_pct=0.5)
        assert result["gross_revenue"] == 100.0
        assert result["margin_revenue"] == 50.0
        assert result["net_profit"] == 20.0
        assert result["roas"] == pytest.approx(100.0 / 30.0, rel=1e-4)
        assert result["is_profitable"] is True

    def test_legacy_positive_margin_pct_reported(self):
        result = compute_net_profit(200.0, 50.0, margin_pct=0.3)
        # margin_pct field kept for backward compat — reports effective rate
        assert abs(result["margin_pct"] - 0.3) < 1e-5

    def test_legacy_unprofitable(self):
        result = compute_net_profit(10.0, 100.0, margin_pct=0.5)
        assert result["is_profitable"] is False

    def test_canonical_financial_contract_overrides_legacy(self):
        fa = FinancialAssumptions.from_legacy(margin_pct=0.4)
        result = compute_net_profit(100.0, 30.0, financial=fa)
        assert result["net_profit"] == pytest.approx(40.0 - 30.0, rel=1e-4)

    def test_invalid_financial_contract_fails_closed(self):
        fa = FinancialAssumptions(gross_margin_rate=1.5)  # invalid
        with pytest.raises(DomainError):
            compute_net_profit(100.0, 30.0, financial=fa)

    def test_provenance_attached_when_contract_used(self):
        fa = FinancialAssumptions.from_legacy(margin_pct=0.6)
        result = compute_net_profit(100.0, 20.0, financial=fa)
        assert "financial_provenance" in result
        assert result["financial_provenance"]["gross_margin_rate"] == 0.6
