"""Prior recommendation domain package."""

from marketing_mcp.domain.priors.contracts import (
    EvidenceGrade,
    EvidenceType,
    IncrementalityStatus,
    PriorAlternative,
    PriorRecommendation,
    PriorRecommendationReport,
    ProvenanceType,
)
from marketing_mcp.domain.priors.recommender import recommend_priors_for_channels

__all__ = [
    "EvidenceGrade",
    "EvidenceType",
    "IncrementalityStatus",
    "PriorAlternative",
    "PriorRecommendation",
    "PriorRecommendationReport",
    "ProvenanceType",
    "recommend_priors_for_channels",
]
