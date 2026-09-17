"""Single-market MMM suitability evaluator."""

from __future__ import annotations

from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity
from marketing_mcp.intelligence.contracts.profile import TemporalProfile
from marketing_mcp.intelligence.contracts.semantics import InferredColumn
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    IdentifiabilityRisk,
    RiskLevel,
    SuitabilityAssessment,
    SuitabilityVerdict,
)


def evaluate_mmm_suitability(
    temporal: TemporalProfile,
    target: InferredColumn | None,
    channels: list[InferredColumn],
    issues: list[IntelligenceIssue],
    identifiability_risk: IdentifiabilityRisk | None = None,
) -> SuitabilityAssessment:
    """Determines whether the dataset is suitable, caution-worthy, or blocked for MMM."""
    reasons: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    # 1. Date / Temporal checks
    if not temporal.date_column:
        blockers.append("No timeline or date column found in dataset")
    elif temporal.frequency == "irregular":
        warnings.append("Irregular observation frequency detected; MMM expects regular weekly or daily periods")
    elif temporal.frequency in ("daily", "weekly", "monthly"):
        reasons.append(f"Regular {temporal.frequency} calendar frequency confirmed")

    if temporal.observed_periods < 26:
        blockers.append(f"Fewer than 26 time periods available ({temporal.observed_periods} periods)")
    elif temporal.observed_periods < 52:
        warnings.append(f"Limited history ({temporal.observed_periods} periods < recommended 52)")
    else:
        reasons.append(f"Sufficient historical depth ({temporal.observed_periods} periods)")

    if not temporal.is_continuous:
        warnings.append(f"{len(temporal.missing_periods)} missing calendar periods detected in date range")

    # 2. Target checks
    if not target:
        blockers.append("No outcome KPI or target column identified")
    else:
        reasons.append(f"Identified primary target: '{target.column}' ({target.semantic_type})")
        if any("attributed" in s.signal_name.lower() for s in target.confidence.evidence):
            warnings.append(f"Target '{target.column}' appears to be platform-attributed revenue, not total business revenue")

    # 3. Media Channels checks
    if not channels:
        blockers.append("No media channel spend columns identified")
    else:
        reasons.append(f"Identified {len(channels)} media channel(s): {[c.column for c in channels]}")

    # 4. Issue Severity rollup
    for iss in issues:
        if iss.blocking:
            blockers.append(f"[{iss.code}] {iss.summary}")
        elif iss.severity in (IssueSeverity.HIGH, IssueSeverity.WARNING):
            warnings.append(f"[{iss.code}] {iss.summary}")

    # 5. Verdict assignment
    if blockers:
        verdict = SuitabilityVerdict.NOT_SUITABLE
    elif any(iss.code == IssueCode.MIXED_CONVERSION_SEMANTICS for iss in issues):
        verdict = SuitabilityVerdict.REQUIRES_TRANSFORMATION
        recommendations.append("Filter dataset by campaign objective before fitting revenue MMM")
    elif warnings or (identifiability_risk and identifiability_risk.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)):
        verdict = SuitabilityVerdict.SUITABLE_WITH_CAUTION
    else:
        verdict = SuitabilityVerdict.SUITABLE

    return SuitabilityAssessment(
        analysis_type=AnalysisType.MMM,
        verdict=verdict,
        reasons=reasons,
        blockers=blockers,
        warnings=warnings,
        recommended_transformations=recommendations,
        identifiability_risk=identifiability_risk,
    )
