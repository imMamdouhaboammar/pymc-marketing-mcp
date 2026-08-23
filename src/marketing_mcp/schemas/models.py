from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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


AdstockType = Literal[
    "geometric",
    "delayed",
    "weibull_cdf",
    "weibull_pdf",
    "binomial",
    "none",
]
SaturationType = Literal[
    "logistic",
    "tanh",
    "tanh_baselined",
    "michaelis_menten",
    "hill",
    "hill_sigmoid",
    "inverse_scaled_logistic",
    "log",
    "root",
    "none",
]


class AdstockConfig(BaseModel):
    type: AdstockType = "geometric"
    l_max: int = Field(default=8, ge=1, le=52, description="Maximum lag periods for adstock")
    normalize: bool = Field(default=True, description="Whether to normalize adstock weights to sum to 1")


class SaturationConfig(BaseModel):
    type: SaturationType = "logistic"


class PriorDistributionConfig(BaseModel):
    dist: str = Field(default="Beta", description="Prior distribution family (e.g. Beta, Gamma, HalfNormal, Normal)")
    kwargs: dict[str, float] = Field(default_factory=dict, description="Distribution parameters (e.g. alpha, beta, sigma, mu)")


class ChannelPriorConfig(BaseModel):
    """Per-channel prior parameters and/or transform class selection."""

    adstock: AdstockConfig | None = None
    saturation: SaturationConfig | None = None
    priors: dict[str, PriorDistributionConfig] = Field(
        default_factory=dict,
        description="Per-parameter prior overrides (e.g. {'adstock_alpha': PriorDistributionConfig(...)})",
    )


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
        default_factory=AdstockConfig,
        description="Global adstock configuration (default for all channels)",
    )
    saturation: SaturationConfig = Field(
        default_factory=SaturationConfig,
        description="Global saturation configuration (default for all channels)",
    )
    sampler: SamplerConfig = Field(
        default_factory=SamplerConfig, description="NUTS sampler configuration"
    )
    dims: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="Multidimensional panel dimensions (e.g. ['geo'])",
    )
    channel_priors: dict[str, ChannelPriorConfig] = Field(
        default_factory=dict,
        description=(
            "Per-channel adstock and/or saturation overrides. "
            "Keys must be a subset of channel_columns. "
            "Channels not listed use the global adstock/saturation config."
        ),
    )

    @field_validator("channel_priors", mode="after")
    @classmethod
    def _channel_priors_are_known_channels(cls, v: dict) -> dict:
        # Deferred — full check via model_validator after channel_columns is known
        return v

    @model_validator(mode="after")
    def _validate_channel_priors_keys(self) -> FitMMMInput:
        unknown = set(self.channel_priors) - set(self.channel_columns)
        if unknown:
            raise ValueError(
                f"channel_priors contains unknown channels: {sorted(unknown)}. "
                f"Keys must be a subset of channel_columns."
            )
        return self


# ---------------------------------------------------------------------------
# CLV Schemas (Phase 3)
# ---------------------------------------------------------------------------

CLVModelType = Literal["bg_nbd", "gamma_gamma", "shifted_beta_geo"]


class FitPurchaseModelInput(BaseModel):
    dataset_id: str = Field(description="Registered dataset ID containing RFM data")
    customer_id_col: str = Field(default="customer_id", description="Column containing unique customer identifiers")
    frequency_col: str = Field(default="frequency", description="Column with repeat purchase count")
    recency_col: str = Field(default="recency", description="Column with recency (time since last purchase)")
    T_col: str = Field(default="T", description="Column with total observation period length")
    cohort_col: str | None = Field(default=None, description="Column with customer cohort (required for sBG)")
    model_type: Literal["bg_nbd", "shifted_beta_geo"] = Field(
        default="bg_nbd",
        description="Purchase model type: 'bg_nbd' (continuous) or 'shifted_beta_geo' (contractual subscription)",
    )
    sampler: SamplerConfig = Field(default_factory=SamplerConfig)


