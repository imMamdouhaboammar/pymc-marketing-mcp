"""Target detection and suitability for revenue/conversion modeling."""

from __future__ import annotations

import pandas as pd
from marketing_mcp.intelligence.contracts.evidence import (
    ConfidenceLevel,
    EvidenceSignal,
    HeuristicConfidence,
)
from marketing_mcp.intelligence.contracts.profile import ColumnProfile
from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole, SemanticType

TARGET_KEYWORDS = ("revenue", "sales", "orders", "conversions", "turnover", "gmv", "gsv", "nsv", "target")
ATTRIBUTED_KEYWORDS = ("attributed", "platform_", "meta_", "google_", "ga4_", "reported_", "pixel_")


def infer_target_column(
    col_name: str,
    series: pd.Series,
    profile: ColumnProfile,
) -> InferredColumn | None:
    """Evaluates whether a column represents a candidate target outcome KPI."""
    cl = col_name.lower()
    if profile.numeric is None:
        return None

    # Check for target keyword match
    matched_keyword = next((k for k in TARGET_KEYWORDS if k in cl), None)
    if not matched_keyword:
        return None

    signals: list[EvidenceSignal] = []
    score = 0.5
    signals.append(
        EvidenceSignal(
            signal_name=f"target_keyword_{matched_keyword}",
            direction="positive",
            weight=0.5,
            description=f"Column name matches target outcome keyword '{matched_keyword}'",
        )
    )

    # Check for non-negativity
    if profile.numeric.negatives_count == 0:
        score += 0.2
        signals.append(
            EvidenceSignal(
                signal_name="non_negative_target",
                direction="positive",
                weight=0.2,
                description="Target values are non-negative",
            )
        )

    # Check variance
    if profile.numeric.std is not None and profile.numeric.std > 0:
        score += 0.2
        signals.append(
            EvidenceSignal(
                signal_name="target_has_variance",
                direction="positive",
                weight=0.2,
                description="Target column exhibits numeric variance over time",
            )
        )

    # Check for attribution contamination
    is_attributed = any(att in cl for att in ATTRIBUTED_KEYWORDS)
    if is_attributed:
        signals.append(
            EvidenceSignal(
                signal_name="ATTRIBUTED_REVENUE_TARGET",
                direction="neutral",
                weight=0.4,
                description="Column indicates platform-attributed or pixel-reported revenue rather than independent total business revenue",
            )
        )

    currency = None
    for cur in ("usd", "eur", "gbp", "sar", "aed", "cad", "aud", "jpy"):
        if cl.endswith(f"_{cur}"):
            currency = cur.upper()
            break

    final_score = min(1.0, max(0.1, score))
    level = ConfidenceLevel.HIGH if final_score >= 0.75 else ConfidenceLevel.MEDIUM

    return InferredColumn(
        column=col_name,
        role=SemanticRole.TARGET,
        semantic_type=SemanticType.REVENUE.value if "revenue" in cl or "sales" in cl or "gmv" in cl else SemanticType.CONVERSIONS.value,
        currency=currency,
        confidence=HeuristicConfidence(level=level, score=round(final_score, 2), evidence=signals),
        user_overridden=False,
    )
