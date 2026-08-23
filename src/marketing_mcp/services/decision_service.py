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
            optimize_flighting_schedule,
        )

        p95_map = {}
        if hasattr(model, "X") and hasattr(model.X, "columns"):
            for ch in model.channel_columns:
                if ch in model.X:
                    p95_map[ch] = float(np.percentile(model.X[ch], 95))

        channel_params = {}
        if hasattr(model, "fit_result") and hasattr(model.fit_result, "data_vars"):
            post = model.fit_result
            channels = getattr(model, "channel_columns", [])
            for ch in channels:
                p = {}
                if "adstock_alpha" in post:
                    try:
                        p["alpha"] = float(post["adstock_alpha"].sel(channel=ch).mean())
                    except (KeyError, ValueError, TypeError, AttributeError):
                        pass
                if "saturation_beta" in post:
                    try:
                        p["beta"] = float(post["saturation_beta"].sel(channel=ch).mean())
                    except (KeyError, ValueError, TypeError, AttributeError):
                        pass
                if "saturation_lam" in post:
                    try:
                        p["lam"] = float(post["saturation_lam"].sel(channel=ch).mean())
                    except (KeyError, ValueError, TypeError, AttributeError):
                        pass
                if p:
                    channel_params[ch] = p

        constraints_dicts = [c.model_dump() for c in input.channel_constraints]
        flighting_res = optimize_flighting_schedule(
            channel_columns=model.channel_columns,
            total_budget=input.total_budget,
            planning_weeks=input.planning_weeks,
            channel_constraints=constraints_dicts,
            objective=input.objective,
            target_iroas_min=input.target_iroas_min,
            margin_pct=input.margin_pct,
            channel_parameters=channel_params if channel_params else None,
            historical_channel_p95=p95_map,
        )

        total_channel_spend = flighting_res["total_channel_spend"]
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

        scenario_id = f"flighting_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "flighting",
            "input": input.model_dump(),
            "weekly_schedule": flighting_res["weekly_schedule"],
            "total_spend": flighting_res["allocated_budget"],
            "net_profit": flighting_res["net_profit"],
            "sim_result": sim_res,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)

        return {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "solver_status": flighting_res["solver_status"],
            "planning_weeks": input.planning_weeks,
            "weekly_schedule": flighting_res["weekly_schedule"],
            "total_budget": input.total_budget,
            "allocated_budget": flighting_res["allocated_budget"],
            "budget_residual": flighting_res["budget_residual"],
            "total_channel_spend": total_channel_spend,
            "net_profit": flighting_res["net_profit"],
            "posterior_response": sim_res["scenario_response"],
            "comparison_to_historical": sim_res["comparison"],
            "warnings": flighting_res["warnings"],
            "provenance": self._provenance(input.model_id, record),
        }
