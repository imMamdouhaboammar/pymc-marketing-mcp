from __future__ import annotations

from typing import Any

from marketing_mcp.domain.diagnostics.engine import diagnose_inferencedata
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    CrossValidateMMMInput,
    DiagnosticResult,
    PriorSensitivityInput,
)


class DiagnosticsService:
    def __init__(self, metadata, modeling):
        self.metadata = metadata
        self.modeling = modeling

    def diagnose(self, model_id: str) -> DiagnosticResult:
        model, rec = self.modeling.load_model(model_id)
        result = diagnose_inferencedata(model.idata)
        result.model_id = model_id
        rec.validation_state = result.decision_status
        diagnostics_data = result.model_dump()

        if hasattr(rec, "dataset_id") and rec.dataset_id:
            try:
                df = self.modeling.datasets.load(rec.dataset_id)
                from marketing_mcp.scientific.datasets import inspect_dataset_frame
                insp = inspect_dataset_frame(df, dataset_id=rec.dataset_id)
                if insp.semantic_contract:
                    sem = insp.semantic_contract
                    diagnostics_data["data_readiness"] = {
                        "dataset_id": rec.dataset_id,
                        "data_quality_status": "pass" if not any(f.severity == "error" for f in insp.issues) else "block",
                        "semantic_ambiguity": len(insp.clarification_requests) > 0,
                        "identification_risk": sem.get("suitability", {}).get("mmm", {}).get("identifiability_risk", {}),
                        "market_heterogeneity": any(f.code == "MARKET_HETEROGENEITY" for f in insp.issues),
                        "temporal_support": {
                            "frequency": insp.frequency,
                            "rows": insp.rows,
                            "missing_periods_count": len(insp.missing_periods),
                        },
                    }
            except Exception:
                pass

        rec.diagnostics = diagnostics_data
        self.metadata.put_model(rec.model_dump())
        return result

    def cross_validate(self, input: CrossValidateMMMInput, cancel_event: Any = None) -> dict[str, Any]:
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Cross-validation was cancelled by client")
        rec = self.modeling.status(input.model_id)
        df = self.modeling.datasets.load(rec.dataset_id)
        adapter = self.modeling.adapter_factory()
        res = adapter.time_slice_cross_validate(
            df=df,
            config=rec.config,
            n_init=input.n_init,
            forecast_horizon=input.forecast_horizon,
            step_size=input.step_size,
            sampler_config=input.sampler.model_dump(),
        )
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Cross-validation was cancelled by client")
        res["model_id"] = input.model_id

        # Persist cross-validation results into model record diagnostics
        if not rec.diagnostics:
            rec.diagnostics = {}
        rec.diagnostics["cross_validation"] = res
        decision = res.get("decision_provenance", {}).get("decision") or res.get("decision_impact")
        if decision == "blocked_predictive_failure":
            rec.validation_state = "blocked_predictive_failure"
            failures = list(rec.diagnostics.get("failures", []))
            for f in res.get("failures", []):
                if f not in failures:
                    failures.append(f)
            rec.diagnostics["failures"] = failures

        self.metadata.put_model(rec.model_dump())
        return res

    def prior_sensitivity(self, input: PriorSensitivityInput, cancel_event: Any = None) -> dict[str, Any]:
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Prior sensitivity was cancelled by client")
        model, rec = self.modeling.load_model(input.model_id)
        df = self.modeling.datasets.load(rec.dataset_id)
        adapter = self.modeling.adapter_factory()
        res = adapter.evaluate_prior_sensitivity(
            model=model,
            df=df,
            config=rec.config,
        )
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Prior sensitivity was cancelled by client")
        res["model_id"] = input.model_id
        return res
