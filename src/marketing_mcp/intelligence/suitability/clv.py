"""CLV (Customer Lifetime Value) suitability evaluator."""

from __future__ import annotations

from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole, SemanticType
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    SuitabilityAssessment,
    SuitabilityVerdict,
)


def evaluate_clv_suitability(columns: dict[str, InferredColumn]) -> SuitabilityAssessment:
    """Evaluates whether dataset has transaction-level customer data for BG/NBD and Gamma-Gamma."""
    reasons: list[str] = []
    blockers: list[str] = []

    has_customer_id = any(
        c.role == SemanticRole.IDENTIFIER or c.semantic_type == SemanticType.CUSTOMER_ID.value
        for c in columns.values()
    )
    has_date = any(c.role == SemanticRole.DATE for c in columns.values())
    has_monetary = any(c.role == SemanticRole.TARGET or c.semantic_type in ("revenue", "spend", "order_value") for c in columns.values())

    if not has_customer_id:
        blockers.append("Dataset lacks a customer identifier (e.g. customer_id, user_id) required for cohort CLV")
    if not has_date:
        blockers.append("Dataset lacks transaction dates")
    if not has_monetary:
        blockers.append("Dataset lacks monetary transaction value column")

    if blockers:
        verdict = SuitabilityVerdict.NOT_SUITABLE
    else:
        verdict = SuitabilityVerdict.SUITABLE
        reasons.append("Transaction-level customer purchase records identified")

    return SuitabilityAssessment(
        analysis_type=AnalysisType.CLV,
        verdict=verdict,
        reasons=reasons,
        blockers=blockers,
    )
