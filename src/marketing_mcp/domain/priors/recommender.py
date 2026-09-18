"""Evidence-aware prior recommendation engine.

Formulates explicit prior recommendations backed by empirical experiments,
historical benchmarks, or weakly informative scale bounds.

Key architecture rules:
1. Never import Simba heuristic constants as defaults.
2. Recommendations never silently mutate a fit request; they are purely informational.
3. Every recommendation exposes alternative priors for prior sensitivity checking.
4. Low/no evidence yields low confidence and explicitly labels channels as unsupported.
"""

from __future__ import annotations

from typing import Any

from marketing_mcp.domain.priors.contracts import (
    PriorAlternative,
    PriorRecommendation,
    PriorRecommendationReport,
)
from marketing_mcp.schemas.models import PriorDistributionConfig


def recommend_priors_for_channels(
    channels: list[str],
    spend_scales: dict[str, float] | None = None,
    experiments: list[dict[str, Any]] | None = None,
    dataset_id: str | None = None,
) -> PriorRecommendationReport:
    """Recommend Bayesian prior distributions for specified marketing channels.

    Parameters
    ----------
    channels:
        List of channel names to evaluate.
    spend_scales:
        Optional mapping of channel to mean or median spend level for scale calibration.
    experiments:
        Optional list of experimental lift test records (e.g. from Experiment Evidence Registry).
    dataset_id:
        Optional registered dataset ID for provenance.

    Returns
    -------
    PriorRecommendationReport
        Explicit recommendations with confidence, assumptions, alternatives, and validation checks.
    """
    spend_scales = spend_scales or {}
    experiments = experiments or []

    exp_by_channel: dict[str, list[dict[str, Any]]] = {}
    for exp in experiments:
        ch = exp.get("channel")
        if ch:
            exp_by_channel.setdefault(ch, []).append(exp)

    recommendations: dict[str, list[PriorRecommendation]] = {}
    unsupported_channels: list[str] = []

    for ch in channels:
        ch_recs: list[PriorRecommendation] = []
        ch_exps = exp_by_channel.get(ch, [])

        if ch_exps:
            # Evidence-backed: experimental lift test available
            latest_exp = ch_exps[-1]
            lift_est = float(latest_exp.get("delta_y", 1.0))
            spend_inc = float(latest_exp.get("delta_x", 1.0))
            sigma = float(latest_exp.get("sigma", 0.5))
            observed_roas = max(0.01, lift_est / max(1.0, spend_inc))

            # Calibrate a HalfNormal or Gamma prior around observed ROAS
            # Standard error scaled by experiment uncertainty
            rec_beta = PriorRecommendation(
                channel=ch,
                parameter_name="channel_beta",
                recommended_distribution=PriorDistributionConfig(
                    dist="HalfNormal",
                    kwargs={"sigma": round(max(0.2, observed_roas * 1.5), 3)},
                ),
                evidence_source=f"experiment:{latest_exp.get('experiment_id', 'lift_test')}",
                evidence_type="experimental_lift",
                confidence=0.85,
                reason=(
                    f"Calibrated from measured experimental incrementality: "
                    f"observed iROAS ~ {observed_roas:.2f} (SE: {sigma:.2f})."
                ),
                assumptions=[
                    "Experiment test period represents current market efficiency",
                    "Geographic / audience treatment conditions generalize to aggregate channel",
                ],
                alternative_priors=[
                    PriorAlternative(
                        dist="Gamma",
                        kwargs={"alpha": 3.0, "beta": round(3.0 / observed_roas, 3)},
                        reason="Informative Gamma centering probability mass closer to experimental mean",
                    ),
                    PriorAlternative(
                        dist="HalfNormal",
                        kwargs={"sigma": round(max(0.5, observed_roas * 3.0), 3)},
                        reason="Wider HalfNormal allowing posterior more flexibility to deviate from experiment",
                    ),
                ],
                required_prior_predictive_checks=[
                    f"Verify simulated 95% credible interval for '{ch}' ROAS includes {observed_roas:.2f}",
                    "Ensure prior predictive does not predict negative incremental response",
                ],
                sensitivity_checks_required=[
                    "Run evaluate_prior_sensitivity comparing HalfNormal vs Gamma alternative",
                ],
            )
            ch_recs.append(rec_beta)

        elif ch in spend_scales and spend_scales[ch] > 0:
            # Scale-bounded: only spend magnitude is known, no incrementality proof
            scale = spend_scales[ch]
            rec_sat = PriorRecommendation(
                channel=ch,
                parameter_name="saturation_lam",
                recommended_distribution=PriorDistributionConfig(
                    dist="Gamma",
                    kwargs={"alpha": 2.0, "beta": round(2.0 / scale, 6)},
                ),
                evidence_source="historical_spend_scale",
                evidence_type="domain_bounds",
                confidence=0.50,
                reason=(
                    f"Weakly informative prior scaled to historical average spend (${scale:,.0f}) "
                    "to prevent saturation parameter divergence."
                ),
                assumptions=[
                    "Historical spend scale is within an order of magnitude of diminishing returns threshold",
                ],
                alternative_priors=[
                    PriorAlternative(
                        dist="HalfNormal",
                        kwargs={"sigma": round(scale * 2.0, 2)},
                        reason="Diffuse half-normal permitting saturation threshold anywhere up to 4x mean spend",
                    ),
                ],
                required_prior_predictive_checks=[
                    "Prior predictive draw distribution covers zero to 3x historical spend",
                ],
                sensitivity_checks_required=[
                    "Verify posterior saturation point does not peg at prior mode",
                ],
            )
            ch_recs.append(rec_sat)
            unsupported_channels.append(ch)

        else:
            # Completely uninformative / diffuse
            rec_diffuse = PriorRecommendation(
                channel=ch,
                parameter_name="channel_beta",
                recommended_distribution=PriorDistributionConfig(
                    dist="HalfNormal",
                    kwargs={"sigma": 2.0},
                ),
                evidence_source="uninformative_reference",
                evidence_type="diffuse_uninformative",
                confidence=0.20,
                reason="No experimental or spend scale evidence available. Weakly regularizing diffuse prior.",
                assumptions=["Channel response is non-negative"],
                alternative_priors=[
                    PriorAlternative(
                        dist="HalfNormal",
                        kwargs={"sigma": 5.0},
                        reason="Wide uninformative prior for large unconstrained parameter search",
                    ),
                ],
                required_prior_predictive_checks=[
                    "Prior predictive checks must be reviewed for extreme output plausibility",
                ],
                sensitivity_checks_required=[
                    "Prior sensitivity must be evaluated before taking budget decisions",
                ],
            )
            ch_recs.append(rec_diffuse)
            unsupported_channels.append(ch)

        recommendations[ch] = ch_recs

    return PriorRecommendationReport(
        dataset_id=dataset_id,
        recommendations=recommendations,
        unsupported_channels=unsupported_channels,
        provenance={"generator": "PriorRecommendationEngine", "version": "1.0.0"},
    )
