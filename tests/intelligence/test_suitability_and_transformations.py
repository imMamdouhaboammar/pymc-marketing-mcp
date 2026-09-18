"""Tests for analysis suitability and transformation planning."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.evidence import ConfidenceLevel, HeuristicConfidence
from marketing_mcp.intelligence.contracts.profile import TemporalProfile
from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    SuitabilityVerdict,
)


def test_mmm_suitability_evaluator_clean_dataset():
    from marketing_mcp.intelligence.suitability.mmm import evaluate_mmm_suitability

    temporal = TemporalProfile(
        date_column="date",
        frequency="weekly",
        observed_periods=60,
        expected_periods=60,
        is_continuous=True,
    )
    target = InferredColumn(
        column="revenue",
        role=SemanticRole.TARGET,
        semantic_type="revenue",
        confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=0.95),
    )
    channel = InferredColumn(
        column="google_spend",
        role=SemanticRole.MEDIA_CHANNEL,
        semantic_type="spend",
        confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=0.95),
    )

    assessment = evaluate_mmm_suitability(
        temporal=temporal,
        target=target,
        channels=[channel],
        issues=[],
        identifiability_risk=None,
    )

    assert assessment.verdict == SuitabilityVerdict.SUITABLE
    assert assessment.analysis_type == AnalysisType.MMM
    assert len(assessment.blockers) == 0


def test_clv_suitability_rejects_pure_aggregate_mmm_data():
    from marketing_mcp.intelligence.suitability.clv import evaluate_clv_suitability

    # Dataset only has date, spend, revenue - NO customer identifier
    cols = {
        "date": InferredColumn(column="date", role=SemanticRole.DATE, semantic_type="date", confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=1.0)),
        "revenue": InferredColumn(column="revenue", role=SemanticRole.TARGET, semantic_type="revenue", confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=1.0)),
    }
    assessment = evaluate_clv_suitability(cols)
    assert assessment.verdict == SuitabilityVerdict.NOT_SUITABLE
    assert any("customer" in b.lower() for b in assessment.blockers)


def test_transformation_planner_proposes_pivot_for_long_form():
    from marketing_mcp.intelligence.transformations.planner import build_transformation_plan

    df = pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10, freq="D").repeat(2),
        "platform": ["Google", "Meta"] * 10,
        "spend": [100.0, 200.0] * 10,
        "revenue": [500.0, 500.0] * 10,
    })

    plan = build_transformation_plan(df, date_column="date", platform_col="platform", spend_col="spend")
    assert plan.requires_mutation is True
    assert len(plan.proposed_steps) >= 1
    assert any(step.operation == "pivot_channels" for step in plan.proposed_steps)
