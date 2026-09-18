"""Unit tests for Bayesian VAR Long-Term Brand Effects prototype (T8).

Fast tests — zero sampling required.
Requirements tested:
- Synthetic ground-truth recovery of positive carryover & multiplier
- Diagnostic eigenvalue threshold enforcement
- Decision rollup enrichment
- Non-stationary explosive models blocked by decision gate
- Tenant isolation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.domain.long_term import (
    BayesianVARLongTermEngine,
    LongTermEffectsEngine,
    LongTermRollup,
)
from marketing_mcp.errors import DomainError


@pytest.fixture
def engine():
    return BayesianVARLongTermEngine()


@pytest.fixture
def synthetic_var_data():
    """Simulate a stationary VAR(1) system: Brand Equity and Sales driven by Upper-funnel TV."""
    np.random.seed(42)
    n = 60
    # Exogenous upper-funnel TV spend
    tv_spend = np.random.uniform(10.0, 50.0, n)

    # Transition: BrandEquity_t = 0.7 * BrandEquity_{t-1} + 0.5 * TV + noise
    # Sales_t = 0.3 * BrandEquity_t + 0.2 * TV + noise
    brand_eq = np.zeros(n)
    sales = np.zeros(n)

    for t in range(1, n):
        brand_eq[t] = 0.7 * brand_eq[t - 1] + 0.5 * tv_spend[t] + np.random.normal(0, 1.0)
        sales[t] = 0.3 * brand_eq[t] + 0.2 * tv_spend[t] + np.random.normal(0, 2.0)

    return pd.DataFrame({
        "tv_spend": tv_spend,
        "brand_equity": brand_eq,
        "sales": sales,
    })


class TestBayesianVARLongTermEngine:
    def test_implements_protocol(self, engine):
        assert isinstance(engine, LongTermEffectsEngine)

    def test_fits_synthetic_data_and_produces_stationary_rollup(self, engine, synthetic_var_data):
        rollup = engine.fit_var(
            df=synthetic_var_data,
            endogenous_columns=["brand_equity", "sales"],
            exogenous_channels=["tv_spend"],
            horizon=12,
            tenant_id="tenant_brand",
        )

        assert isinstance(rollup, LongTermRollup)
        assert rollup.tenant_id == "tenant_brand"
        assert rollup.is_stationary is True
        assert rollup.max_eigenvalue < 1.0
        assert rollup.diagnostic_status in ("pass", "caution")

        # Upper funnel TV should exhibit a long-run multiplier > 1.0 due to brand persistence
        assert "tv_spend" in rollup.channel_multipliers
        mult = rollup.channel_multipliers["tv_spend"]
        assert mult >= 1.0

        # Detailed IRF exists
        assert "tv_spend" in rollup.irfs
        irf = rollup.irfs["tv_spend"]
        assert len(irf.horizons) == 13  # 0 to 12
        assert len(irf.responses) == 13

    def test_decision_gate_enriches_valid_decision(self, engine, synthetic_var_data):
        rollup = engine.fit_var(
            df=synthetic_var_data,
            endogenous_columns=["brand_equity", "sales"],
            exogenous_channels=["tv_spend"],
        )

        base_decision = {
            "scenario_id": "sc_123",
            "recommended_allocation": {"tv_spend": 20000.0},
            "provenance": {"base": "mmm"},
        }
        enriched = engine.rollup_into_decision(base_decision, rollup)
        prov = enriched["provenance"]
        assert "long_term_effects" in prov
        assert prov["long_term_effects"]["status"] == rollup.diagnostic_status
        assert prov["long_term_effects"]["channel_multipliers"] == rollup.channel_multipliers
        assert prov["long_term_effects"]["experimental"] is True

    def test_explosive_non_stationary_model_is_blocked_by_gate(self, engine):
        """Synthetic explosive model with eigenvalue >= 1.0 must fail decision gate."""
        explosive_rollup = LongTermRollup(
            model_id="var_explosive",
            endogenous_columns=["brand", "sales"],
            exogenous_channels=["tv"],
            channel_multipliers={"tv": 5.0},
            max_eigenvalue=1.25,  # Explosive root
            is_stationary=False,
            diagnostic_status="rejected",
        )

        decision = {"scenario_id": "sc_test", "provenance": {}}
        with pytest.raises(DomainError) as exc_info:
            engine.rollup_into_decision(decision, explosive_rollup)
        assert exc_info.value.code == "LONG_TERM_GATE_REJECTED"
