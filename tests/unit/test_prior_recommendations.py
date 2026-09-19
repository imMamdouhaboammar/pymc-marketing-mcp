"""Unit tests for evidence-aware prior recommendations (T4).

Fast tests — zero MCMC sampling required.
Requirements verified:
- recommendations never silently mutate a fit request
- user override always remains explicit
- unsupported evidence yields low confidence
- prior sensitivity alternatives are systematically provided
- conversion to ChannelPriorConfig produces valid spec objects
"""

from __future__ import annotations

from marketing_mcp.domain.priors import (
    PriorRecommendationReport,
    recommend_priors_for_channels,
)
from marketing_mcp.schemas.models import ChannelPriorConfig, FitMMMInput


class TestPriorRecommendationEngine:
    def test_experimental_lift_produces_high_confidence_prior(self):
        channels = ["meta_spend", "search_spend"]
        experiments = [
            {
                "experiment_id": "geo_lift_meta_2025",
                "channel": "meta_spend",
                "delta_x": 10000.0,
                "delta_y": 25000.0,  # iROAS ~ 2.5
                "sigma": 0.10,  # SE=0.10 → precision-derived confidence 1/(1+0.10) ≈ 0.91
            }
        ]

        report = recommend_priors_for_channels(
            channels=channels,
            experiments=experiments,
            spend_scales={"meta_spend": 10000.0, "search_spend": 8000.0},
        )

        assert isinstance(report, PriorRecommendationReport)
        assert "meta_spend" in report.recommendations
        meta_recs = report.recommendations["meta_spend"]
        assert len(meta_recs) == 1
        rec = meta_recs[0]

        assert rec.evidence_type == "experimental_lift"
        assert rec.confidence >= 0.80
        assert "experiment:geo_lift_meta_2025" in rec.evidence_source
        assert len(rec.alternative_priors) >= 2
        assert len(rec.required_prior_predictive_checks) >= 1
        assert len(rec.sensitivity_checks_required) >= 1

        # Check conversion to valid ChannelPriorConfig
        cfg = rec.to_channel_prior_config()
        assert isinstance(cfg, ChannelPriorConfig)
        assert "channel_beta" in cfg.priors
        assert cfg.priors["channel_beta"].dist == "HalfNormal"

    def test_unsupported_channels_yield_low_confidence(self):
        channels = ["unknown_channel"]
        report = recommend_priors_for_channels(channels=channels)

        assert "unknown_channel" in report.unsupported_channels
        rec = report.recommendations["unknown_channel"][0]
        assert rec.confidence <= 0.30
        assert rec.evidence_type == "diffuse_uninformative"

    def test_recommendation_does_not_mutate_fit_request_silently(self):
        """Invariant: FitMMMInput without channel_priors remains unmodified."""
        channels = ["tv_spend", "digital_spend"]
        report = recommend_priors_for_channels(channels=channels)

        # Baseline request without priors
        fit_input = FitMMMInput(
            dataset_id="test_ds",
            date_column="date",
            target_column="sales",
            channel_columns=channels,
        )
        assert fit_input.channel_priors == {}

        # User must explicitly adopt recommendation
        adopted_priors = {
            ch: report.recommendations[ch][0].to_channel_prior_config()
            for ch in channels
        }
        fit_input_explicit = FitMMMInput(
            dataset_id="test_ds",
            date_column="date",
            target_column="sales",
            channel_columns=channels,
            channel_priors=adopted_priors,
        )
        assert len(fit_input_explicit.channel_priors) == 2
        assert "tv_spend" in fit_input_explicit.channel_priors
        assert "digital_spend" in fit_input_explicit.channel_priors

    def test_alternative_priors_support_sensitivity_comparison(self):
        channels = ["meta_spend"]
        experiments = [
            {
                "experiment_id": "exp_1",
                "channel": "meta_spend",
                "delta_x": 5000.0,
                "delta_y": 10000.0,
                "sigma": 0.2,
            }
        ]
        report = recommend_priors_for_channels(channels=channels, experiments=experiments)
        rec = report.recommendations["meta_spend"][0]

        # Recommended vs alternative distributions are distinct
        alt_dists = [alt.dist for alt in rec.alternative_priors]
        assert "Gamma" in alt_dists or "HalfNormal" in alt_dists
        for alt in rec.alternative_priors:
            assert alt.reason != ""
            assert len(alt.kwargs) > 0

    def test_experiment_record_schema_parity(self):
        channels = ["meta_spend"]
        experiments = [
            {
                "experiment_id": "exp_canonical",
                "channel": "meta_spend",
                "spend_delta": 5000.0,
                "measured_incremental_response": 12500.0,
                "standard_error": 0.25,
                "evidence_quality_score": 0.90,
            }
        ]
        report = recommend_priors_for_channels(channels=channels, experiments=experiments)
        rec = report.recommendations["meta_spend"][0]
        assert rec.evidence_type == "experimental_lift"
        assert rec.confidence == 0.90
        assert "experiment:exp_canonical" in rec.evidence_source
        assert rec.recommended_distribution.kwargs["sigma"] > 0
        assert rec.is_empirically_calibrated is True
        assert rec.incrementality_status == "positive_lift"

    def test_non_positive_lift_experiment_rejects_positive_halfnormal_roas_prior(self):
        """Invariant: Experiments showing zero or negative lift must not be clamped to positive ROAS."""
        channels = ["meta_spend"]
        experiments = [
            {
                "experiment_id": "exp_failed_lift",
                "channel": "meta_spend",
                "spend_delta": 10000.0,
                "measured_incremental_response": -500.0,  # Negative lift
                "standard_error": 0.50,
            }
        ]
        report = recommend_priors_for_channels(channels=channels, experiments=experiments)
        rec = report.recommendations["meta_spend"][0]

        assert rec.incrementality_status == "non_positive_or_inconclusive"
        assert rec.evidence_grade == "empirical_inconclusive"
        # Must not claim observed positive ROAS or recommend informative positive ROAS prior
        assert "non-positive" in rec.reason.lower() or "inconclusive" in rec.reason.lower()
        assert rec.recommended_distribution.dist != "HalfNormal" or rec.recommended_distribution.kwargs.get("sigma", 0) >= 2.0

    def test_noisy_experiment_yields_low_precision_confidence(self):
        """Signal-to-noise ratio must drive confidence when no caller quality score is passed."""
        channels = ["noisy_channel"]
        experiments = [
            {
                "experiment_id": "exp_noisy",
                "channel": "noisy_channel",
                "spend_delta": 10000.0,
                "measured_incremental_response": 1000.0,  # iROAS = 0.1
                "standard_error": 5.0,  # Very high SE relative to effect
            }
        ]
        report = recommend_priors_for_channels(channels=channels, experiments=experiments)
        rec = report.recommendations["noisy_channel"][0]
        # Should not get the legacy fake 0.85 score!
        assert rec.confidence < 0.50
        assert rec.provenance_type == "empirical_precision"

    def test_domain_spend_scale_channels_separated_from_unsupported_diffuse(self):
        """Channels with spend scales are domain-bounded, while channels with zero info are unsupported."""
        channels = ["brand_spend", "unknown_channel"]
        report = recommend_priors_for_channels(
            channels=channels,
            spend_scales={"brand_spend": 50000.0},
        )
        assert "brand_spend" in report.domain_bounded_channels
        assert "unknown_channel" in report.unsupported_channels
        brand_rec = report.recommendations["brand_spend"][0]
        assert brand_rec.evidence_grade == "domain_spend_scale"
        assert brand_rec.is_empirically_calibrated is False

