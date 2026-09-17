"""Tests for Marketing Data Intelligence Engine typed domain contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_heuristic_confidence_validation():
    from marketing_mcp.intelligence.contracts.evidence import (
        ConfidenceLevel,
        EvidenceSignal,
        HeuristicConfidence,
    )

    signal = EvidenceSignal(
        signal_name="spend_keyword_match",
        direction="positive",
        weight=0.8,
        description="Column name matches media spend pattern",
    )
    conf = HeuristicConfidence(
        level=ConfidenceLevel.HIGH,
        score=0.92,
        evidence=[signal],
    )
    assert conf.level == ConfidenceLevel.HIGH
    assert conf.score == 0.92
    assert len(conf.evidence) == 1
    assert conf.evidence[0].signal_name == "spend_keyword_match"

    # Score must be between 0.0 and 1.0
    with pytest.raises(ValidationError):
        HeuristicConfidence(level=ConfidenceLevel.LOW, score=1.5)


def test_intelligence_issue_creation():
    from marketing_mcp.intelligence.contracts.issues import (
        IntelligenceIssue,
        IssueCode,
        IssueSeverity,
    )

    issue = IntelligenceIssue(
        code=IssueCode.STAGGERED_CHANNEL_LIFECYCLE,
        severity=IssueSeverity.WARNING,
        summary="Channels 'meta' and 'snapchat' have disjoint active windows",
        evidence={"overlap_ratio": 0.12},
        affected_columns=["meta", "snapchat"],
        why_it_matters="Temporal confounding impairs separating channel carryover from trend",
        recommended_action="Align observation windows or use informative adstock priors",
        blocking=False,
    )
    assert issue.code == IssueCode.STAGGERED_CHANNEL_LIFECYCLE
    assert issue.severity == IssueSeverity.WARNING
    assert not issue.blocking
    assert "meta" in issue.affected_columns


def test_semantic_role_and_inferred_column():
    from marketing_mcp.intelligence.contracts.evidence import ConfidenceLevel, HeuristicConfidence
    from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole

    col = InferredColumn(
        column="facebook_ads_usd",
        role=SemanticRole.MEDIA_CHANNEL,
        semantic_type="spend",
        currency="USD",
        confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=0.95),
        user_overridden=False,
    )
    assert col.role == SemanticRole.MEDIA_CHANNEL
    assert col.semantic_type == "spend"
    assert col.currency == "USD"
    assert not col.user_overridden


def test_suitability_assessment_and_verdict():
    from marketing_mcp.intelligence.contracts.suitability import (
        AnalysisType,
        IdentifiabilityRisk,
        RiskLevel,
        SuitabilityAssessment,
        SuitabilityVerdict,
    )

    risk = IdentifiabilityRisk(
        overall_risk=RiskLevel.MEDIUM,
        factors=["High collinearity between search and social spend"],
        mitigations=["Use lift experiment priors for search"],
    )
    assessment = SuitabilityAssessment(
        analysis_type=AnalysisType.MMM,
        verdict=SuitabilityVerdict.SUITABLE_WITH_CAUTION,
        reasons=["Dataset has 60 weekly periods and 3 active channels"],
        warnings=["Search and social spend exhibit r=0.88 correlation"],
        identifiability_risk=risk,
    )
    assert assessment.verdict == SuitabilityVerdict.SUITABLE_WITH_CAUTION
    assert assessment.identifiability_risk.overall_risk == RiskLevel.MEDIUM


def test_semantic_dataset_contract_roundtrip():
    from marketing_mcp.intelligence.contracts.contract import SemanticDatasetContract
    from marketing_mcp.intelligence.contracts.evidence import ConfidenceLevel, HeuristicConfidence
    from marketing_mcp.intelligence.contracts.profile import StructuralProfile, TemporalProfile
    from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole
    from marketing_mcp.intelligence.contracts.suitability import (
        AnalysisType,
        SuitabilityAssessment,
        SuitabilityVerdict,
    )

    temporal = TemporalProfile(
        date_column="week_start",
        frequency="weekly",
        start_date="2025-01-06",
        end_date="2026-03-02",
        observed_periods=60,
        expected_periods=60,
        missing_periods=[],
        is_continuous=True,
    )
    structural = StructuralProfile(
        rows=60,
        columns=4,
        memory_bytes=4800,
        duplicate_rows=0,
        temporal=temporal,
        column_profiles={},
    )
    target_col = InferredColumn(
        column="revenue",
        role=SemanticRole.TARGET,
        semantic_type="revenue",
        confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=0.98),
    )
    channel_col = InferredColumn(
        column="google_spend",
        role=SemanticRole.MEDIA_CHANNEL,
        semantic_type="spend",
        currency="USD",
        confidence=HeuristicConfidence(level=ConfidenceLevel.HIGH, score=0.95),
    )
    assessment = SuitabilityAssessment(
        analysis_type=AnalysisType.MMM,
        verdict=SuitabilityVerdict.SUITABLE,
        reasons=["Meets all sample size and continuity standards"],
    )

    contract = SemanticDatasetContract(
        dataset_id="test_ds",
        structural=structural,
        target=target_col,
        channels=[channel_col],
        controls=[],
        dimensions=[],
        columns={"revenue": target_col, "google_spend": channel_col},
        issues=[],
        suitability={AnalysisType.MMM: assessment},
    )

    data = contract.model_dump()
    rehydrated = SemanticDatasetContract.model_validate(data)
    assert rehydrated.dataset_id == "test_ds"
    assert rehydrated.target.column == "revenue"
    assert len(rehydrated.channels) == 1
    assert rehydrated.suitability[AnalysisType.MMM].verdict == SuitabilityVerdict.SUITABLE
