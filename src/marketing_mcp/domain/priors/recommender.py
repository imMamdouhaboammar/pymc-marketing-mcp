"""Evidence-aware prior recommendation engine.

Formulates explicit prior recommendations backed by empirical experiments,
historical benchmarks, or weakly informative scale bounds.

Key architecture rules:
1. Never import Simba heuristic constants as defaults.
2. Recommendations never silently mutate a fit request; they are purely informational.
3. Every recommendation exposes alternative priors for prior sensitivity checking.
4. Low/no evidence yields low confidence and explicitly labels channels as unsupported.

Scientific provenance invariants (Iteration N+1 additions):
5. confidence is NEVER fabricated from a magic float fallback.
   - If the caller supplies evidence_quality_score: use it verbatim → provenance_type="caller_quality_score"
   - If no quality_score but SE available: derive 1/(1+SE) → provenance_type="empirical_precision"
   - For domain-bound or diffuse paths: use a documented policy tier → provenance_type="policy_default"
6. Non-positive lift (Δy ≤ 0 or Δx ≤ 0) is never clamped to a positive-ROAS HalfNormal prior.
   It sets evidence_grade="empirical_inconclusive", incrementality_status="non_positive_or_inconclusive",
   and recommends a wide, uninformative prior instead.
7. Channels with only spend scales are "domain_bounded_channels", not "unsupported_channels".
   Only channels with zero evidence and zero spend scale are "unsupported_channels".
"""

from __future__ import annotations

from typing import Any

from marketing_mcp import __version__
from marketing_mcp.domain.priors.contracts import (
    EvidenceGrade,
    IncrementalityStatus,
    PriorAlternative,
    PriorRecommendation,
    PriorRecommendationReport,
    ProvenanceType,
)
from marketing_mcp.schemas.models import PriorDistributionConfig


def _extract_float(record: dict[str, Any], *keys: str, default: float) -> float:
    for k in keys:
        v = record.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return default


