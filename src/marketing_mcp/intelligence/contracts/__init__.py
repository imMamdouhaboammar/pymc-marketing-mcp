"""Typed contracts for Marketing Data Intelligence Engine."""

from .evidence import ConfidenceLevel, EvidenceSignal, HeuristicConfidence
from .profile import ColumnProfile, StructuralProfile, TemporalProfile
from .semantics import InferredColumn, SemanticRole, SemanticType
from .issues import IntelligenceIssue, IssueCode, IssueSeverity
from .suitability import AnalysisType, IdentifiabilityRisk, RiskLevel, SuitabilityAssessment, SuitabilityVerdict
from .contract import SemanticDatasetContract, TransformationPlan, ModelingContract

__all__ = [
    "ConfidenceLevel", "EvidenceSignal", "HeuristicConfidence",
    "ColumnProfile", "StructuralProfile", "TemporalProfile",
    "InferredColumn", "SemanticRole", "SemanticType",
    "IntelligenceIssue", "IssueCode", "IssueSeverity",
    "AnalysisType", "IdentifiabilityRisk", "RiskLevel", "SuitabilityAssessment", "SuitabilityVerdict",
    "SemanticDatasetContract", "TransformationPlan", "ModelingContract",
]
