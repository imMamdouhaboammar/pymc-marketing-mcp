from __future__ import annotations

from typing import Any

from marketing_mcp.domain.diagnostics.engine import diagnose_inferencedata
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
        rec.diagnostics = result.model_dump()
        self.metadata.put_model(rec.model_dump())
        return result

    def cross_validate(self, input: CrossValidateMMMInput) -> dict[str, Any]:
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
        res["model_id"] = input.model_id
        return res

    def prior_sensitivity(self, input: PriorSensitivityInput) -> dict[str, Any]:
        model, rec = self.modeling.load_model(input.model_id)
        df = self.modeling.datasets.load(rec.dataset_id)
        adapter = self.modeling.adapter_factory()
        res = adapter.evaluate_prior_sensitivity(
            model=model,
            df=df,
            config=rec.config,
        )
        res["model_id"] = input.model_id
        return res
