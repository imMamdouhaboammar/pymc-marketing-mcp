"""Campaign objective and conversion semantics analysis."""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity

UPPER_FUNNEL = ("aware", "reach", "brand", "view", "traffic", "engagement", "video")
LOWER_FUNNEL = ("sale", "purchase", "lead", "conversion", "revenue", "install", "order")


@dataclass
class ObjectiveAnalysis:
    has_objectives: bool = False
    has_mixed_objectives: bool = False
    has_zero_revenue_awareness: bool = False
    objective_column: str | None = None
    detected_objectives: list[str] | None = None
    issue: IntelligenceIssue | None = None


def analyze_campaign_objectives(df: pd.DataFrame) -> ObjectiveAnalysis:
    """Inspects dataset for mixed campaign objectives and non-revenue awareness semantics."""
    obj_col = None
    for col in df.columns:
        cl = col.lower()
        if any(k in cl for k in ["objective", "campaign_type", "funnel", "goal"]):
            obj_col = col
            break

    if not obj_col:
        return ObjectiveAnalysis()

    vals = [str(v).lower() for v in df[obj_col].dropna().unique()]
    has_upper = any(any(u in v for u in UPPER_FUNNEL) for v in vals)
    has_lower = any(any(l in v for l in LOWER_FUNNEL) for v in vals)
    has_mixed = has_upper and has_lower

    # Check for zero revenue under awareness campaigns
    has_zero_rev_awareness = False
    rev_cols = [c for c in df.columns if any(k in c.lower() for k in ["revenue", "sales", "target"])]
    if rev_cols and has_upper:
        for r_col in rev_cols:
            upper_rows = df[df[obj_col].astype(str).str.lower().apply(lambda v: any(u in v for u in UPPER_FUNNEL))]
            if len(upper_rows) > 0 and (upper_rows[r_col].fillna(0) == 0).all():
                has_zero_rev_awareness = True
                break

    issue = None
    if has_mixed:
        issue = IntelligenceIssue(
            code=IssueCode.MIXED_CONVERSION_SEMANTICS,
            severity=IssueSeverity.WARNING,
            summary=f"Column '{obj_col}' mixes upper-funnel awareness and lower-funnel sales/conversion campaigns",
            evidence={
                "objective_column": obj_col,
                "detected_objectives": vals,
                "has_zero_revenue_awareness": has_zero_rev_awareness,
            },
            affected_columns=[obj_col],
            why_it_matters="Pooling non-revenue upper-funnel media with direct sales campaigns distorts adstock decay and ROI response",
            recommended_action="Filter dataset to conversion-oriented campaigns or model awareness as an upstream mediator KPI",
            blocking=False,
        )

    return ObjectiveAnalysis(
        has_objectives=True,
        has_mixed_objectives=has_mixed,
        has_zero_revenue_awareness=has_zero_rev_awareness,
        objective_column=obj_col,
        detected_objectives=vals,
        issue=issue,
    )
