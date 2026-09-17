"""Unified Semantic Dataset Contract and Modeling Contract."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .evidence import HeuristicConfidence
from .issues import IntelligenceIssue
from .profile import StructuralProfile
from .semantics import InferredColumn
from .suitability import AnalysisType, SuitabilityAssessment


class TransformationStep(BaseModel):
    operation: str = Field(description="Transformation type: aggregate, pivot, filter, date_complete, currency_normalize")
    reason: str = Field(description="Why this transformation is necessary for statistical validity")
    details: dict[str, Any] = Field(default_factory=dict, description="Parameters and column mappings for the transformation")


class TransformationPlan(BaseModel):
    requires_mutation: bool = False
    proposed_steps: list[TransformationStep] = Field(default_factory=list)
    human_explanation: str = ""


class ClarificationRequest(BaseModel):
    question: str
    context: str
    options: list[str] = Field(default_factory=list)
    affected_analysis: str = ""


class ModelingContract(BaseModel):
    """Downstream contract consumed by PyMC-Marketing fitting tools without rediscovery."""
    dataset_id: str
    date_column: str
    target_column: str
    channel_columns: list[str]
    control_columns: list[str] = Field(default_factory=list)
    dims: list[str] = Field(default_factory=list)
    frequency: str = "weekly"
    currency: str | None = None
    known_risks: list[str] = Field(default_factory=list)
    user_overrides_applied: dict[str, Any] = Field(default_factory=dict)


class SemanticDatasetContract(BaseModel):
    """Authoritative source of truth describing dataset structure, semantics, and readiness."""
    dataset_id: str
    structural: StructuralProfile
    target: InferredColumn | None = None
    channels: list[InferredColumn] = Field(default_factory=list)
    controls: list[InferredColumn] = Field(default_factory=list)
    dimensions: list[InferredColumn] = Field(default_factory=list)
    columns: dict[str, InferredColumn] = Field(default_factory=dict)
    currencies: list[str] = Field(default_factory=list)
    issues: list[IntelligenceIssue] = Field(default_factory=list)
    suitability: dict[AnalysisType, SuitabilityAssessment] = Field(default_factory=dict)
    transformation_plan: TransformationPlan = Field(default_factory=TransformationPlan)
    clarification_requests: list[ClarificationRequest] = Field(default_factory=list)
    modeling_contract: ModelingContract | None = None
    user_overrides: dict[str, Any] = Field(default_factory=dict)
