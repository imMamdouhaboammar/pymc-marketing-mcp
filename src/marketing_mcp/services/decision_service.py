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

    def _approved(self, model_id, action: str = "optimize_budget", mode: str = "production"):
        record = self.modeling.status(model_id)
        if not record.diagnostics:
            raise DomainError(
                "MODEL_NOT_DIAGNOSED",
                f"Model '{model_id}' has not been diagnosed yet. Run diagnose_mmm before using decision tools.",
                evidence={"model_id": model_id, "validation_state": record.validation_state},
                next_action=f"Call diagnose_mmm(model_id='{model_id}') to run MCMC convergence diagnostics.",
            )
        DecisionGate(
            decision_status=record.validation_state,
            failures=record.diagnostics.get("failures", []),
            model_id=model_id,
            dataset_id=record.dataset_id,
            dataset_fingerprint=getattr(record, "dataset_fingerprint", None),
            mode=mode,
        ).require_decision_access(action=action)

        # Dataset Fingerprint Lineage Verification
        if getattr(record, "dataset_fingerprint", None) and record.dataset_id:
            t_id = getattr(record, "tenant_id", None)
            try:
                current_ds = self.metadata.get_dataset(record.dataset_id, tenant_id=t_id)
                if current_ds and isinstance(current_ds, dict):
                    cur_fp = current_ds.get("fingerprint")
                    if (
                        isinstance(cur_fp, str)
                        and isinstance(record.dataset_fingerprint, str)
                        and cur_fp != record.dataset_fingerprint
                    ):
                        raise DomainError(
                            "DATASET_FINGERPRINT_MISMATCH",
                            f"Underlying dataset '{record.dataset_id}' has mutated since model '{model_id}' was trained. Training fingerprint: {record.dataset_fingerprint[:12]}... vs Current: {cur_fp[:12]}...",
                            evidence={"training_fingerprint": record.dataset_fingerprint, "current_fingerprint": cur_fp},
                            next_action="Refit the MMM model using the updated dataset before running optimizations.",
                        )
            except DomainError as exc:
                if exc.code == "DATASET_FINGERPRINT_MISMATCH":
                    raise

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
        if getattr(record, "config", None) and isinstance(record.config, dict) and "dataset_intelligence" in record.config:
            di = record.config["dataset_intelligence"]
            payload["dataset_quality_status"] = di.get("data_quality_status", "validated")
            payload["identifiability_risk"] = di.get("identifiability_risk", "low")
        return payload

    @staticmethod
    def _provenance(model_id, record) -> dict:
        prov = {
            "model_id": model_id,
            "dataset_id": record.dataset_id,
            "lineage_stage": getattr(record, "lineage_stage", "initial_fit"),
            "parent_model_id": getattr(record, "parent_model_id", None),
            "versions": record.config.get("provenance", {}) if getattr(record, "config", None) else {},
        }
        if getattr(record, "config", None) and isinstance(record.config, dict) and "dataset_intelligence" in record.config:
            prov["dataset_intelligence"] = record.config["dataset_intelligence"]
        return prov

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
        for ch_name, ch_data in channel_curves.items():
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

    @staticmethod
    def _channel_spend_map(allocation: dict[str, Any] | None) -> dict[str, float]:
        """Normalize 1D or multidimensional (cell-based) allocation into channel spend totals."""
        if not allocation or not isinstance(allocation, dict):
            return {}
        if "cells" in allocation and isinstance(allocation["cells"], list):
            totals: dict[str, float] = {}
            for cell in allocation["cells"]:
                if isinstance(cell, dict):
                    ch = cell.get("channel")
                    amt = float(cell.get("amount", 0.0))
                    if ch:
                        totals[ch] = totals.get(ch, 0.0) + amt
            return totals
        return {
            str(k): float(v)
            for k, v in allocation.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }

    def _collect_channel_identifiability_warnings(
        self,
        record,
        recommended_allocation: dict[str, Any] | None,
        baseline_allocation: dict[str, Any] | None,
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

        channel_alloc = self._channel_spend_map(recommended_allocation)
        channel_base = self._channel_spend_map(baseline_allocation)

        for ch, rec_spend in channel_alloc.items():
            base_spend = channel_base.get(ch, 0.0)
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

    @staticmethod
    def _raise_if_cancelled(cancel_event: Any = None, action: str = "Operation") -> None:
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", f"{action} was cancelled by client")

    def optimize(self, input, cancel_event: Any = None):
        self._raise_if_cancelled(cancel_event, "Optimization")
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
        self._raise_if_cancelled(cancel_event, "Optimization")
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

        # Economic explainability and rationale per channel
        channel_iroas: dict[str, float] = {}
        try:
            adapter = self.modeling.adapter_factory()
            if hasattr(adapter, "calculate_iroas"):
                iroas_res = adapter.calculate_iroas(model)
                for ch, stats in iroas_res.items():
                    if isinstance(stats, dict):
                        channel_iroas[ch] = stats.get("mean", 1.0)
            elif hasattr(adapter, "incremental_roas"):
                iroas_res = adapter.incremental_roas(model)
                for ch_data in iroas_res.get("channels", []):
                    ch_name = ch_data.get("channel")
                    m_stat = ch_data.get("marginal_iroas")
                    if ch_name and isinstance(m_stat, dict):
                        channel_iroas[ch_name] = m_stat.get("mean", 1.0)
        except Exception:
            channel_iroas = {}

        rationale: dict[str, Any] = {}
        economic_warnings: list[dict[str, Any]] = []
        channel_alloc = self._channel_spend_map(allocation)
        channel_base = self._channel_spend_map(baseline)
        for ch, spend in channel_alloc.items():
            base_spend = channel_base.get(ch, 0.0)
            spend_change_pct = (
                round(((spend - base_spend) / base_spend) * 100, 2)
                if base_spend > 0
                else None
            )

            constraints_active = []
            ch_constraint = input.constraints.get(ch)
            if ch_constraint:
                if ch_constraint.min is not None and abs(spend - ch_constraint.min) < 1e-2:
                    constraints_active.append("at_min_spend_bound")
                if ch_constraint.max is not None and abs(spend - ch_constraint.max) < 1e-2:
                    constraints_active.append("at_max_spend_bound")
                if ch_constraint.fixed is not None and abs(spend - ch_constraint.fixed) < 1e-2:
                    constraints_active.append("fixed_spend_bound")

            m_iroas = channel_iroas.get(ch)
            if m_iroas is not None and m_iroas < 1.0:
                verdict = "sub_marginal_warning"
                economic_warnings.append(
                    {
                        "code": "ECONOMIC_SUB_MARGINAL_ALLOCATION",
                        "severity": "warning",
                        "channel": ch,
                        "message": (
                            f"Channel '{ch}' was allocated ${spend:,.0f} despite estimated marginal iROAS < 1.0 ({m_iroas:.2f}). "
                            f"This allocation is likely driven by steep initial saturation curvature near zero spend or constraint bounds rather than incremental profitability."
                        ),
                        "evidence": {
                            "channel": ch,
                            "allocated_spend": spend,
                            "marginal_iroas": m_iroas,
                            "binding_constraints": constraints_active,
                        },
                        "suggested_action": (
                            f"Evaluate whether to constrain '{ch}' with min=0 or reallocate its budget to higher-performing incremental channels."
                        ),
                    }
                )
            else:
                verdict = "profitable"

            rationale[ch] = {
                "allocated_spend": spend,
                "baseline_spend": base_spend,
                "spend_change_pct": spend_change_pct,
                "marginal_iroas_estimate": m_iroas,
                "binding_constraints": constraints_active or ["budget_constrained"],
                "economic_verdict": verdict,
            }

        combined_warnings = extrap_warnings + ident_warnings + economic_warnings

        scenario_id = f"scenario_{uuid.uuid4().hex[:12]}"
        payload = {
            "scenario_id": scenario_id,
            "model_id": input.model_id,
            "kind": "optimization",
            "input": input.model_dump(),
            "result": result,
            "extrapolation_warnings": extrap_warnings,
            "identifiability_warnings": ident_warnings,
            "economic_warnings": economic_warnings,
            "channel_confidence": channel_conf,
            "allocation_rationale": rationale,
            "created_at": _utc(),
        }
        self._raise_if_cancelled(cancel_event, "Optimization")
        self.metadata.put_scenario(payload)
        result.update(
            {
                "scenario_id": scenario_id,
                "model_id": input.model_id,
                "allocation_rationale": rationale,
                "warnings": combined_warnings,
                "identifiability_warnings": ident_warnings,
                "identifiability_risks": ident_warnings,
                "economic_warnings": economic_warnings,
                "channel_confidence": channel_conf,
                "decision_gate": self._gate_payload(record),
                "provenance": self._provenance(input.model_id, record),
            }
        )
        return result

    def simulate(self, input, cancel_event: Any = None):
        self._raise_if_cancelled(cancel_event, "Simulation")
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
        self._raise_if_cancelled(cancel_event, "Simulation")
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
        self._raise_if_cancelled(cancel_event, "Simulation")
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

    def optimize_flighting(self, input, cancel_event: Any = None):
        self._raise_if_cancelled(cancel_event, "Flighting optimization")
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

        # Training-time channel scaling and target scaling: parameters live in scaled space.
        channel_scale: dict[str, float] | None = None
        target_scale: float | None = None
        try:
            scales = model.get_scales_as_xarray()
            if "target_scale" in scales:
                target_scale = float(np.asarray(scales["target_scale"]).reshape(-1).mean())
            elif "target" in scales:
                target_scale = float(np.asarray(scales["target"]).reshape(-1).mean())
            elif hasattr(model, "scalers") and hasattr(model.scalers, "_target"):
                target_scale = float(
                    np.asarray(
                        getattr(model.scalers._target, "values", model.scalers._target)
                    ).reshape(-1).mean()
                )

            if "channel_scale" in scales:
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
        if data_vars is not None and post is not None:
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
            target_scale=target_scale,
        )

        constraints_dicts = [c.model_dump() for c in input.channel_constraints]
        fin_assump = None
        if getattr(input, "financial", None) is not None:
            from marketing_mcp.domain.decisions.financial import FinancialAssumptions
            fin_assump = FinancialAssumptions(**input.financial.model_dump())

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
            financial=fin_assump,
        )
        self._raise_if_cancelled(cancel_event, "Flighting optimization")

        total_channel_spend = flighting_res["total_channel_spend"]
        baseline_channel_spend = historical_allocation(
            model,
            input.planning_weeks,
            total_budget=input.total_budget,
        )

        from marketing_mcp.domain.decisions.allocation import model_dimensions
        dims = model_dimensions(model)
        if dims and isinstance(baseline_channel_spend, dict) and "cells" in baseline_channel_spend:
            channel_baseline_totals: dict[str, float] = {}
            for cell in baseline_channel_spend["cells"]:
                ch = cell["channel"]
                channel_baseline_totals[ch] = channel_baseline_totals.get(ch, 0.0) + float(cell["amount"])

            scenario_cells = []
            for cell in baseline_channel_spend["cells"]:
                ch = cell["channel"]
                base_tot = channel_baseline_totals.get(ch, 0.0)
                rec_ch_spend = total_channel_spend.get(ch, 0.0)
                if base_tot > 0:
                    scaled_amt = float(cell["amount"]) * (rec_ch_spend / base_tot)
                else:
                    cells_for_ch = sum(1 for c in baseline_channel_spend["cells"] if c["channel"] == ch)
                    scaled_amt = rec_ch_spend / max(1, cells_for_ch)
                scenario_cells.append({
                    "channel": ch,
                    "dimensions": dict(cell["dimensions"]),
                    "amount": round(scaled_amt, 4),
                })
            scenario_allocation: dict[str, Any] = {
                "dimensions": list(dims),
                "cells": scenario_cells,
            }
        else:
            scenario_allocation = total_channel_spend

        sim_res = self.modeling.adapter_factory().simulate_budget(
            model,
            baseline_allocation=baseline_channel_spend,
            scenario_allocation=scenario_allocation,
            planning_periods=input.planning_weeks,
        )
        self._raise_if_cancelled(cancel_event, "Flighting optimization")

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
        self._raise_if_cancelled(cancel_event, "Flighting optimization")
        self.metadata.put_scenario(payload)

        prov = self._provenance(input.model_id, record)
        if fin_assump is not None:
            prov["financial_assumptions"] = fin_assump.to_provenance()
        elif getattr(input, "margin_pct", None) is not None:
            prov["financial_assumptions"] = {"gross_margin_rate": input.margin_pct, "legacy_margin_pct": True}
        prov["objective_definition"] = {
            "name": input.objective,
            "description": "Expected net profit" if input.objective == "maximize_net_profit" else "Expected response",
        }
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
            "comparison_baseline": {
                "total_budget": input.total_budget,
                "planning_weeks": input.planning_weeks,
                "baseline_channel_spend": baseline_channel_spend,
                "baseline_response": sim_res.get("baseline_response"),
                "scenario_response": sim_res.get("scenario_response"),
                "mean_response_delta": sim_res.get("comparison", {}).get("mean_response_delta")
                if isinstance(sim_res.get("comparison"), dict)
                else None,
                "percent_change": sim_res.get("comparison", {}).get("percent_change")
                if isinstance(sim_res.get("comparison"), dict)
                else None,
            },
            "warnings": flighting_res["warnings"],
            "decision_gate": self._gate_payload(record),
            "provenance": prov,
        }
