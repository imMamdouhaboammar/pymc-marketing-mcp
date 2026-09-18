"""Channel spend variance and coefficient of variation analysis."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from marketing_mcp.intelligence.contracts.issues import IntelligenceIssue, IssueCode, IssueSeverity


@dataclass
class SpendVarianceReport:
    channel_cv: dict[str, float] = field(default_factory=dict)
    issues: list[IntelligenceIssue] = field(default_factory=list)


def assess_spend_variance(df: pd.DataFrame, channel_columns: list[str]) -> SpendVarianceReport:
    """Calculates coefficient of variation (std/mean) and identifies near-constant spend."""
    cv_dict: dict[str, float] = {}
    issues: list[IntelligenceIssue] = []

    for ch in channel_columns:
        if ch not in df.columns:
            continue
        s = pd.to_numeric(df[ch], errors="coerce").dropna()
        if len(s) == 0:
            continue

        mean = float(s.mean())
        std = float(s.std()) if len(s) > 1 else 0.0
        cv = round(std / max(1e-6, mean), 4) if mean > 0 else 0.0
        cv_dict[ch] = cv

        if cv < 0.05 or s.nunique() <= 1:
            issues.append(
                IntelligenceIssue(
                    code=IssueCode.LOW_VARIATION_CHANNEL,
                    severity=IssueSeverity.WARNING,
                    summary=f"Channel '{ch}' has near-constant spend (CV={cv:.3f}, std={std:.2f})",
                    evidence={"channel": ch, "coefficient_of_variation": cv, "std": std, "mean": mean},
                    affected_columns=[ch],
                    why_it_matters="Near-constant media spend prevents identifying adstock decay and saturation curvature",
                    recommended_action="Introduce spend pulsation or calibrate channel with incrementality experiments",
                    blocking=False,
                )
            )

    return SpendVarianceReport(channel_cv=cv_dict, issues=issues)
