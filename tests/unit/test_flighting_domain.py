"""
Unit tests for Phase 4 — Dynamic Multi-Period Flighting domain and calculations.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marketing_mcp.domain.decisions.flighting import (
    apply_spend_pattern,
    build_weekly_schedule,
    check_extrapolation_risk,
    compute_net_profit,
)
from marketing_mcp.schemas.models import (
    FlightingOptimizationInput,
    WeeklyFlightingConstraint,
)


class TestFlightingDomain:
    def test_apply_spend_pattern_flat(self):
        weekly = apply_spend_pattern(1200.0, 12, "flat")
        assert len(weekly) == 12
        assert sum(weekly) == pytest.approx(1200.0)
        assert all(w == pytest.approx(100.0) for w in weekly)

    def test_apply_spend_pattern_frontloaded(self):
        weekly = apply_spend_pattern(1000.0, 4, "frontloaded")
        assert len(weekly) == 4
        assert sum(weekly) == pytest.approx(1000.0)
        assert weekly[0] > weekly[-1]

    def test_apply_spend_pattern_backloaded(self):
        weekly = apply_spend_pattern(1000.0, 4, "backloaded")
        assert len(weekly) == 4
        assert sum(weekly) == pytest.approx(1000.0)
        assert weekly[0] < weekly[-1]

    def test_apply_spend_pattern_pulsed(self):
        weekly = apply_spend_pattern(1000.0, 4, "pulsed")
        assert len(weekly) == 4
        assert sum(weekly) == pytest.approx(1000.0)
        assert weekly[0] > weekly[1]

    def test_build_weekly_schedule_sum(self):
        channels = ["meta", "google"]
        constraints = [
            {"channel": "meta", "pattern": "frontloaded"},
            {"channel": "google", "pattern": "flat"},
        ]
        schedule = build_weekly_schedule(channels, 2000.0, 10, constraints)
        assert "meta" in schedule
        assert "google" in schedule
        total = sum(sum(weeks) for weeks in schedule.values())
        assert total == pytest.approx(2000.0)

    def test_compute_net_profit(self):
        res = compute_net_profit(total_response=10000.0, total_spend=5000.0, margin_pct=0.8)
        assert res["gross_revenue"] == 10000.0
        assert res["total_spend"] == 5000.0
        assert res["margin_pct"] == 0.8
        assert res["margin_revenue"] == 8000.0
        assert res["net_profit"] == 3000.0
        assert res["roas"] == 2.0
        assert res["is_profitable"] is True

    def test_check_extrapolation_risk_triggers(self):
        schedule = {"meta": [100.0, 250.0, 100.0]}
        p95 = {"meta": 100.0}
        warnings = check_extrapolation_risk(schedule, p95, multiplier=1.5)
        assert len(warnings) == 1
        assert warnings[0]["week"] == 2
        assert warnings[0]["code"] == "EXTRAPOLATION_RISK"


class TestFlightingSchemas:
    def test_flighting_input_validation(self):
        inp = FlightingOptimizationInput(
            model_id="mmm_123",
            total_budget=50000.0,
            planning_weeks=12,
            target_iroas_min=2.5,
            margin_pct=0.6,
            channel_constraints=[WeeklyFlightingConstraint(channel="meta", pattern="frontloaded")],
            objective="maximize_net_profit",
        )
        assert inp.total_budget == 50000.0
        assert inp.planning_weeks == 12

    def test_flighting_input_rejects_negative_budget(self):
        with pytest.raises(ValidationError):
            FlightingOptimizationInput(model_id="mmm_123", total_budget=-100.0)