class FitValueModelInput(BaseModel):
    dataset_id: str = Field(description="Registered dataset ID containing monetary transaction data")
    customer_id_col: str = Field(default="customer_id", description="Column containing unique customer identifiers")
    frequency_col: str = Field(default="frequency", description="Column with repeat purchase count")
    monetary_value_col: str = Field(default="monetary_value", description="Column with average monetary value per transaction")
    model_type: Literal["gamma_gamma"] = Field(
        default="gamma_gamma",
        description="Value model type: 'gamma_gamma'",
    )
    sampler: SamplerConfig = Field(default_factory=SamplerConfig)


class PredictExpectedPurchasesInput(BaseModel):
    model_id: str = Field(description="Fitted purchase model ID (BG/NBD)")
    future_t: int = Field(default=12, ge=1, le=104, description="Number of future periods to forecast")
    top_n: int | None = Field(default=None, ge=1, le=10000, description="Return top N customers by expected purchases")


class PredictProbabilityAliveInput(BaseModel):
    model_id: str = Field(description="Fitted purchase/churn model ID")
    top_n: int | None = Field(default=None, ge=1, le=10000, description="Return top N customers by probability alive")


class PredictExpectedSpendInput(BaseModel):
    model_id: str = Field(description="Fitted monetary value model ID (Gamma-Gamma)")
    top_n: int | None = Field(default=None, ge=1, le=10000, description="Return top N customers by expected spend")


class EstimateCLVInput(BaseModel):
    purchase_model_id: str = Field(description="Fitted transaction/purchase model ID (e.g. BG/NBD)")
    value_model_id: str = Field(description="Fitted monetary value model ID (e.g. Gamma-Gamma)")
    future_t: int = Field(default=12, ge=1, le=104, description="Number of future periods to forecast")
    discount_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Periodic discount rate for NPV")
    top_n: int | None = Field(default=None, ge=1, le=10000, description="Return top N customers by predicted CLV")


class ChurnRiskInput(BaseModel):
    model_id: str = Field(description="Fitted purchase or churn model ID")
    threshold_p_alive: float = Field(default=0.3, ge=0.0, le=1.0, description="Probability threshold below which customer is at churn risk")


class CLVModelConfig(BaseModel):
    model_type: CLVModelType = "bg_nbd"
    customer_id_column: str = Field(description="Column containing unique customer identifiers")
    frequency_column: str = Field(description="Column with repeat purchase count")
    recency_column: str = Field(description="Column with recency (time since last purchase)")
    T_column: str = Field(description="Column with total observation period length")
    monetary_value_column: str | None = Field(
        default=None,
        description="Column with average monetary value per purchase (required for gamma_gamma)",
    )
    cohort_column: str | None = Field(
        default=None,
        description="Column with customer cohort (required for shifted_beta_geo)",
    )
    sampler: SamplerConfig = Field(default_factory=SamplerConfig)

    @model_validator(mode="after")
    def _validate_model_specific_columns(self) -> CLVModelConfig:
        if self.model_type == "gamma_gamma" and not self.monetary_value_column:
            raise ValueError("gamma_gamma model requires monetary_value_column to be set")
        if self.model_type == "shifted_beta_geo" and not self.cohort_column:
            # sBG requires cohort column for grouping
            pass
        return self


class FitCLVInput(BaseModel):
    dataset_id: str = Field(description="Registered dataset ID containing RFM data")
    config: CLVModelConfig


class PredictCLVInput(BaseModel):
    model_id: str = Field(description="Fitted CLV model ID")
    future_t: int = Field(
        default=12,
        ge=1,
        le=104,
        description="Number of future periods to forecast",
    )
    top_n_customers: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="If set, return only the top N customers by expected purchases",
    )



class CLVModelRecord(BaseModel):
    model_id: str
    model_type: CLVModelType
    dataset_id: str
    status: ModelStatus
    artifact_path: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    package_provenance: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    failure: dict[str, Any] | None = None


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


PlotType = Literal[
    "saturation_curves",
    "waterfall_decomposition",
    "actual_vs_predicted",
    "channel_contribution_share",
]


