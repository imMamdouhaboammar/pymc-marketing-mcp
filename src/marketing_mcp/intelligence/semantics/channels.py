"""Channel detection using multi-signal evidence combination."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.evidence import (
    ConfidenceLevel,
    EvidenceSignal,
    HeuristicConfidence,
)
from marketing_mcp.intelligence.contracts.profile import ColumnProfile
from marketing_mcp.intelligence.contracts.semantics import (
    InferredColumn,
    SemanticRole,
    SemanticType,
)

MEDIA_PLATFORMS = (
    "google", "meta", "facebook", "fb", "instagram", "ig",
    "tiktok", "tt", "snapchat", "snap", "linkedin", "li",
    "twitter", "tweet", "x_ads", "x_spend", "x_cost",
    "youtube", "yt", "pinterest", "pin", "bing", "msn",
    "reddit", "amazon", "tv", "radio", "ooh", "dooh",
    "affiliate", "influencer", "display", "programmatic", "ctv", "ott",
)

SPEND_TERMS = ("spend", "cost", "investment", "budget", "media_spend", "paid_media")
IMPRESSION_TERMS = ("impression", "impr", "views", "grp", "trps")
CLICK_TERMS = ("click", "clicks", "cpc", "visits")
NON_CHANNEL_INDICATORS = ("score", "flag", "index", "user", "users", "id", "rank", "weight", "ratio")


def infer_channel_column(
    col_name: str,
    series: pd.Series,
    profile: ColumnProfile,
) -> InferredColumn | None:
    """Evaluates whether a column represents a media channel using combined signals."""
    cl = col_name.lower()
    signals: list[EvidenceSignal] = []
    score = 0.0

    # 1. Reject non-numeric types immediately
    if profile.numeric is None:
        return None

    num = profile.numeric

    import re
    tokens = set(re.findall(r"[a-z0-9]+", cl))

    # 2. Strong negative signals: non-channel words (e.g. score, flag, users, id)
    # Check if a non-channel indicator is present without explicit spend/cost indicator
    has_non_channel_word = any(ind in tokens for ind in NON_CHANNEL_INDICATORS)
    has_spend_term = any(t in tokens for t in SPEND_TERMS) or any(t in cl for t in ("spend", "cost", "investment", "budget"))
    if has_non_channel_word and not has_spend_term:
        return None

    # 3. Non-negativity check
    if num.negatives_count > 0:
        signals.append(
            EvidenceSignal(
                signal_name="contains_negatives",
                direction="negative",
                weight=0.9,
                description=f"{num.negatives_count} negative values observed in media candidate",
            )
        )
        return None
    else:
        signals.append(
            EvidenceSignal(
                signal_name="non_negative",
                direction="positive",
                weight=0.2,
                description="Column values are strictly non-negative",
            )
        )
        score += 0.2

    # 4. Temporal variation check
    if num.std is not None and num.std > 0 and (num.max != num.min):
        signals.append(
            EvidenceSignal(
                signal_name="varies_over_time",
                direction="positive",
                weight=0.2,
                description="Column exhibits variance over time",
                observed_value=num.std,
            )
        )
        score += 0.2
    else:
        signals.append(
            EvidenceSignal(
                signal_name="zero_variance",
                direction="neutral",
                weight=0.1,
                description="Column has zero variance (constant)",
            )
        )
        score += 0.05

    # 5. Spend naming or platform naming match
    is_platform = (
        any(p in tokens for p in MEDIA_PLATFORMS)
        or "x" in tokens
        or any(k in cl for k in ("x_ads", "x_spend", "x_cost"))
        or cl in ("x", "x_ads", "x_spend", "x_cost")
    )
    is_spend = has_spend_term

    if is_spend and is_platform:
        signals.append(
            EvidenceSignal(
                signal_name="spend_and_platform_match",
                direction="positive",
                weight=0.5,
                description="Matches both known media platform and spend keyword",
            )
        )
        score += 0.5
    elif is_spend:
        signals.append(
            EvidenceSignal(
                signal_name="spend_keyword_match",
                direction="positive",
                weight=0.45,
                description="Matches media spend/cost keyword (e.g. influencer_cost, radio_spend)",
            )
        )
        score += 0.45
    elif is_platform:
        # Platform name alone (e.g. google, meta, tiktok) without spend term
        signals.append(
            EvidenceSignal(
                signal_name="platform_name_match",
                direction="positive",
                weight=0.35,
                description="Matches known media platform name",
            )
        )
        score += 0.35
    elif cl.startswith("channel_") or cl.startswith("media_"):
        signals.append(
            EvidenceSignal(
                signal_name="generic_channel_prefix",
                direction="positive",
                weight=0.3,
                description="Matches generic channel naming convention",
            )
        )
        score += 0.3
    else:
        # No media keyword at all
        return None

    # Determine metric type: impressions, clicks, or spend
    if any(t in cl for t in IMPRESSION_TERMS) and not is_spend:
        role = SemanticRole.METRIC_IMPRESSION
        sem_type = SemanticType.IMPRESSIONS
    elif any(t in cl for t in CLICK_TERMS) and not is_spend:
        role = SemanticRole.METRIC_CLICK
        sem_type = SemanticType.CLICKS
    else:
        role = SemanticRole.MEDIA_CHANNEL
        sem_type = SemanticType.SPEND

    final_score = min(1.0, max(0.1, score))
    level = (
        ConfidenceLevel.HIGH
        if final_score >= 0.75
        else ConfidenceLevel.MEDIUM
        if final_score >= 0.5
        else ConfidenceLevel.LOW
    )

    # Inferred currency from suffix if any (e.g. _usd, _eur, _sar)
    currency = None
    for cur in ("usd", "eur", "gbp", "sar", "aed", "cad", "aud", "jpy"):
        if cl.endswith(f"_{cur}"):
            currency = cur.upper()
            break

    return InferredColumn(
        column=col_name,
        role=role,
        semantic_type=str(sem_type.value),
        currency=currency,
        confidence=HeuristicConfidence(level=level, score=round(final_score, 2), evidence=signals),
        user_overridden=False,
    )
