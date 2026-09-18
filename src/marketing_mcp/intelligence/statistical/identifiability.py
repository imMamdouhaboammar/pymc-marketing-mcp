"""Synthesizes statistical risk factors into actionable IdentifiabilityRisk."""

from __future__ import annotations

from marketing_mcp.intelligence.contracts.issues import IssueCode
from marketing_mcp.intelligence.contracts.profile import TemporalProfile
from marketing_mcp.intelligence.contracts.suitability import IdentifiabilityRisk, RiskLevel


def evaluate_identifiability_risk(
    temporal: TemporalProfile,
    collinearity_issues: list[IssueCode],
    variance_issues: list[IssueCode],
    staggered_issues: list[IssueCode],
    sparse_issues: list[IssueCode],
    leakage_issues: list[IssueCode] | None = None,
    break_issues: list[IssueCode] | None = None,
) -> IdentifiabilityRisk:
    """Combines empirical evidence across collinearity, variance, leakage, and history into overall risk."""
    factors: list[str] = []
    mitigations: list[str] = []
    risk_score = 0

    if leakage_issues and IssueCode.TARGET_LEAKAGE in leakage_issues:
        factors.append("Candidate controls exhibit high correlation/leakage with target")
        mitigations.append("Exclude post-treatment controls or verify causal ordering")
        risk_score += 2

    if break_issues and IssueCode.STRUCTURAL_BREAK in break_issues:
        factors.append("Structural regime break detected in baseline target response")
        mitigations.append("Enable time_varying_intercept or segment estimation period")
        risk_score += 1

    if IssueCode.HIGH_CHANNEL_COLLINEARITY in collinearity_issues:
        factors.append("High collinearity between media channels")
        mitigations.append("Supply informative Bayesian priors from incrementality / geo-lift experiments")
        risk_score += 2

    if IssueCode.LOW_VARIATION_CHANNEL in variance_issues:
        factors.append("Near-constant media spend in one or more channels")
        mitigations.append("Test spend pulsing / flighting or pool near-constant channel into baseline")
        risk_score += 2

    if IssueCode.STAGGERED_CHANNEL_LIFECYCLE in staggered_issues:
        factors.append("Staggered or disjoint channel active windows")
        mitigations.append("Align flighting windows across channels to disentangle trend from carryover")
        risk_score += 1

    if IssueCode.SPARSE_CHANNEL in sparse_issues:
        factors.append("Sparse media channels with few active periods")
        mitigations.append("Pool sparse channels into parent media grouping")
        risk_score += 1

    if temporal.observed_periods < 26:
        factors.append(f"Extremely short history ({temporal.observed_periods} periods < recommended 52)")
        mitigations.append("Collect at least 52 periods of observations for robust Bayesian MCMC inference")
        risk_score += 3
    elif temporal.observed_periods < 52:
        factors.append(f"Limited history ({temporal.observed_periods} periods < 52)")
        mitigations.append("Interpret annual seasonality and long adstock carryovers with caution")
        risk_score += 1

    if not temporal.is_continuous:
        factors.append(f"{len(temporal.missing_periods)} missing calendar periods detected in timeline")
        mitigations.append("Impute or align observation periods before fitting MMM to avoid distorted lag weights")
        risk_score += 1

    level = (
        RiskLevel.CRITICAL
        if risk_score >= 5
        else RiskLevel.HIGH
        if risk_score >= 3
        else RiskLevel.MEDIUM
        if risk_score >= 1
        else RiskLevel.LOW
    )

    return IdentifiabilityRisk(
        overall_risk=level,
        factors=factors,
        evidence={"risk_score": risk_score, "observed_periods": temporal.observed_periods},
        mitigations=mitigations,
    )
