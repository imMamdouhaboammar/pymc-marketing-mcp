"""Domain contracts for evidence-aware prior recommendations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from marketing_mcp.schemas.models import ChannelPriorConfig, PriorDistributionConfig

EvidenceType = Literal[
    "experimental_lift",
    "historical_benchmark",
    "domain_bounds",
    "diffuse_uninformative",
]


class PriorAlternative(BaseModel):
    """An alternative candidate prior specification."""

    dist: str = Field(description="Distribution family, e.g. Beta, Gamma, HalfNormal, LogNormal")
    kwargs: dict[str, float] = Field(description="Alternative parameter values")
    reason: str = Field(description="Why this alternative could be considered")


class PriorRecommendation(BaseModel):
    """An explicit, evidence-backed prior recommendation.

    Design invariant (T4): Recommendations are never applied silently.
    They require explicit user adoption into FitMMMInput.channel_priors.
    """

    channel: str = Field(description="Channel target for this recommendation")
    parameter_name: str = Field(
        description="Target parameter, e.g. adstock_alpha, saturation_lam, channel_beta"
    )
    recommended_distribution: PriorDistributionConfig = Field(
        description="Recommended prior family and parameterization"
    )
    evidence_source: str = Field(description="Provenance or identifier of supporting evidence")
    evidence_type: EvidenceType = Field(description="Methodological category of evidence")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0=unsupported/diffuse, 1.0=gold-standard experiment)",
    )
    reason: str = Field(description="Statistical and commercial rationale for recommendation")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions under which this prior recommendation is valid",
    )
    alternative_priors: list[PriorAlternative] = Field(
        default_factory=list, description="Candidate alternatives for prior sensitivity testing"
    )
    required_prior_predictive_checks: list[str] = Field(
        default_factory=list,
        description="Prior-predictive validation checks that must pass before model fitting",
    )
    sensitivity_checks_required: list[str] = Field(
        default_factory=list,
        description="Sensitivity verification steps required if this prior is adopted",
    )

    def to_channel_prior_config(self) -> ChannelPriorConfig:
        """Convert recommendation into a typed ChannelPriorConfig for FitMMMInput."""
        return ChannelPriorConfig(
            priors={self.parameter_name: self.recommended_distribution}
        )


class PriorRecommendationReport(BaseModel):
    """Full recommendation bundle across all channels."""

    dataset_id: str | None = None
    recommendations: dict[str, list[PriorRecommendation]] = Field(
        default_factory=dict,
        description="Recommendations keyed by channel name",
    )
    unsupported_channels: list[str] = Field(
        default_factory=list,
        description="Channels with no empirical evidence where uninformative priors are suggested",
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Source details and timestamps",
    )
