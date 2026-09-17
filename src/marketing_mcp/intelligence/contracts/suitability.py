"""Suitability evaluation and identifiability risk contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AnalysisType(str, Enum):
    MMM = "mmm"
    PANEL_MMM = "panel_mmm"
    CLV = "clv"
    EXPERIMENTATION = "experimentation"


class SuitabilityVerdict(str, Enum):
    SUITABLE = "suitable"
    SUITABLE_WITH_CAUTION = "suitable_with_caution"
    REQUIRES_TRANSFORMATION = "requires_transformation"
    REQUIRES_BUSINESS_CLARIFICATION = "requires_business_clarification"
    NOT_SUITABLE = "not_suitable"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IdentifiabilityRisk(BaseModel):
    overall_risk: RiskLevel = Field(default=RiskLevel.LOW)
    factors: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    mitigations: list[str] = Field(default_factory=list)


class SuitabilityAssessment(BaseModel):
    analysis_type: AnalysisType
    verdict: SuitabilityVerdict
    reasons: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_transformations: list[str] = Field(default_factory=list)
    identifiability_risk: IdentifiabilityRisk | None = None
