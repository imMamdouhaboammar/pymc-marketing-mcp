"""Domain contracts for evidence-aware prior recommendations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from marketing_mcp.schemas.models import ChannelPriorConfig, PriorDistributionConfig

EvidenceType = Literal[
    "experimental_lift",
    "historical_benchmark",
    "domain_bounds",
    "diffuse_uninformative",
]

EvidenceGrade = Literal[
    "empirical_experiment",      # Caller-provided quality_score or SE-derived precision
    "empirical_inconclusive",    # Experiment run but lift ≤ 0 or spend ≤ 0
    "domain_spend_scale",        # Only spend magnitude known; no incrementality proof
    "diffuse_uninformative",     # No experiment, no spend scale
]

IncrementalityStatus = Literal[
    "positive_lift",
    "non_positive_or_inconclusive",
    "not_applicable",
]

ProvenanceType = Literal[
    "caller_quality_score",     # Caller explicitly supplied evidence_quality_score
    "empirical_precision",      # Derived from 1 / (1 + SE) when no quality_score provided
    "policy_default",           # Policy-defined tier for domain/diffuse paths
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

    Scientific provenance invariants:
    - confidence is NEVER fabricated from a magic fallback float.
      It is either the caller-supplied quality_score, or derived from
      experimental precision 1/(1+SE), or documented as a policy-default tier.
    - Non-positive experimental lift (Δy ≤ 0 or Δx ≤ 0) sets
      incrementality_status = "non_positive_or_inconclusive" and disqualifies
      the recommendation from producing an informative positive-ROAS prior.
    - evidence_grade records whether the recommendation is backed by an
      empirical experiment, domain spend scale, or pure diffusion.
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
    evidence_grade: EvidenceGrade = Field(
        description="Scientific quality grade of the underlying evidence"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence score grounded in empirical precision or policy tier. "
            "Never fabricated: see provenance_type for how this value was derived."
        ),
    )
    provenance_type: ProvenanceType = Field(
        description="How the confidence value was derived"
    )
    is_empirically_calibrated: bool = Field(
        description="True only when the recommendation is backed by a positive-lift experiment"
    )
    incrementality_status: IncrementalityStatus = Field(
        default="not_applicable",
        description="Incrementality result of the backing experiment (if any)",
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

    @model_validator(mode="after")
    def _check_calibration_incrementality_consistency(self) -> "PriorRecommendation":
        """Invariant: is_empirically_calibrated=True requires incrementality_status='positive_lift'.

        Without this guard, directly constructed or deserialized recommendations
        could claim empirical calibration while omitting or contradicting the
        incrementality evidence that calibration depends on.
        """
        if self.is_empirically_calibrated and self.incrementality_status != "positive_lift":
            raise ValueError(
                f"is_empirically_calibrated=True requires incrementality_status='positive_lift', "
                f"got incrementality_status='{self.incrementality_status}'. "
                "A recommendation cannot be empirically calibrated without positive-lift evidence."
            )
        return self

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
        description="Channels with zero evidence (no experiment, no spend scale); diffuse prior",
    )
    domain_bounded_channels: list[str] = Field(
        default_factory=list,
        description="Channels with spend-scale bounds but no incrementality experiment",
    )
    provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="Source details and timestamps",
    )
