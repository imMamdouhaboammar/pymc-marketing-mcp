"""Extensible suitability dispatcher assess_suitability(contract, analysis_type)."""

from __future__ import annotations

from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    SuitabilityAssessment,
)
from .mmm import evaluate_mmm_suitability
from .panel_mmm import evaluate_panel_mmm_suitability
from .clv import evaluate_clv_suitability


def assess_suitability(
    analysis_type: AnalysisType,
    temporal,
    target,
    channels,
    dimensions,
    columns,
    issues,
    identifiability_risk=None,
) -> SuitabilityAssessment:
    """Dispatches to appropriate suitability evaluator for the requested analysis type."""
    if analysis_type == AnalysisType.MMM:
        return evaluate_mmm_suitability(
            temporal=temporal,
            target=target,
            channels=channels,
            issues=issues,
            identifiability_risk=identifiability_risk,
        )
    elif analysis_type == AnalysisType.PANEL_MMM:
        return evaluate_panel_mmm_suitability(
            temporal=temporal,
            target=target,
            channels=channels,
            dimensions=dimensions,
            market_count=len(dimensions) if dimensions else 1,
        )
    elif analysis_type == AnalysisType.CLV:
        return evaluate_clv_suitability(columns=columns)
    else:
        return evaluate_mmm_suitability(temporal, target, channels, issues, identifiability_risk)