def _extract_float_or_none(record: dict[str, Any], *keys: str) -> float | None:
    """Return the first parseable float found, or None if none of the keys exist."""
    for k in keys:
        v = record.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _precision_confidence(sigma: float) -> float:
    """Derive confidence from experimental standard error via 1/(1+SE).

    - SE=0   → confidence=1.0  (perfect precision)
    - SE=1   → confidence=0.5
    - SE=5   → confidence=0.17
    Never exceeds 0.95 to avoid falsely implying gold-standard certainty.
    """
    return min(0.95, 1.0 / (1.0 + max(0.0, sigma)))


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
        Confidence is NEVER fabricated; it is always derived from empirical precision or a
        documented policy-default tier.
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
    domain_bounded_channels: list[str] = []

    for ch in channels:
        ch_recs: list[PriorRecommendation] = []
        ch_exps = exp_by_channel.get(ch, [])

        if ch_exps:
            latest_exp = ch_exps[-1]
            lift_est = _extract_float(
                latest_exp, "measured_incremental_response", "delta_y", default=0.0
            )
            spend_inc = _extract_float(latest_exp, "spend_delta", "delta_x", default=0.0)
            exp_id = latest_exp.get("experiment_id", "lift_test")

            # ── Non-positive lift: never clamp to a positive-ROAS prior ──────────
            if lift_est <= 0.0 or spend_inc <= 0.0:
                evidence_grade: EvidenceGrade = "empirical_inconclusive"
                incrementality_status: IncrementalityStatus = "non_positive_or_inconclusive"
                # Use wide uninformative prior; acknowledge refutation of positive ROAS
                rec_inconclusive = PriorRecommendation(
                    channel=ch,
                    parameter_name="channel_beta",
                    recommended_distribution=PriorDistributionConfig(
                        dist="HalfNormal",
                        kwargs={"sigma": 2.0},  # Wide / uninformative
                    ),
                    evidence_source=f"experiment:{exp_id}",
                    evidence_type="experimental_lift",
                    evidence_grade=evidence_grade,
                    confidence=0.10,
                    provenance_type="policy_default",
                    is_empirically_calibrated=False,
                    incrementality_status=incrementality_status,
                    reason=(
                        f"Experiment '{exp_id}' produced non-positive or inconclusive incrementality "
                        f"(Δy={lift_est:.2f}, Δx={spend_inc:.2f}). "
                        "A positive-ROAS HalfNormal prior is NOT recommended. "
                        "Uninformative prior suggested pending further evidence."
                    ),
                    assumptions=[
                        "Experimental conditions may not adequately represent incremental effect",
                        "Re-run or cross-validate before fitting the model",
                    ],
                    alternative_priors=[
                        PriorAlternative(
                            dist="HalfNormal",
                            kwargs={"sigma": 5.0},
                            reason="Very wide prior allowing full posterior flexibility",
                        ),
                    ],
                    required_prior_predictive_checks=[
                        "Prior predictive must be reviewed before fitting given non-positive experimental evidence",
                    ],
                    sensitivity_checks_required=[
                        "Compare posterior under uninformative prior with any future positive-lift evidence",
                    ],
                )
                ch_recs.append(rec_inconclusive)

            else:
                # ── Positive lift: derive confidence from empirical evidence ─────
                caller_quality_score = _extract_float_or_none(
                    latest_exp, "evidence_quality_score"
                )
                # SE is optional; only use precision-derivation when SE is actually present
                sigma_or_none = _extract_float_or_none(latest_exp, "standard_error", "sigma")

                if caller_quality_score is not None:
                    # Verbatim caller score — never modify/round (P3 fix: honor provenance contract)
                    confidence = caller_quality_score
                    provenance_type: ProvenanceType = "caller_quality_score"
                elif sigma_or_none is not None:
                    # SE present: derive precision score 1/(1+SE)
                    confidence = _precision_confidence(sigma_or_none)
                    provenance_type = "empirical_precision"
                else:
                    # SE absent and no caller score: documented policy-default tier
                    # ponytail: 0.30 is a conservative policy tier for experiment-present-but-SE-missing;
                    # upgrade to empirical_precision when SE is captured in the experiment record.
                    confidence = 0.30
                    provenance_type = "policy_default"

                sigma = sigma_or_none if sigma_or_none is not None else 0.0

                observed_roas = lift_est / spend_inc

                rec_beta = PriorRecommendation(
                    channel=ch,
                    parameter_name="channel_beta",
                    recommended_distribution=PriorDistributionConfig(
                        dist="HalfNormal",
                        kwargs={"sigma": round(max(0.2, observed_roas * 1.5), 3)},
                    ),
                    evidence_source=f"experiment:{exp_id}",
                    evidence_type="experimental_lift",
                    evidence_grade="empirical_experiment",
                    # P3 fix: caller_quality_score must be stored verbatim to honor provenance contract.
                    # Only precision-derived and policy-default values are rounded (they are computed floats).
                    confidence=confidence if provenance_type == "caller_quality_score" else round(confidence, 6),
                    provenance_type=provenance_type,
                    is_empirically_calibrated=True,
                    incrementality_status="positive_lift",
                    reason=(
                        f"Calibrated from measured experimental incrementality: "
                        f"observed iROAS ~ {observed_roas:.2f} (SE: {sigma:.2f}). "
                        f"Confidence derived from {'caller-supplied quality score' if provenance_type == 'caller_quality_score' else 'experimental precision 1/(1+SE)'}."
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
            # ── Domain-bounded: only spend magnitude known ──────────────────────
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
                evidence_grade="domain_spend_scale",
                confidence=0.30,
                # ponytail: 0.30 is documented policy-default tier for spend-scale bounds;
                # upgrade to empirical_precision when an experiment is available.
                provenance_type="policy_default",
                is_empirically_calibrated=False,
                incrementality_status="not_applicable",
                reason=(
                    f"Weakly informative prior scaled to historical average spend (${scale:,.0f}) "
                    "to prevent saturation parameter divergence. "
                    "Confidence is a policy-default tier (0.30); no incrementality experiment available."
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
            domain_bounded_channels.append(ch)

        else:
            # ── Completely uninformative / diffuse ──────────────────────────────
            rec_diffuse = PriorRecommendation(
                channel=ch,
                parameter_name="channel_beta",
                recommended_distribution=PriorDistributionConfig(
                    dist="HalfNormal",
                    kwargs={"sigma": 2.0},
                ),
                evidence_source="uninformative_reference",
                evidence_type="diffuse_uninformative",
                evidence_grade="diffuse_uninformative",
                confidence=0.10,
                # ponytail: 0.10 is documented policy-default tier for zero-evidence diffuse priors.
                provenance_type="policy_default",
                is_empirically_calibrated=False,
                incrementality_status="not_applicable",
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
        domain_bounded_channels=domain_bounded_channels,
        provenance={"generator": "PriorRecommendationEngine", "version": __version__},
    )
