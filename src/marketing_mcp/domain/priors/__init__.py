"""Prior recommendation domain package."""

from marketing_mcp.domain.priors.contracts import (
    EvidenceType,
    PriorAlternative,
    PriorRecommendation,
    PriorRecommendationReport,
)
from marketing_mcp.domain.priors.recommender import recommend_priors_for_channels

__all__ = [
    "EvidenceType",
    "PriorAlternative",
    "PriorRecommendation",
    "PriorRecommendationReport",
    "recommend_priors_for_channels",
]
