"""Evidence and confidence contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceSignal(BaseModel):
    signal_name: str = Field(description="Machine-readable identifier of the signal")
    direction: Literal["positive", "negative", "neutral"] = "positive"
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Importance weight of this evidence")
    description: str = Field(description="Human-readable description of the observed evidence")
    observed_value: Any = Field(default=None, description="Underlying observed value or statistic")


class HeuristicConfidence(BaseModel):
    level: ConfidenceLevel = Field(description="Categorical confidence level: high, medium, low")
    score: float = Field(ge=0.0, le=1.0, description="Explicit heuristic confidence score between 0.0 and 1.0 (not a Bayesian probability)")
    evidence: list[EvidenceSignal] = Field(default_factory=list, description="List of supporting or contradicting evidence signals")
