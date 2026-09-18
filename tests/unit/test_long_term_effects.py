"""Unit tests for the deterministic VARX long-term-effects prototype (T8).

Fast tests — zero sampling required.
Requirements tested:
- Synthetic ground-truth recovery of positive and damped carryover multipliers
- Lag-before-filter time alignment so missing values cannot create synthetic transitions
- Diagnostic eigenvalue threshold enforcement
- Deterministic point estimates blocked from decision-grade rollup
- Non-stationary explosive models blocked by decision gate
- Honest estimator provenance
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import marketing_mcp.domain.long_term as long_term
from marketing_mcp.domain.long_term import (
    DeterministicVARLongTermEngine,
    LongTermEffectsEngine,
    LongTermRollup,
)
from marketing_mcp.errors import DomainError


@pytest.fixture
def engine():
    return DeterministicVARLongTermEngine()


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


def test_engine_export_name_matches_deterministic_estimator():
    assert hasattr(long_term, "DeterministicVARLongTermEngine")
    assert not hasattr(long_term, "BayesianVARLongTermEngine")


class TestDeterministicVARLongTermEngine:
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

        # Analytic finite-horizon multiplier for the noise-free DGP is 2 - 0.7**12.
        assert "tv_spend" in rollup.channel_multipliers
        mult = rollup.channel_multipliers["tv_spend"]
        assert mult == pytest.approx(2 - 0.7**12, abs=0.25)
        assert rollup.provenance["estimation_method"] == "ridge_regularized_least_squares"
        assert rollup.provenance["uncertainty_quantified"] is False

        # Detailed IRF exists
        assert "tv_spend" in rollup.irfs
        irf = rollup.irfs["tv_spend"]
        assert len(irf.horizons) == 13  # 0 to 12
        assert len(irf.responses) == 13

    def test_multiplier_preserves_damped_negative_carryover_below_one(self, engine):
        rng = np.random.default_rng(7)
        n = 120
        media = rng.normal(0.0, 1.0, n)
        target = np.zeros(n)
        for t in range(1, n):
            target[t] = -0.5 * target[t - 1] + 0.8 * media[t] + rng.normal(0.0, 0.01)

        rollup = engine.fit_var(
            df=pd.DataFrame({"media": media, "target": target}),
            endogenous_columns=["target"],
            exogenous_channels=["media"],
            horizon=12,
        )

        # True finite-horizon multiplier is sum((-0.5) ** h, h=0..12) ~= 2/3.
        assert rollup.channel_multipliers["media"] == pytest.approx(
            sum((-0.5) ** h for h in range(13)),
            abs=0.08,
        )

    def test_near_zero_initial_effect_rejects_undefined_multiplier(self, engine):
        rng = np.random.default_rng(9)
        df = pd.DataFrame(
            {
                "media": rng.normal(0.0, 1.0, 40),
                "target": np.zeros(40),
            }
        )

        with pytest.raises(DomainError) as exc_info:
            engine.fit_var(
                df=df,
                endogenous_columns=["target"],
                exogenous_channels=["media"],
                horizon=4,
            )

        assert exc_info.value.code == "LONG_TERM_MULTIPLIER_UNDEFINED"

    def test_near_zero_initial_effect_rejects_even_when_var_is_explosive(self, engine):
        n = 40
        target = 1.2 ** np.arange(n, dtype=float)
        df = pd.DataFrame({"media": np.zeros(n), "target": target})

        with pytest.raises(DomainError) as exc_info:
            engine.fit_var(
                df=df,
                endogenous_columns=["target"],
                exogenous_channels=["media"],
                horizon=4,
            )

        assert exc_info.value.code == "LONG_TERM_MULTIPLIER_UNDEFINED"

    def test_deterministic_rollup_cannot_become_decision_evidence(self, engine, synthetic_var_data):
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
        with pytest.raises(DomainError) as exc_info:
            engine.rollup_into_decision(base_decision, rollup)

        assert exc_info.value.code == "LONG_TERM_UNCERTAINTY_REQUIRED"

    @pytest.mark.parametrize(
        ("endogenous_columns", "exogenous_channels"),
        [
            (["brand_equity", "brand_equity"], ["tv_spend"]),
            (["brand_equity", "sales"], ["tv_spend", "tv_spend"]),
            (["brand_equity", "sales"], ["sales"]),
        ],
    )
    def test_rejects_duplicate_or_overlapping_varx_roles(
        self,
        engine,
        synthetic_var_data,
        endogenous_columns,
        exogenous_channels,
    ):
        with pytest.raises(DomainError) as exc_info:
            engine.fit_var(
                df=synthetic_var_data,
                endogenous_columns=endogenous_columns,
                exogenous_channels=exogenous_channels,
            )

        assert exc_info.value.code == "INPUT_INVALID"

    def test_missing_endogenous_value_does_not_bridge_non_adjacent_periods(self, engine):
        rng = np.random.default_rng(2)
        n = 40
        media = rng.normal(0.0, 1.0, n)
        target = np.zeros(n)
        for t in range(1, n):
            target[t] = 0.8 * target[t - 1] + 1.2 * media[t]

        dirty = pd.DataFrame({"media": media, "target": target})
        dirty.loc[30, "target"] = np.nan

        rollup = engine.fit_var(
            df=dirty,
            endogenous_columns=["target"],
            exogenous_channels=["media"],
            horizon=4,
        )

        assert rollup.max_eigenvalue == pytest.approx(0.8, abs=0.01)
        assert rollup.channel_multipliers["media"] == pytest.approx(
            sum(0.8**h for h in range(5)),
            abs=0.05,
        )

    def test_minimum_sample_check_counts_complete_adjacent_transitions(self, engine):
        media = np.linspace(0.1, 1.7, 17)
        target = np.zeros(17)
        for t in range(1, 17):
            target[t] = 0.5 * target[t - 1] + media[t]

        dirty = pd.DataFrame({"media": media, "target": target})
        dirty.loc[8, "target"] = np.nan

        with pytest.raises(DomainError) as exc_info:
            engine.fit_var(
                df=dirty,
                endogenous_columns=["target"],
                exogenous_channels=["media"],
            )

        assert exc_info.value.code == "DATASET_TOO_SHORT"

    def test_explosive_fit_reports_actual_finite_horizon_multiplier(self, engine):
        rng = np.random.default_rng(17)
        n = 50
        media = rng.normal(0.0, 1.0, n)
        target = np.zeros(n)
        for t in range(1, n):
            target[t] = 1.08 * target[t - 1] + 0.8 * media[t]

        rollup = engine.fit_var(
            df=pd.DataFrame({"media": media, "target": target}),
            endogenous_columns=["target"],
            exogenous_channels=["media"],
            horizon=4,
        )

        assert rollup.is_stationary is False
        assert rollup.diagnostic_status == "rejected"
        assert rollup.channel_multipliers["media"] == pytest.approx(
            sum(1.08**h for h in range(5)), abs=0.02
        )

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
        assert "prior" not in exc_info.value.next_action.lower()
