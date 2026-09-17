"""Tests for prior sensitivity contract fidelity and multi-dimensional evaluation.

Verifies:
1. evaluate_prior_sensitivity evaluates both adstock and saturation dimensions.
2. tested_dimensions contract returns {"adstock": True, "saturation": True}.
3. Each scenario returns scenario_config with explicit adstock and saturation keys.
4. Shift detection and findings contracts operate correctly.
5. Failures during individual refits are recorded without crashing the entire assessment.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter


class ControllableFakeMMM:
    """Lightweight test double for MMM refitting in prior sensitivity."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.fitted = False

    def build_model(self, X, y):
        pass

    def add_original_scale_contribution_variable(self, var):
        pass

    def fit(self, X, y, **kwargs):
        self.fitted = True


def _make_dummy_dataset() -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=12, freq="W-MON"),
            "tv": [100.0] * 12,
            "social": [200.0] * 12,
            "search": [150.0] * 12,
            "sales": [1000.0] * 12,
        }
    )
    config = {
        "date_column": "date",
        "target_column": "sales",
        "channel_columns": ["tv", "social", "search"],
        "adstock": {"type": "geometric", "l_max": 8},
        "saturation": {"type": "logistic"},
        "sampler": {"draws": 50, "tune": 50, "chains": 2},
    }
    return df, config


def test_prior_sensitivity_evaluates_adstock_and_saturation_dimensions():
    """Verify contract fidelity: tested_dimensions contains both adstock and saturation."""
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.MMM = ControllableFakeMMM

    call_count = 0

    def mock_channel_contributions(model):
        nonlocal call_count
        call_count += 1
        # Baseline order: social (0), search (1), tv (2)
        if call_count == 1:
            return {
                "channels": [
                    {"channel": "social", "contribution_median": 500.0},
                    {"channel": "search", "contribution_median": 300.0},
                    {"channel": "tv", "contribution_median": 100.0},
                ]
            }
        # Alternative 1 (shorter_memory): same order
        elif call_count == 2:
            return {
                "channels": [
                    {"channel": "social", "contribution_median": 480.0},
                    {"channel": "search", "contribution_median": 310.0},
                    {"channel": "tv", "contribution_median": 110.0},
                ]
            }
        # Alternative 2 (alternative_type): small shift
        elif call_count == 3:
            return {
                "channels": [
                    {"channel": "social", "contribution_median": 450.0},
                    {"channel": "search", "contribution_median": 350.0},
                    {"channel": "tv", "contribution_median": 90.0},
                ]
            }
        # Alternative 3 (alternative_saturation): inverted order (tv shifts by 2)
        else:
            return {
                "channels": [
                    {"channel": "tv", "contribution_median": 600.0},
                    {"channel": "social", "contribution_median": 300.0},
                    {"channel": "search", "contribution_median": 200.0},
                ]
            }

    adapter.channel_contributions = mock_channel_contributions

    df, config = _make_dummy_dataset()
    base_model = ControllableFakeMMM()

    res = adapter.evaluate_prior_sensitivity(base_model, df, config)

    assert res["tested_dimensions"] == {"adstock": True, "saturation": True}
    assert len(res["alternatives"]) == 3

    # Check dimensions
    dimensions = [alt["dimension"] for alt in res["alternatives"]]
    assert "adstock" in dimensions
    assert "saturation" in dimensions

    # Check scenario_config fidelity
    for alt in res["alternatives"]:
        assert "scenario_config" in alt
        assert "adstock" in alt["scenario_config"]
        assert "saturation" in alt["scenario_config"]
        assert "ranks" in alt
        assert alt["ranks"] is not None

    # Check finding generation and prior_stability
    assert res["max_rank_shift"] >= 2
    assert res["prior_stability"] == "sensitive"
    assert len(res["findings"]) > 0
    assert any(f["code"] == "HIGH_PRIOR_SENSITIVITY" for f in res["findings"])


def test_prior_sensitivity_robust_when_rankings_stable():
    """Verify prior_stability is robust when rank shifts are under threshold."""
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.MMM = ControllableFakeMMM

    def mock_channel_contributions(model):
        return {
            "channels": [
                {"channel": "social", "contribution_median": 500.0},
                {"channel": "search", "contribution_median": 300.0},
                {"channel": "tv", "contribution_median": 100.0},
            ]
        }

    adapter.channel_contributions = mock_channel_contributions

    df, config = _make_dummy_dataset()
    base_model = ControllableFakeMMM()

    res = adapter.evaluate_prior_sensitivity(base_model, df, config)

    assert res["max_rank_shift"] == 0
    assert res["prior_stability"] == "robust"
    assert len(res["findings"]) == 0


def test_prior_sensitivity_records_alternative_failure_without_aborting():
    """Verify that if one alternative refit fails, error is captured and others continue."""
    adapter = object.__new__(PyMCMarketingAdapter)

    class FailingMMM(ControllableFakeMMM):
        def fit(self, X, y, **kwargs):
            if kwargs.get("chains") == 2:
                raise RuntimeError("Fitting failed on alternative prior")
            super().fit(X, y, **kwargs)

    adapter.MMM = FailingMMM
    adapter.channel_contributions = lambda model: {
        "channels": [{"channel": "tv", "contribution_median": 100.0}]
    }

    df, config = _make_dummy_dataset()
    base_model = ControllableFakeMMM()

    res = adapter.evaluate_prior_sensitivity(base_model, df, config)

    assert res["tested_dimensions"] == {"adstock": True, "saturation": True}
    assert len(res["alternatives"]) == 3
    # All alternatives failed because FakeMMM throws
    for alt in res["alternatives"]:
        assert alt["ranks"] is None
        assert "error" in alt
        assert "Fitting failed on alternative prior" in alt["error"]
