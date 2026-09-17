"""Panel / Hierarchical MMM suitability evaluator."""

from __future__ import annotations

from marketing_mcp.intelligence.contracts.profile import TemporalProfile
from marketing_mcp.intelligence.contracts.semantics import InferredColumn
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    SuitabilityAssessment,
    SuitabilityVerdict,
)


def evaluate_panel_mmm_suitability(
    temporal: TemporalProfile,
    target: InferredColumn | None,
    channels: list[InferredColumn],
    dimensions: list[InferredColumn],
    is_rectangular: bool = True,
    market_count: int = 1,
) -> SuitabilityAssessment:
    """Determines whether dataset satisfies panel MMM criteria."""
    reasons: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if not dimensions:
        blockers.append("No geographic or segment dimension identified for panel modeling")

    if market_count < 2:
        blockers.append("Panel modeling requires at least 2 distinct markets/segments")

    if not is_rectangular:
        recommendations.append("Balance the date x market panel grid before hierarchical modeling")
        verdict = SuitabilityVerdict.REQUIRES_TRANSFORMATION
    elif blockers:
        verdict = SuitabilityVerdict.NOT_SUITABLE
    else:
        verdict = SuitabilityVerdict.SUITABLE
        reasons.append(f"Balanced rectangular panel with {market_count} segments confirmed")

    return SuitabilityAssessment(
        analysis_type=AnalysisType.PANEL_MMM,
        verdict=verdict,
        reasons=reasons,
        blockers=blockers,
        warnings=warnings,
        recommended_transformations=recommendations,
    )