class GetPosteriorPlotsInput(BaseModel):
    model_id: str = Field(description="Fitted model ID to visualize")
    plot_types: list[PlotType] = Field(
        default=["saturation_curves", "waterfall_decomposition"],
        min_length=1,
        max_length=4,
        description="Which posterior plots to generate",
    )
    format: Literal["png", "svg"] = Field(default="png", description="Output image format")


# ---------------------------------------------------------------------------
# Phase 4 — Dynamic Flighting Schemas
# ---------------------------------------------------------------------------

SpendPattern = Literal["flat", "frontloaded", "backloaded", "pulsed"]
FlightingObjective = Literal["maximize_response", "maximize_net_profit", "target_roas"]


class WeeklyFlightingConstraint(BaseModel):
    channel: str = Field(description="Channel name this constraint applies to")
    min_weekly: float | None = Field(default=None, ge=0, description="Minimum weekly spend floor")
    max_weekly: float | None = Field(default=None, ge=0, description="Maximum weekly spend cap")
    pattern: SpendPattern = Field(
        default="flat",
        description="Preferred spend pattern for this channel across the planning horizon",
    )


class FlightingOptimizationInput(BaseModel):
    model_id: str = Field(description="Approved MMM model ID to use for response estimation")
    total_budget: float = Field(
        gt=0, description="Total budget to allocate across all channels and weeks"
    )
    planning_weeks: int = Field(default=12, ge=2, le=52, description="Planning horizon in weeks")
    target_iroas_min: float | None = Field(
        default=None,
        ge=0,
        description="Minimum acceptable posterior median iROAS across the planning period",
    )
    margin_pct: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Revenue margin fraction for net-profit objective (revenue × margin − spend)",
    )
    channel_constraints: list[WeeklyFlightingConstraint] = Field(
        default_factory=list,
        description="Per-channel weekly spend floor/cap and pattern constraints",
    )
    objective: FlightingObjective = Field(
        default="maximize_response",
        description="Optimization objective function",
    )


# ---------------------------------------------------------------------------
# Phase 5 — Model Selection Schemas
# ---------------------------------------------------------------------------

CriterionType = Literal["loo", "waic", "both"]
WeightingType = Literal["stacking", "bb-pseudo-bma", "pseudo-bma"]
ComparisonMethod = Literal["loo", "waic", "stacking", "all"]


class ModelComparisonInput(BaseModel):
    model_ids: list[str] = Field(
        min_length=2,
        max_length=10,
        description="List of 2–10 model IDs to compare. All must be fitted on the same dataset.",
    )
    criterion: CriterionType = Field(
        default="loo",
        description="Information criterion: 'loo' (PSIS-LOO), 'waic', or 'both'",
    )
    weighting: WeightingType = Field(
        default="stacking",
        description="Model weighting method: 'stacking', 'bb-pseudo-bma', or 'pseudo-bma'",
    )
    method: str | None = Field(
        default=None,
        description="Deprecated: use `criterion` and `weighting` instead",
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_method(cls, data: Any) -> Any:
        if isinstance(data, dict) and "method" in data and data["method"]:
            legacy = data["method"]
            if "criterion" not in data:
                if legacy in ("loo", "waic", "both"):
                    data["criterion"] = legacy
                elif legacy == "stacking":
                    data["criterion"] = "loo"
                    data["weighting"] = "stacking"
                elif legacy == "all":
                    data["criterion"] = "both"
            if "weighting" not in data and legacy in ("stacking", "bb-pseudo-bma", "pseudo-bma"):
                data["weighting"] = legacy
        return data


class ModelComparisonResult(BaseModel):
    criterion: str = "loo"
    weighting: str = "stacking"
    method: str = "loo"
    ranked_models: list[dict[str, Any]] = Field(default_factory=list)
    best_model_id: str | None = None
    recommended_model_id: str | None = None
    recommendation_reason: str | None = None
    stacking_weights: dict[str, float] | None = None
    pareto_k_warnings: list[dict[str, Any]] = Field(default_factory=list)
    comparisons: dict[str, Any] | None = None
    interpretation: str = ""


class ToolEnvelope(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[Any] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
