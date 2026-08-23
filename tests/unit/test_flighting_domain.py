"""Unit tests for Phase 4 — Dynamic Multi-Period Flighting domain and calculations.

Task 5 contract:
1. True channel-by-week optimization with carryover and saturation.
2. Strict budget conservation.
3. Infeasible constraint rejection (min > max, sum(min) > budget, sum(max) < budget, unachievable target ROAS).
4. Objective choice changes allocation.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from marketing_mcp.domain.decisions.flighting import (
    apply_spend_pattern,
    build_weekly_schedule,
    check_extrapolation_risk,
    compute_net_profit,
    evaluate_carryover_response,
    optimize_flighting_schedule,
)
from marketing_mcp.errors import DomainError
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

    def test_evaluate_carryover_response(self):
        spend_matrix = np.array([[100.0, 100.0, 100.0], [50.0, 50.0, 50.0]])
        params = [
            {"alpha": 0.5, "beta": 10.0, "lam": 100.0},
            {"alpha": 0.2, "beta": 5.0, "lam": 50.0},
        ]
        resp = evaluate_carryover_response(spend_matrix, params)
        assert resp > 0

    def test_optimize_flighting_strict_budget_conservation(self):
        channels = ["meta", "google", "tv"]
        constraints = [
            {"channel": "meta", "min_weekly": 50.0, "max_weekly": 300.0, "pattern": "frontloaded"},
            {"channel": "google", "min_weekly": 20.0, "max_weekly": 200.0, "pattern": "flat"},
            {"channel": "tv", "min_weekly": 100.0, "pattern": "pulsed"},
        ]
        res = optimize_flighting_schedule(
            channel_columns=channels,
            total_budget=5000.0,
            planning_weeks=8,
            channel_constraints=constraints,
            objective="maximize_response",
        )
        assert res["solver_status"] in ("success", "converged")
        assert res["allocated_budget"] == pytest.approx(5000.0, abs=1.0)
        assert res["budget_residual"] <= 1.0
        total_sum = sum(sum(weeks) for weeks in res["weekly_schedule"].values())
        assert total_sum == pytest.approx(5000.0, abs=1.0)

    def test_optimize_flighting_infeasible_min_greater_than_max(self):
        channels = ["meta"]
        constraints = [{"channel": "meta", "min_weekly": 500.0, "max_weekly": 100.0}]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=channels,
                total_budget=1000.0,
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_optimize_flighting_infeasible_sum_min_exceeds_budget(self):
        channels = ["meta", "google"]
        # Min sum = (300 + 300) * 4 weeks = 2400 > budget (2000)
        constraints = [
            {"channel": "meta", "min_weekly": 300.0},
            {"channel": "google", "min_weekly": 300.0},
        ]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=channels,
                total_budget=2000.0,
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_optimize_flighting_infeasible_sum_max_below_budget(self):
        channels = ["meta", "google"]
        # Max sum = (100 + 100) * 4 weeks = 800 < budget (2000)
        constraints = [
            {"channel": "meta", "max_weekly": 100.0},
            {"channel": "google", "max_weekly": 100.0},
        ]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=channels,
                total_budget=2000.0,
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_optimize_flighting_infeasible_unachievable_target_roas(self):
        channels = ["meta"]
        # Target ROAS of 1000.0 is impossible with standard saturation
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=channels,
                total_budget=2000.0,
                planning_weeks=4,
                target_iroas_min=1000.0,
                channel_parameters={"meta": {"alpha": 0.1, "beta": 1.0, "lam": 500.0}},
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_objective_changes_allocation_on_asymmetric_surface(self):
        channels = ["meta", "google"]
        # meta has high margin response, google has low
        params = {
            "meta": {"alpha": 0.7, "beta": 200.0, "lam": 500.0},
            "google": {"alpha": 0.1, "beta": 10.0, "lam": 100.0},
        }
        res_resp = optimize_flighting_schedule(
            channel_columns=channels,
            total_budget=2000.0,
            planning_weeks=4,
            objective="maximize_response",
            channel_parameters=params,
        )
        res_profit = optimize_flighting_schedule(
            channel_columns=channels,
            total_budget=2000.0,
            planning_weeks=4,
            objective="maximize_net_profit",
            margin_pct=0.2,
            channel_parameters=params,
        )
        # Optimal schedules allocate different amounts depending on the objective
        assert res_resp["weekly_schedule"]["meta"] != res_profit["weekly_schedule"]["meta"]

    def test_legacy_build_weekly_schedule_wrapper(self):
        channels = ["meta", "google"]
        constraints = [
            {"channel": "meta", "pattern": "frontloaded"},
            {"channel": "google", "pattern": "flat"},
        ]
        schedule = build_weekly_schedule(channels, 2000.0, 10, constraints)
        assert "meta" in schedule
        assert "google" in schedule
        total = sum(sum(weeks) for weeks in schedule.values())
        assert total == pytest.approx(2000.0, abs=1.0)

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
