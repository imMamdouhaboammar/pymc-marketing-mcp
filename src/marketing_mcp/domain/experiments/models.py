"""Domain models and schemas for Experiment Evidence Registry."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExperimentMethodology = Literal[
    "geo_lift",
    "user_randomized",
    "matched_markets",
    "regression_discontinuity",
    "switchback",
    "other",
]


class RegisterExperimentInput(BaseModel):
    """Input payload to register an experiment in the evidence registry."""

    experiment_id: str = Field(description="Unique experiment identifier")
    channel: str = Field(description="Target marketing channel")
    geo: str | None = Field(default=None, description="Optional geography or region dimension value")
    methodology: ExperimentMethodology = Field(
        default="geo_lift", description="Experimental methodology applied"
    )
    start_date: str = Field(description="Experiment start date (YYYY-MM-DD)")
    end_date: str = Field(description="Experiment end date (YYYY-MM-DD)")
    treatment_description: str | None = Field(
        default=None, description="Description of treatment / intervention design"
    )
    baseline_spend: float = Field(ge=0, description="Baseline spend level (x)")
    spend_delta: float = Field(gt=0, description="Incremental spend during experiment (delta_x)")
    measured_incremental_response: float = Field(
        description="Measured incremental KPI response (delta_y)"
    )
    standard_error: float = Field(
        gt=0, description="Standard error / uncertainty of incremental response (sigma)"
    )
    evidence_quality_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Quality rating: 0.0=observational proxy, 1.0=gold-standard double-blind/geo-lift",
    )
    source: str = Field(default="experiment_registry", description="Evidence origin or platform")
    tenant_id: str | None = Field(default=None, description="Tenant/organization identifier")
    project_id: str | None = Field(default=None, description="Project identifier")


class ExperimentRecord(BaseModel):
    """Stored experiment record with immutable provenance."""

    experiment_id: str
    channel: str
    geo: str | None = None
    methodology: ExperimentMethodology
    start_date: str
    end_date: str
    treatment_description: str | None = None
    baseline_spend: float
    spend_delta: float
    measured_incremental_response: float
    standard_error: float
    evidence_quality_score: float
    source: str
    tenant_id: str = "default"
    project_id: str | None = None
    archived: bool = False
    created_at: str
    provenance: dict[str, Any] = Field(default_factory=dict)
