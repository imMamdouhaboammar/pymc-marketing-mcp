"""Typed contracts for Marketing Data Intelligence Engine."""

from .contract import ModelingContract, SemanticDatasetContract, TransformationPlan
from .evidence import ConfidenceLevel, EvidenceSignal, HeuristicConfidence
from .issues import IntelligenceIssue, IssueCode, IssueSeverity
from .profile import ColumnProfile, StructuralProfile, TemporalProfile
from .semantics import InferredColumn, SemanticRole, SemanticType
from .suitability import (
    AnalysisType,
    IdentifiabilityRisk,
    RiskLevel,
    SuitabilityAssessment,
    SuitabilityVerdict,
)

__all__ = [
    "ConfidenceLevel", "EvidenceSignal", "HeuristicConfidence",
    "ColumnProfile", "StructuralProfile", "TemporalProfile",
    "InferredColumn", "SemanticRole", "SemanticType",
    "IntelligenceIssue", "IssueCode", "IssueSeverity",
    "AnalysisType", "IdentifiabilityRisk", "RiskLevel", "SuitabilityAssessment", "SuitabilityVerdict",
    "SemanticDatasetContract", "TransformationPlan", "ModelingContract",
]
