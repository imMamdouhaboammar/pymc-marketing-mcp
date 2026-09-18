"""Unit and adversarial tests for structural breaks, target leakage, and control variance diagnostics (T3)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.intelligence.contracts.issues import IssueCode
from marketing_mcp.intelligence.statistical.break_detection import detect_structural_breaks
from marketing_mcp.intelligence.statistical.control_variance import assess_control_variance
from marketing_mcp.intelligence.statistical.target_leakage import check_target_leakage


class TestStructuralBreakDetection:
    def test_detects_obvious_regime_shift(self):
        # 30 periods at mean 100, then 30 periods at mean 300 (massive break)
        dates = pd.date_range("2024-01-01", periods=60, freq="W-MON")
        target_vals = np.concatenate([
            np.random.normal(100.0, 5.0, 30),
            np.random.normal(300.0, 5.0, 30),
        ])
        df = pd.DataFrame({"date": dates, "revenue": target_vals})

        issues = detect_structural_breaks(df, date_column="date", target_column="revenue")
        assert len(issues) == 1
        issue = issues[0]
        assert issue.code == IssueCode.STRUCTURAL_BREAK
        assert "revenue" in issue.affected_columns
        assert issue.blocking is False
        assert issue.evidence["break_index"] == pytest.approx(30, abs=3)

    def test_clean_stationary_series_has_no_break(self):
        # Stationary random walk / normal series with constant mean
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=60, freq="W-MON")
        target_vals = np.random.normal(100.0, 10.0, 60)
        df = pd.DataFrame({"date": dates, "revenue": target_vals})

        issues = detect_structural_breaks(df, date_column="date", target_column="revenue")
        assert len(issues) == 0

    def test_short_series_skips_gracefully(self):
        df = pd.DataFrame({"date": ["2024-01-01", "2024-01-08"], "revenue": [10.0, 20.0]})
        issues = detect_structural_breaks(df, date_column="date", target_column="revenue")
        assert len(issues) == 0


class TestTargetLeakageDetection:
    def test_detects_direct_target_proxy_leakage(self):
        dates = pd.date_range("2024-01-01", periods=40, freq="W-MON")
        revenue = np.random.uniform(500, 1500, 40)
        # total_orders perfectly mirrors revenue (r ~ 0.999)
        total_orders = revenue * 0.1 + np.random.normal(0, 0.5, 40)
        df = pd.DataFrame({
            "date": dates,
            "revenue": revenue,
            "total_orders": total_orders,
            "cpi": np.random.normal(100, 2, 40),
        })

        issues = check_target_leakage(
            df,
            target_column="revenue",
            candidate_controls=["total_orders", "cpi"],
        )
        assert len(issues) == 1
        issue = issues[0]
        assert issue.code == IssueCode.TARGET_LEAKAGE
        assert issue.evidence["control_column"] == "total_orders"
        assert issue.severity.value == "high"

    def test_clean_independent_controls_produce_no_leakage(self):
        dates = pd.date_range("2024-01-01", periods=40, freq="W-MON")
        df = pd.DataFrame({
            "date": dates,
            "revenue": np.random.uniform(500, 1500, 40),
            "unemployment_rate": np.random.uniform(3.5, 4.5, 40),
            "temperature": np.random.uniform(10, 30, 40),
        })
        issues = check_target_leakage(
            df,
            target_column="revenue",
            candidate_controls=["unemployment_rate", "temperature"],
        )
        assert len(issues) == 0


class TestControlVarianceAssessment:
    def test_detects_constant_and_near_constant_controls(self):
        df = pd.DataFrame({
            "constant_ctrl": [1.0] * 50,
            "near_constant_ctrl": [0.0] * 49 + [1.0],  # 98% constant
            "good_ctrl": np.random.normal(50, 10, 50),
        })

        issues = assess_control_variance(df, ["constant_ctrl", "near_constant_ctrl", "good_ctrl"])
        flagged_cols = [iss.affected_columns[0] for iss in issues]
        assert "constant_ctrl" in flagged_cols
        assert "near_constant_ctrl" in flagged_cols
        assert "good_ctrl" not in flagged_cols

        for iss in issues:
            assert iss.code == IssueCode.CONTROL_NEAR_ZERO_VARIANCE
            assert iss.blocking is False

    def test_clean_controls_produce_no_variance_issues(self):
        df = pd.DataFrame({
            "gdp_growth": np.random.normal(2.0, 0.5, 40),
            "competitor_price": np.random.uniform(20, 50, 40),
        })
        issues = assess_control_variance(df, ["gdp_growth", "competitor_price"])
        assert len(issues) == 0
