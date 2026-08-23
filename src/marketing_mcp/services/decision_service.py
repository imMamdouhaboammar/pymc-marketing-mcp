from __future__ import annotations

import uuid
from datetime import UTC, datetime

from marketing_mcp.domain.decisions.allocation import (
    apply_changes,
    check_extrapolation_risk,
    historical_allocation,
)
from marketing_mcp.domain.diagnostics.gate import DecisionGate
from marketing_mcp.errors import DomainError


def _utc() -> str:
    return datetime.now(UTC).isoformat()


class DecisionService:
    def __init__(self, metadata, modeling):
        self.metadata = metadata
        self.modeling = modeling

    def _approved(self, model_id):
        record = self.modeling.status(model_id)
        if not record.diagnostics:
            raise DomainError(
                "MODEL_NOT_DIAGNOSED",
                "Run diagnose_mmm before using decision tools",
            )
        DecisionGate(
            record.validation_state,
            record.diagnostics.get("failures", []),
        ).require_decision_access()
        model, _ = self.modeling.load_model(model_id)
        return model, record

    @staticmethod
    def _provenance(model_id, record) -> dict:
        return {
            "model_id": model_id,
            "dataset_id": record.dataset_id,
            "lineage_stage": getattr(record, "lineage_stage", "initial_fit"),
            "parent_model_id": getattr(record, "parent_model_id", None),
            "versions": record.config.get("provenance", {}),
        }

    def contributions(self, model_id):
        model, record = self.modeling.load_model(model_id)
        result = self.modeling.adapter_factory().channel_contributions(model)
        result["model_id"] = model_id
        result["provenance"] = self._provenance(model_id, record)
        return result

    def iroas(self, model_id):
        model, record = self.modeling.load_model(model_id)
        result = self.modeling.adapter_factory().incremental_roas(model)
        result.update(
            {
                "model_id": model_id,
                "provenance": self._provenance(model_id, record),
            }
        )
        return result

    def response_curves(self, model_id):
        model, record = self.modeling.load_model(model_id)
        result = self.modeling.adapter_factory().response_curves(model)
        result.update(
            {
                "model_id": model_id,
                "provenance": self._provenance(model_id, record),
            }
        )
        return result

    def optimize(self, input):
        model, record = self._approved(input.model_id)
        result = self.modeling.adapter_factory().optimize_budget(
            model,
            input.budget,
            input.planning_periods,
            {
                channel: constraint.model_dump(exclude_none=True)
                for channel, constraint in input.constraints.items()
            },
            [constraint.model_dump(exclude_none=True) for constraint in input.cell_constraints],
        )
        allocation = result.get("recommended_allocation")
        if allocation is None:
            raise DomainError(
                "OPTIMIZATION_RESULT_INCOMPLETE",
                "Optimizer did not return a recommended allocation",
                evidence={"keys": sorted(result)},
            )
        extrap_warnings = check_extrapolation_risk(
            model,
            allocation,
            input.planning_periods,
        )
        scenario_id = f"scenario_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "optimization",
            "input": input.model_dump(),
            "result": result,
            "extrapolation_warnings": extrap_warnings,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)
        result.update(
            {
                "scenario_id": scenario_id,
                "model_id": input.model_id,
                "warnings": extrap_warnings,
                "provenance": self._provenance(input.model_id, record),
            }
        )
        return result

    def simulate(self, input):
        model, record = self._approved(input.model_id)
        baseline = historical_allocation(model, input.planning_periods)
        scenario = apply_changes(
            model,
            baseline,
            input.changes,
            input.cell_changes,
        )

        posterior_result = self.modeling.adapter_factory().simulate_budget(
            model,
            baseline,
            scenario,
            input.planning_periods,
        )
        extrap_warnings = check_extrapolation_risk(
            model,
            scenario,
            input.planning_periods,
        )
        scenario_id = f"scenario_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "simulation",
            "input": input.model_dump(),
            "baseline_allocation": baseline,
            "scenario_allocation": scenario,
            "result": posterior_result,
            "extrapolation_warnings": extrap_warnings,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)

        return {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "baseline_allocation": baseline,
            "scenario_allocation": scenario,
            **posterior_result,
            "warnings": extrap_warnings,
            "caveats": [
                "Scenario evaluation is conditional on the fitted MMM and its posterior uncertainty."
            ],
            "provenance": self._provenance(input.model_id, record),
        }

    def recommend_measurement(self, model_id):
        record = self.modeling.status(model_id)
        warnings = (record.diagnostics or {}).get("warnings", [])
        validation = self.modeling.datasets.validate(
            record.dataset_id,
            record.config["date_column"],
            record.config["target_column"],
            record.config["channel_columns"],
            record.config.get("control_columns", []),
            record.config.get("dims", []),
        )
        findings = []
        for finding in validation.findings:
            if finding.code == "HIGH_CHANNEL_CORRELATION":
                findings.append(
                    {
                        "finding": "CHANNEL_EFFECTS_HARD_TO_SEPARATE",
                        "channels": finding.evidence.get("channels", []),
                        "reason": finding.message,
                        "recommended_measurement": "geo_lift_experiment_or_channel_holdout",
                        "priority": "high",
                    }
                )
        for warning in warnings:
            if warning.get("code") == "LOW_EFFECTIVE_SAMPLE_SIZE":
                findings.append(
                    {
                        "finding": "POSTERIOR_UNCERTAINTY_HIGH",
                        "reason": warning.get("message"),
                        "recommended_measurement": "more_history_or_model_revision",
                        "priority": "medium",
                    }
                )
        if not findings:
            findings.append(
                {
                    "finding": "NO_SINGLE_MEASUREMENT_IMPLIED",
                    "reason": (
                        "Current validation signals do not justify prescribing "
                        "one specific experiment"
                    ),
                    "recommended_measurement": "review_business_risk_and_experiment_feasibility",
                    "priority": "low",
                }
            )
        return {"model_id": model_id, "recommendations": findings}

    def optimize_flighting(self, input):
        model, record = self._approved(input.model_id)
        import numpy as np

        from marketing_mcp.domain.decisions.flighting import (
            build_weekly_schedule,
            compute_net_profit,
        )
        from marketing_mcp.domain.decisions.flighting import (
            check_extrapolation_risk as check_flighting_extrapolation_risk,
        )

        constraints_dicts = [c.model_dump() for c in input.channel_constraints]
        weekly_schedule = build_weekly_schedule(
            model.channel_columns,
            input.total_budget,
            input.planning_weeks,
            constraints_dicts,
        )

        total_channel_spend = {ch: sum(spends) for ch, spends in weekly_schedule.items()}
        baseline_channel_spend = historical_allocation(
            model,
            input.planning_weeks,
            total_budget=input.total_budget,
        )

        sim_res = self.modeling.adapter_factory().simulate_budget(
            model,
            baseline_allocation=baseline_channel_spend,
            scenario_allocation=total_channel_spend,
            planning_periods=input.planning_weeks,
        )

        scenario_resp_median = sim_res["scenario_response"]["median"]
        net_profit_info = compute_net_profit(
            total_response=scenario_resp_median,
            total_spend=input.total_budget,
            margin_pct=input.margin_pct,
        )

        p95_map = {}
        if hasattr(model, "X") and hasattr(model.X, "columns"):
            for ch in model.channel_columns:
                if ch in model.X:
                    p95_map[ch] = float(np.percentile(model.X[ch], 95))
        extrap_warnings = check_flighting_extrapolation_risk(weekly_schedule, p95_map)

        if input.target_iroas_min is not None:
            achieved_roas = net_profit_info["roas"]
            if achieved_roas < input.target_iroas_min:
                extrap_warnings.append(
                    {
                        "code": "TARGET_ROAS_UNMET",
                        "severity": "warning",
                        "target_iroas_min": input.target_iroas_min,
                        "achieved_roas": achieved_roas,
                        "message": f"Achieved ROAS ({achieved_roas}) is below the required target ({input.target_iroas_min}).",
                    }
                )

        scenario_id = f"flighting_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "flighting",
            "input": input.model_dump(),
            "weekly_schedule": weekly_schedule,
            "total_spend": input.total_budget,
            "net_profit": net_profit_info,
            "sim_result": sim_res,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)

        return {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "planning_weeks": input.planning_weeks,
            "weekly_schedule": weekly_schedule,
            "total_budget": input.total_budget,
            "total_channel_spend": total_channel_spend,
            "net_profit": net_profit_info,
            "posterior_response": sim_res["scenario_response"],
            "comparison_to_historical": sim_res["comparison"],
            "warnings": extrap_warnings,
            "provenance": self._provenance(input.model_id, record),
        }
