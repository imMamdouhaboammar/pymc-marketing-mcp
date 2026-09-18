"""Unified column role resolution engine with user override precedence."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.evidence import (
    ConfidenceLevel,
    EvidenceSignal,
    HeuristicConfidence,
)
from marketing_mcp.intelligence.contracts.profile import StructuralProfile
from marketing_mcp.intelligence.contracts.semantics import (
    InferredColumn,
    SemanticRole,
    SemanticType,
)

from .channels import infer_channel_column
from .targets import infer_target_column


def infer_all_column_roles(
    df: pd.DataFrame,
    profile: StructuralProfile,
    user_overrides: dict[str, dict] | None = None,
) -> dict[str, InferredColumn]:
    """Resolves semantic roles for every column, strictly honoring user overrides first."""
    user_overrides = user_overrides or {}
    results: dict[str, InferredColumn] = {}

    for col in df.columns:
        col_prof = profile.column_profiles.get(col)
        if col_prof is None:
            continue

        # 1. User overrides take absolute precedence
        if col in user_overrides:
            ov = user_overrides[col]
            role = ov.get("role", SemanticRole.UNKNOWN)
            sem_type = ov.get("semantic_type", SemanticType.UNKNOWN.value)
            currency = ov.get("currency")
            results[col] = InferredColumn(
                column=col,
                role=role,
                semantic_type=str(sem_type),
                currency=currency,
                confidence=HeuristicConfidence(
                    level=ConfidenceLevel.HIGH,
                    score=1.0,
                    evidence=[
                        EvidenceSignal(
                            signal_name="user_override",
                            direction="positive",
                            weight=1.0,
                            description=f"User explicitly designated '{col}' as {role}",
                        )
                    ],
                ),
                user_overridden=True,
            )
            continue

        # 2. Date column check
        if col == profile.temporal.date_column:
            results[col] = InferredColumn(
                column=col,
                role=SemanticRole.DATE,
                semantic_type="date",
                confidence=HeuristicConfidence(
                    level=ConfidenceLevel.HIGH,
                    score=0.98,
                    evidence=[
                        EvidenceSignal(
                            signal_name="temporal_date_column",
                            direction="positive",
                            weight=0.98,
                            description="Identified as primary timeline date column",
                        )
                    ],
                ),
                user_overridden=False,
            )
            continue

        # 3. Target candidate check
        target_cand = infer_target_column(col, df[col], col_prof)
        if target_cand is not None:
            results[col] = target_cand
            continue

        # 4. Media channel check
        channel_cand = infer_channel_column(col, df[col], col_prof)
        if channel_cand is not None:
            results[col] = channel_cand
            continue

        # 5. Geographic/market dimension check
        cl = col.lower()
        if any(g in cl for g in ["market", "country", "geo", "region", "state", "city", "segment"]):
            results[col] = InferredColumn(
                column=col,
                role=SemanticRole.DIMENSION,
                semantic_type=SemanticType.GEOGRAPHY.value,
                confidence=HeuristicConfidence(
                    level=ConfidenceLevel.HIGH,
                    score=0.90,
                    evidence=[
                        EvidenceSignal(
                            signal_name="dimension_geo_keyword",
                            direction="positive",
                            weight=0.9,
                            description="Column matches geographic dimension pattern",
                        )
                    ],
                ),
                user_overridden=False,
            )
            continue

        # 6. Control variables check (pricing, discounts, promotions, holidays)
        if any(c in cl for c in ["discount", "price", "promo", "holiday", "season", "competitor", "macro"]):
            results[col] = InferredColumn(
                column=col,
                role=SemanticRole.CONTROL,
                semantic_type=SemanticType.DISCOUNT.value if "discount" in cl or "promo" in cl else SemanticType.PRICE.value,
                confidence=HeuristicConfidence(
                    level=ConfidenceLevel.MEDIUM,
                    score=0.75,
                    evidence=[
                        EvidenceSignal(
                            signal_name="control_keyword",
                            direction="positive",
                            weight=0.75,
                            description="Column matches known marketing control variable pattern",
                        )
                    ],
                ),
                user_overridden=False,
            )
            continue

        # 7. Identifier check (id, customer, account)
        if any(i in cl for i in ["id", "customer", "account", "user_id", "cookie"]):
            results[col] = InferredColumn(
                column=col,
                role=SemanticRole.IDENTIFIER,
                semantic_type=SemanticType.CUSTOMER_ID.value if "customer" in cl else "identifier",
                confidence=HeuristicConfidence(
                    level=ConfidenceLevel.HIGH,
                    score=0.85,
                    evidence=[
                        EvidenceSignal(
                            signal_name="identifier_pattern",
                            direction="positive",
                            weight=0.85,
                            description="Column matches entity or customer identifier",
                        )
                    ],
                ),
                user_overridden=False,
            )
            continue

        # 8. Fallback
        results[col] = InferredColumn(
            column=col,
            role=SemanticRole.METADATA if col_prof.categorical else SemanticRole.UNKNOWN,
            semantic_type=SemanticType.GENERIC_CATEGORICAL.value if col_prof.categorical else SemanticType.GENERIC_NUMERIC.value,
            confidence=HeuristicConfidence(
                level=ConfidenceLevel.LOW,
                score=0.3,
                evidence=[EvidenceSignal(signal_name="default_fallback", direction="neutral", weight=0.3, description="No strong semantic pattern detected")],
            ),
            user_overridden=False,
        )

    return results
