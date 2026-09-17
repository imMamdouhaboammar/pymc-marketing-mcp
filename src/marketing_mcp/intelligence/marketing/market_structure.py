"""Market dimensionality, heterogeneity, and strategy recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pandas as pd
from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity


@dataclass
class MarketStructureReport:
    market_count: int = 1
    dimension_columns: list[str] | None = None
    markets: list[str] | None = None
    observations_per_market: dict[str, int] | None = None
    recommended_strategy: str = "pooled_global"  # pooled_global, hierarchical_panel, separate_models
    issue: IntelligenceIssue | None = None


def analyze_market_structure(
    df: pd.DataFrame,
    date_column: str,
    dims: list[str] | None = None,
) -> MarketStructureReport:
    """Analyzes dimensional segmentation and recommends pooled, separate, or hierarchical modeling."""
    dims = dims or []
    # If dims not provided, look for geographic columns
    if not dims:
        for col in df.columns:
            if col == date_column:
                continue
            cl = col.lower()
            if any(k in cl for k in ["market", "country", "geo", "region", "state", "city", "segment"]):
                uniques = df[col].dropna().unique()
                if 2 <= len(uniques) <= 50:
                    issue = IntelligenceIssue(
                        code=IssueCode.MARKET_HETEROGENEITY,
                        severity=IssueSeverity.WARNING,
                        summary=f"Dataset contains market/geographic column '{col}' with {len(uniques)} segments, but dims=[] was supplied",
                        evidence={"column": col, "unique_markets": [str(x) for x in uniques[:10]]},
                        affected_columns=[col],
                        why_it_matters="A single pooled global model can obscure significant geographic heterogeneity in media effectiveness",
                        recommended_action=f"Specify dims=['{col}'] to enable hierarchical panel MMM or fit separate models per market",
                        blocking=False,
                    )
                    return MarketStructureReport(
                        market_count=len(uniques),
                        dimension_columns=[col],
                        markets=[str(x) for x in uniques],
                        recommended_strategy="hierarchical_panel",
                        issue=issue,
                    )
        return MarketStructureReport(market_count=1, recommended_strategy="pooled_global")

    # Dims provided: evaluate sufficiency
    primary_dim = dims[0]
    uniques = df[primary_dim].dropna().unique()
    market_count = len(uniques)
    counts = df[primary_dim].value_counts().to_dict()
    obs_per_market = {str(k): int(v) for k, v in counts.items()}
    min_obs = min(obs_per_market.values()) if obs_per_market else 0

    if min_obs >= 52:
        strategy = "separate_models"
    elif min_obs >= 20 and market_count >= 2:
        strategy = "hierarchical_panel"
    else:
        strategy = "pooled_global"

    return MarketStructureReport(
        market_count=market_count,
        dimension_columns=dims,
        markets=[str(x) for x in uniques],
        observations_per_market=obs_per_market,
        recommended_strategy=strategy,
        issue=None,
    )
