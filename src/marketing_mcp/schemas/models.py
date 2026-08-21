from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

Severity=Literal["info","warning","error"]
DecisionStatus=Literal["approved","approved_with_caution","rejected"]

class Finding(BaseModel):
    severity: Severity
    code: str
    message: str
    evidence: dict[str,Any]=Field(default_factory=dict)
    suggested_action: str | None=None

class DatasetRegistration(BaseModel):
    dataset_id:str; path:str; fingerprint:str; format:Literal["csv","parquet"]; rows:int; created_at:str

class DatasetInspection(BaseModel):
    dataset_id:str; rows:int; frequency:str|None; date_range:dict[str,str|None]; possible_targets:list[str]; possible_channels:list[str]; possible_controls:list[str]; missing_periods:list[str]; issues:list[Finding]; mmm_candidate:bool

class DatasetValidationResult(BaseModel):
    dataset_id:str; findings:list[Finding]; valid_for_modeling:bool

class AdstockConfig(BaseModel):
    type: Literal["geometric"]="geometric"
    l_max:int=Field(default=8,ge=1,le=52)

class SaturationConfig(BaseModel):
    type: Literal["logistic"]="logistic"

class SamplerConfig(BaseModel):
    draws:int=Field(default=1000,ge=100,le=20000)
    tune:int=Field(default=1000,ge=100,le=20000)
    chains:int=Field(default=4,ge=2,le=8)
    target_accept:float=Field(default=0.9,ge=0.8,le=0.999)
    random_seed:int=42

class FitMMMInput(BaseModel):
    dataset_id:str
    date_column:str
    target_column:str
    channel_columns:list[str]=Field(min_length=1,max_length=40)
    control_columns:list[str]=Field(default_factory=list,max_length=100)
    yearly_seasonality:int|None=Field(default=None,ge=1,le=12)
    adstock:AdstockConfig=Field(default_factory=AdstockConfig)
    saturation:SaturationConfig=Field(default_factory=SaturationConfig)
    sampler:SamplerConfig=Field(default_factory=SamplerConfig)
    dims:list[str]=Field(default_factory=list,max_length=4)

class ModelRecord(BaseModel):
    model_id:str; dataset_id:str; status:Literal["queued","running","completed","failed","cancelled"]; model_type:str="MMM"; artifact_path:str|None=None; config:dict[str,Any]; created_at:str; updated_at:str; failure:dict[str,Any]|None=None; validation_state:str="not_diagnosed"; diagnostics:dict[str,Any]|None=None; override_history:list[dict[str,Any]]=Field(default_factory=list)

class DiagnosticResult(BaseModel):
    model_id:str|None=None; decision_status:DecisionStatus; diagnostics:dict[str,Any]; warnings:list[Finding]=Field(default_factory=list); failures:list[dict[str,Any]]=Field(default_factory=list); decision_tools_enabled:bool

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
    budget: float = Field(gt=0)
    planning_periods: int = Field(default=8, ge=1, le=260)
    constraints: dict[str, ChannelConstraint] = Field(default_factory=dict)
    cell_constraints: list[BudgetCellConstraint] = Field(default_factory=list, max_length=1000)


class ToolEnvelope(BaseModel):
    summary:dict[str,Any]=Field(default_factory=dict); evidence:dict[str,Any]=Field(default_factory=dict); warnings:list[Any]=Field(default_factory=list); provenance:dict[str,Any]=Field(default_factory=dict); next_actions:list[str]=Field(default_factory=list)
