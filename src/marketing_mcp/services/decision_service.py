from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

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
                f"Model '{model_id}' has not been diagnosed yet. Run diagnose_mmm before using decision tools.",
                evidence={"model_id": model_id, "validation_state": record.validation_state},
                next_action=f"Call diagnose_mmm(model_id='{model_id}') to run MCMC convergence diagnostics.",
            )
        DecisionGate(
            record.validation_state,
            record.diagnostics.get("failures", []),
        ).require_decision_access()
        model, _ = self.modeling.load_model(model_id)
        return model, record

    @staticmethod
    def _gate_payload(record) -> dict:
        """Explicit gate context attached to every model-consuming tool result.

        Descriptive tools run on rejected models so users can inspect the
        evidence behind a rejection; the payload labels those numbers as
        coming from a rejected model so they cannot be treated as
        decision-grade.
        """
        diagnostics = record.diagnostics or {}
        status = record.validation_state or "not_diagnosed"
        payload: dict = {
            "decision_status": status,
            "diagnostic_warnings": list(diagnostics.get("warnings") or []),
        }
        if status == "rejected":
            payload["diagnostic_failures"] = list(diagnostics.get("failures") or [])
        return payload

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
        result["decision_gate"] = self._gate_payload(record)
        result["provenance"] = self._provenance(model_id, record)
        return result

    def iroas(self, model_id):
        # iROAS drives budget reallocation, so it is decision-grade and must
        # pass the full diagnostics gate like simulate/optimize/flighting.
        model, record = self._approved(model_id)
        result = self.modeling.adapter_factory().incremental_roas(model)
        result.update(
            {
                "model_id": model_id,
                "decision_gate": self._gate_payload(record),
                "provenance": self._provenance(model_id, record),
            }
        )
        return result

    def response_curves(self, model_id):
        model, record = self.modeling.load_model(model_id)
        result = self.modeling.adapter_factory().response_curves(model)

        # Connect native LTTB compression and sparkline for AI client context efficiency
        from marketing_mcp.accelerators import compress_curve_lttb, generate_sparkline
        channel_curves = result.get("channel_curves") or result.get("curves") or {}
        for ch_data in channel_curves.values():
            if isinstance(ch_data, dict):
                spends = ch_data.get("spend_grid")
                medians = ch_data.get("median_response")
                if spends and medians and len(spends) > 30:
                    down_x, down_y = compress_curve_lttb(spends, medians, max_points=30)
                    ch_data["transport_curve"] = {
                        "spend": down_x,
                        "median_response": down_y,
                        "downsampled_points": len(down_x),
                        "algorithm": "lttb",
                    }
                if medians:
                    ch_data["sparkline"] = generate_sparkline(medians)

        result.update(
            {
                "model_id": model_id,
                "decision_gate": self._gate_payload(record),
                "provenance": self._provenance(model_id, record),
            }
        )
        return result

    def _collect_channel_identifiability_warnings(
        self,
        record,
        recommended_allocation: dict[str, float] | None,
        baseline_allocation: dict[str, float] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Check allocated channels against upstream dataset validation findings.

        Carries forward identifiability warnings (e.g. LONG_ZERO_SPEND_RUN,
        EXTREME_OUTLIERS, HIGH_CHANNEL_CORRELATION) into budget decisions
        so agents and users are not misled by high-confidence reallocations
        into channels with sparse or unidentifiable history.
        """
        warnings: list[dict[str, Any]] = []
        channel_confidence: dict[str, str] = {}

        if not recommended_allocation:
            return warnings, channel_confidence

        dataset_id = getattr(record, "dataset_id", None)
        cfg = getattr(record, "config", {}) or {}
        date_col = cfg.get("date_column")
        target_col = cfg.get("target_column")
        channels = cfg.get("channel_columns", [])
        controls = cfg.get("control_columns", [])
        dims = cfg.get("dims", [])

        if not (dataset_id and date_col and target_col and channels):
            return warnings, channel_confidence

        try:
            val_res = self.modeling.datasets.validate(
                dataset_id=dataset_id,
                date_column=date_col,
                target_column=target_col,
                channel_columns=channels,
                control_columns=controls,
                dims=dims,
            )
            findings = val_res.findings
        except Exception:
            findings = []

        channel_findings: dict[str, list[Any]] = {}
        for f in findings:
            ev = f.evidence if isinstance(f.evidence, dict) else {}
            col = ev.get("column")
            if col:
                channel_findings.setdefault(col, []).append(f)
            corr_channels = ev.get("channels")
            if corr_channels and isinstance(corr_channels, list):
                for c in corr_channels:
                    channel_findings.setdefault(c, []).append(f)

        for ch, rec_spend in recommended_allocation.items():
            base_spend = (baseline_allocation or {}).get(ch, 0.0)
            ch_warns = channel_findings.get(ch, [])

            if ch_warns:
                zero_run = any(f.code == "LONG_ZERO_SPEND_RUN" for f in ch_warns)
                outliers = any(f.code == "EXTREME_OUTLIERS" for f in ch_warns)
                confidence = (
                    "low_sparse_history"
                    if zero_run
                    else ("medium_outliers" if outliers else "medium_correlated")
                )
                channel_confidence[ch] = confidence

                for f in ch_warns:
                    msg = (
                        f"Channel '{ch}' was allocated ${rec_spend:,.2f} "
                        f"(vs baseline ${base_spend:,.2f}), but the model input has dataset warning: "
                        f"{f.code} - {f.message}. Reallocations to channels with sparse data "
                        f"carry high estimation uncertainty."
                    )
                    warnings.append(
                        {
                            "code": "IDENTIFIABILITY_RISK",
                            "channel": ch,
                            "severity": "high" if (zero_run and rec_spend > 0) else "medium",
                            "message": msg,
                            "dataset_finding": {
                                "code": f.code,
                                "evidence": f.evidence,
                                "next_action": getattr(
                                    f, "suggested_action", getattr(f, "next_action", None)
                                ),
                            },
                            "next_action": "Validate channel response with incrementality/lift tests before committing budget.",
                        }
                    )
            else:
                channel_confidence[ch] = "high"

        return warnings, channel_confidence

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
        if result.get("optimizer_success") is not True:
            raise DomainError(
                "OPTIMIZATION_FAILED",
                "Budget optimizer failed to produce a trustworthy allocation",
                evidence={
                    "optimizer_message": str(result.get("optimizer_message", ""))[:500],
                    "optimizer_success": result.get("optimizer_success"),
                },
                next_action="Review budget bounds and optimizer convergence diagnostics",
            )
        allocation = result.get("recommended_allocation")
        if allocation is None:
            raise DomainError(
                "OPTIMIZATION_RESULT_INCOMPLETE",
                "Optimizer did not return a recommended allocation",
                evidence={"keys": sorted(result)},
            )
        baseline = result.get("baseline_allocation")
        if baseline is None:
            try:
                baseline = historical_allocation(model, input.planning_periods)
            except Exception:
                baseline = {}

        extrap_warnings = check_extrapolation_risk(
            model,
            allocation,
            input.planning_periods,
        )
        ident_warnings, channel_conf = self._collect_channel_identifiability_warnings(
            record,
            allocation,
            baseline,
        )
        combined_warnings = extrap_warnings + ident_warnings

        scenario_id = f"scenario_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "optimization",
            "input": input.model_dump(),
            "result": result,
            "extrapolation_warnings": extrap_warnings,
            "identifiability_warnings": ident_warnings,
            "channel_confidence": channel_conf,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)
        result.update(
            {
                "scenario_id": scenario_id,
                "model_id": input.model_id,
                "warnings": combined_warnings,
                "identifiability_warnings": ident_warnings,
                "identifiability_risks": ident_warnings,
                "channel_confidence": channel_conf,
                "decision_gate": self._gate_payload(record),
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
        ident_warnings, channel_conf = self._collect_channel_identifiability_warnings(
            record,
            scenario,
            baseline,
        )
        combined_warnings = extrap_warnings + ident_warnings

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
            "identifiability_warnings": ident_warnings,
            "channel_confidence": channel_conf,
            "created_at": _utc(),
        }
        self.metadata.put_scenario(payload)

        caveats = [
            "Scenario evaluation is conditional on the fitted MMM and its posterior uncertainty."
        ] + [w["message"] for w in ident_warnings]

        return {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "baseline_allocation": baseline,
            "scenario_allocation": scenario,
            **posterior_result,
            "warnings": combined_warnings,
            "identifiability_warnings": ident_warnings,
            "identifiability_risks": ident_warnings,
            "channel_confidence": channel_conf,
            "decision_gate": self._gate_payload(record),
            "caveats": caveats,
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

        from marketing_mcp.adapters.mmm_config import ADSTOCK_MAP, SATURATION_MAP
        from marketing_mcp.domain.decisions.flighting import (
            build_official_response_evaluator,
            optimize_flighting_schedule,
        )

        p95_map = {}
        if hasattr(model, "X") and hasattr(model.X, "columns"):
            for ch in model.channel_columns:
                if ch in model.X:
                    p95_map[ch] = float(np.percentile(model.X[ch], 95))

        channels = list(getattr(model, "channel_columns", []) or [])

        # Resolve the model's actual transform families from the fitted instance.
        adstock_instance = getattr(model, "adstock", None)
        saturation_instance = getattr(model, "saturation", None)

        def _type_name(instance, mapping):
            if instance is None:
                return None
            for name, cls in mapping.items():
                if cls is not None and isinstance(instance, cls):
                    return name
            return None

        adstock_type = _type_name(adstock_instance, ADSTOCK_MAP)
        saturation_type = _type_name(saturation_instance, SATURATION_MAP)
        l_max = int(getattr(adstock_instance, "l_max", 4) or 4)

        # Training-time channel scaling: posterior parameters live in scaled space.
        channel_scale: dict[str, float] | None = None
        try:
            scales = model.get_scales_as_xarray()
            scales_da = scales["channel_scale"]
            channel_scale = {}
            for ch in channels:
                if "channel" in scales_da.dims:
                    channel_scale[ch] = float(
                        np.asarray(scales_da.sel(channel=ch)).reshape(-1).mean()
                    )
                else:
                    channel_scale[ch] = float(np.asarray(scales_da).reshape(-1).mean())
        except (AttributeError, KeyError, ValueError, TypeError):
            channel_scale = None

        # Family-correct posterior means keyed by full posterior variable name.
        channel_params: dict[str, dict[str, float]] = {ch: {} for ch in channels}
        post = getattr(model, "fit_result", None)
        data_vars = getattr(post, "data_vars", None)
        if data_vars is not None:
            for var in data_vars:
                if not var.startswith(("adstock_", "saturation_")):
                    continue
                da = post[var]
                has_channel_dim = "channel" in da.dims
                for ch in channels:
                    vals = da.sel(channel=ch) if has_channel_dim else da
                    try:
                        channel_params[ch][var] = float(
                            np.asarray(vals, dtype=float).reshape(-1).mean()
                        )
                    except (KeyError, ValueError, TypeError):
                        continue

        response_evaluator = None
        if adstock_type is None or saturation_type is None:
            raise DomainError(
                "INPUT_INVALID",
                "Model transform families are not supported for flighting optimization; "
                "refusing to approximate with a generic response surface",
                evidence={
                    "adstock_class": type(adstock_instance).__name__ if adstock_instance else None,
                    "saturation_class": type(saturation_instance).__name__
                    if saturation_instance
                    else None,
                },
                next_action="Refit the model using a supported adstock/saturation family",
            )
        response_evaluator = build_official_response_evaluator(
            adstock_type=adstock_type,
            saturation_type=saturation_type,
            l_max=l_max,
            channel_params=channel_params,
            channel_scale=channel_scale,
            channel_columns=channels,
        )

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
            response_evaluator=response_evaluator,
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
            "decision_gate": self._gate_payload(record),
            "provenance": self._provenance(input.model_id, record),
        }
