from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Severity = Literal["info", "warning", "error"]
DecisionStatus = Literal["approved", "approved_with_caution", "rejected"]
ModelStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
LineageStage = Literal["initial_fit", "calibrated", "refreshed"]


class Finding(BaseModel):
    severity: Severity = Field(description="Finding severity level")
    code: str = Field(description="Machine-readable code")
    message: str = Field(description="Human-readable explanation")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence data")
    suggested_action: str | None = Field(default=None, description="Recommended remediation action")


class DatasetRegistration(BaseModel):
    dataset_id: str
    path: str
    fingerprint: str
    format: Literal["csv", "parquet"]
    rows: int
    created_at: str


class DatasetInspection(BaseModel):
    dataset_id: str
    rows: int
    frequency: str | None
    date_range: dict[str, str | None]
    possible_targets: list[str]
    possible_channels: list[str]
    possible_controls: list[str]
    missing_periods: list[str]
    issues: list[Finding]
    mmm_candidate: bool


class DatasetValidationResult(BaseModel):
    dataset_id: str
    findings: list[Finding]
    valid_for_modeling: bool


class AdstockConfig(BaseModel):
    type: Literal["geometric"] = "geometric"
    l_max: int = Field(default=8, ge=1, le=52, description="Maximum lag periods for adstock")


class SaturationConfig(BaseModel):
    type: Literal["logistic"] = "logistic"


class SamplerConfig(BaseModel):
    draws: int = Field(default=1000, ge=50, le=20000, description="Posterior draws per chain")
    tune: int = Field(
        default=1000, ge=50, le=20000, description="Tuning/warmup iterations per chain"
    )
    chains: int = Field(default=4, ge=2, le=8, description="Number of MCMC chains")
    target_accept: float = Field(
        default=0.9, ge=0.8, le=0.999, description="Target acceptance rate for NUTS"
    )
    random_seed: int = Field(default=42, description="Deterministic random seed")


class FitMMMInput(BaseModel):
    dataset_id: str = Field(description="Registered dataset ID")
    date_column: str = Field(description="Column containing temporal dates")
    target_column: str = Field(description="Outcome KPI column (e.g. revenue, conversions)")
    channel_columns: list[str] = Field(
        min_length=1, max_length=40, description="Media spend column names"
    )
    control_columns: list[str] = Field(
        default_factory=list, max_length=100, description="Non-media control columns"
    )
    yearly_seasonality: int | None = Field(
        default=None, ge=1, le=12, description="Order of Fourier yearly seasonality"
    )
    adstock: AdstockConfig = Field(
        default_factory=AdstockConfig, description="Adstock configuration"
    )
    saturation: SaturationConfig = Field(
        default_factory=SaturationConfig, description="Saturation configuration"
    )
    sampler: SamplerConfig = Field(
        default_factory=SamplerConfig, description="NUTS sampler configuration"
    )
    dims: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Multidimensional panel dimensions (e.g. ['geo'])",
    )


class ModelRecord(BaseModel):
    model_id: str
    parent_model_id: str | None = None
    lineage_stage: LineageStage = "initial_fit"
    dataset_id: str
    dataset_fingerprint: str = ""
    semantic_config_hash: str = ""
    status: ModelStatus = "completed"
    model_type: str = "MMM"
    artifact_path: str | None = None
    config: dict[str, Any]
    package_provenance: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    failure: dict[str, Any] | None = None
    validation_state: str = "not_diagnosed"
    diagnostics: dict[str, Any] | None = None
    override_history: list[dict[str, Any]] = Field(default_factory=list)


class DiagnosticResult(BaseModel):
    model_id: str | None = None
    decision_status: DecisionStatus
    diagnostics: dict[str, Any]
    warnings: list[Finding] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)
    decision_tools_enabled: bool


class BudgetChange(BaseModel):
    type: Literal["relative", "absolute"]
    value: float


class BudgetCellChange(BudgetChange):
    channel: str
    dimensions: dict[str, str | int | float | bool] = Field(default_factory=dict)


class BudgetSimulationInput(BaseModel):
    model_id: str
    planning_periods: int = Field(default=8, ge=1, le=260)
    changes: dict[str, BudgetChange] = Field(default_factory=dict)
    cell_changes: list[BudgetCellChange] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def require_change(self):
        if not self.changes and not self.cell_changes:
            raise ValueError("At least one channel or dimension-cell change is required")
        return self


class ChannelConstraint(BaseModel):
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)
    fixed: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_bounds(self):
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min cannot exceed max")
        if self.fixed is not None:
            if self.min is not None and self.fixed < self.min:
                raise ValueError("fixed below min")
            if self.max is not None and self.fixed > self.max:
                raise ValueError("fixed above max")
        return self


class BudgetCellConstraint(ChannelConstraint):
    channel: str
    dimensions: dict[str, str | int | float | bool] = Field(default_factory=dict)


class BudgetOptimizationInput(BaseModel):
    model_id: str
    budget: float = Field(gt=0, description="Total budget amount to allocate")
    planning_periods: int = Field(
        default=8, ge=1, le=260, description="Number of future periods in planning horizon"
    )
    constraints: dict[str, ChannelConstraint] = Field(
        default_factory=dict, description="Channel-level min/max/fixed bounds"
    )
    cell_constraints: list[BudgetCellConstraint] = Field(
        default_factory=list, max_length=1000, description="Cell-level dimension bounds"
    )


class LiftTestMeasurement(BaseModel):
    channel: str = Field(description="Marketing channel name")
    geo: str | None = Field(default=None, description="Optional geography dimension value")
    x: float = Field(ge=0, description="Baseline media spend or volume level during experiment")
    delta_x: float = Field(gt=0, description="Spend or volume increment during experiment")
    delta_y: float = Field(description="Measured incremental KPI response")
    sigma: float = Field(
        gt=0, description="Standard error/uncertainty of the measured incremental KPI"
    )
    description: str | None = Field(
        default=None, description="Experiment description or study identifier"
    )


class CalibrateMMMInput(BaseModel):
    model_id: str = Field(description="Fitted base model ID to calibrate")
    lift_tests: list[LiftTestMeasurement] = Field(
        min_length=1, max_length=100, description="Lift test experimental measurements"
    )
    sampler: SamplerConfig = Field(
        default_factory=SamplerConfig, description="Sampler settings for calibration fit"
    )


class CrossValidateMMMInput(BaseModel):
    model_id: str = Field(description="Fitted model ID to cross-validate")
    n_init: int = Field(default=40, ge=10, le=500, description="Initial training period count")
    forecast_horizon: int = Field(
        default=10, ge=1, le=52, description="Out-of-sample forecast window size"
    )
    step_size: int = Field(default=10, ge=1, le=52, description="Step size between rolling folds")
    sampler: SamplerConfig = Field(
        default_factory=SamplerConfig, description="Sampler settings for fold fitting"
    )


class CompareModelsInput(BaseModel):
    model_ids: list[str] = Field(
        min_length=2, max_length=10, description="List of model IDs to compare"
    )


class ArchiveModelInput(BaseModel):
    model_id: str = Field(description="Model ID to archive")


class PriorSensitivityInput(BaseModel):
    model_id: str = Field(description="Model ID to evaluate for prior sensitivity")


class ToolEnvelope(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[Any] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
