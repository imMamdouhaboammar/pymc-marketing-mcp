"""
Unit tests for the Adstock & Saturation Model Zoo (Phase 1 — v0.4.0).

Tests schema validation, factory instantiation, and channel_priors constraints.
All tests use real PyMC-Marketing transform objects — no mocks.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marketing_mcp.schemas.models import (
    AdstockConfig,
    ChannelPriorConfig,
    FitMMMInput,
    SaturationConfig,
)

# ---------------------------------------------------------------------------
# AdstockConfig schema
# ---------------------------------------------------------------------------


class TestAdstockConfig:
    def test_schema_accepts_geometric_default(self):
        cfg = AdstockConfig()
        assert cfg.type == "geometric"
        assert cfg.l_max == 8

    def test_schema_accepts_delayed_adstock(self):
        cfg = AdstockConfig(type="delayed", l_max=12)
        assert cfg.type == "delayed"
        assert cfg.l_max == 12

    def test_schema_accepts_weibull_cdf(self):
        cfg = AdstockConfig(type="weibull_cdf", l_max=16)
        assert cfg.type == "weibull_cdf"

    def test_schema_accepts_weibull_pdf(self):
        cfg = AdstockConfig(type="weibull_pdf", l_max=10)
        assert cfg.type == "weibull_pdf"

    def test_schema_accepts_binomial(self):
        cfg = AdstockConfig(type="binomial", l_max=6)
        assert cfg.type == "binomial"

    def test_schema_accepts_none(self):
        cfg = AdstockConfig(type="none", l_max=1)
        assert cfg.type == "none"

    def test_schema_rejects_unknown_adstock_type(self):
        with pytest.raises(ValidationError) as exc_info:
            AdstockConfig(type="custom_magic")
        assert "custom_magic" in str(exc_info.value) or "type" in str(exc_info.value)

    def test_l_max_lower_bound(self):
        with pytest.raises(ValidationError):
            AdstockConfig(l_max=0)

    def test_l_max_upper_bound(self):
        with pytest.raises(ValidationError):
            AdstockConfig(l_max=53)


# ---------------------------------------------------------------------------
# SaturationConfig schema
# ---------------------------------------------------------------------------


class TestSaturationConfig:
    def test_schema_accepts_logistic_default(self):
        cfg = SaturationConfig()
        assert cfg.type == "logistic"

    def test_schema_accepts_tanh(self):
        assert SaturationConfig(type="tanh").type == "tanh"

    def test_schema_accepts_tanh_baselined(self):
        assert SaturationConfig(type="tanh_baselined").type == "tanh_baselined"

    def test_schema_accepts_michaelis_menten(self):
        assert SaturationConfig(type="michaelis_menten").type == "michaelis_menten"

    def test_schema_accepts_hill(self):
        assert SaturationConfig(type="hill").type == "hill"

    def test_schema_accepts_hill_sigmoid(self):
        assert SaturationConfig(type="hill_sigmoid").type == "hill_sigmoid"

    def test_schema_accepts_inverse_scaled_logistic(self):
        assert SaturationConfig(type="inverse_scaled_logistic").type == "inverse_scaled_logistic"

    def test_schema_accepts_log(self):
        assert SaturationConfig(type="log").type == "log"

    def test_schema_accepts_root(self):
        assert SaturationConfig(type="root").type == "root"

    def test_schema_accepts_none(self):
        assert SaturationConfig(type="none").type == "none"

    def test_schema_rejects_unknown_saturation_type(self):
        with pytest.raises(ValidationError) as exc_info:
            SaturationConfig(type="magic_sigmoid")
        assert "magic_sigmoid" in str(exc_info.value) or "type" in str(exc_info.value)


# ---------------------------------------------------------------------------
# ChannelPriorConfig schema
# ---------------------------------------------------------------------------


class TestChannelPriorConfig:
    def test_channel_prior_with_adstock_only(self):
        cfg = ChannelPriorConfig(adstock=AdstockConfig(type="delayed"))
        assert cfg.adstock is not None
        assert cfg.adstock.type == "delayed"
        assert cfg.saturation is None

    def test_channel_prior_with_saturation_only(self):
        cfg = ChannelPriorConfig(saturation=SaturationConfig(type="hill"))
        assert cfg.saturation is not None
        assert cfg.saturation.type == "hill"
        assert cfg.adstock is None

    def test_channel_prior_with_both(self):
        cfg = ChannelPriorConfig(
            adstock=AdstockConfig(type="weibull_cdf"),
            saturation=SaturationConfig(type="michaelis_menten"),
        )
        assert cfg.adstock.type == "weibull_cdf"
        assert cfg.saturation.type == "michaelis_menten"

    def test_channel_prior_empty_is_valid(self):
        cfg = ChannelPriorConfig()
        assert cfg.adstock is None
        assert cfg.saturation is None


# ---------------------------------------------------------------------------
# FitMMMInput channel_priors validation
# ---------------------------------------------------------------------------


BASE_FIT_KWARGS = {
    "dataset_id": "ds_001",
    "date_column": "date",
    "target_column": "revenue",
    "channel_columns": ["meta", "google", "tiktok"],
    "control_columns": [],
}


class TestFitMMMInputChannelPriors:
    def test_fit_input_accepts_empty_channel_priors(self):
        inp = FitMMMInput(**BASE_FIT_KWARGS)
        assert inp.channel_priors == {}

    def test_fit_input_accepts_valid_channel_prior(self):
        inp = FitMMMInput(
            **BASE_FIT_KWARGS,
            channel_priors={
                "meta": ChannelPriorConfig(adstock=AdstockConfig(type="delayed")),
                "tiktok": ChannelPriorConfig(saturation=SaturationConfig(type="hill")),
            },
        )
        assert "meta" in inp.channel_priors
        assert inp.channel_priors["meta"].adstock.type == "delayed"
        assert "tiktok" in inp.channel_priors

    def test_channel_priors_must_be_subset_of_channels(self):
        """channel_priors keys not in channel_columns must raise ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            FitMMMInput(
                **BASE_FIT_KWARGS,
                channel_priors={
                    "youtube": ChannelPriorConfig(adstock=AdstockConfig(type="delayed")),
                },
            )
        error_text = str(exc_info.value)
        assert "youtube" in error_text or "channel_priors" in error_text

    def test_channel_priors_partial_override_is_valid(self):
        """Only one channel in channel_priors is fine — others use global config."""
        inp = FitMMMInput(
            **BASE_FIT_KWARGS,
            channel_priors={
                "google": ChannelPriorConfig(adstock=AdstockConfig(type="weibull_pdf"))
            },
        )
        assert "google" in inp.channel_priors
        # meta and tiktok should still use global config (not in channel_priors)
        assert "meta" not in inp.channel_priors

    def test_fit_input_global_adstock_type_delayed(self):
        """Global adstock can be set to delayed."""
        inp = FitMMMInput(**BASE_FIT_KWARGS, adstock=AdstockConfig(type="delayed", l_max=10))
        assert inp.adstock.type == "delayed"
        assert inp.adstock.l_max == 10

    def test_fit_input_global_saturation_hill(self):
        """Global saturation can be set to hill."""
        inp = FitMMMInput(**BASE_FIT_KWARGS, saturation=SaturationConfig(type="hill"))
        assert inp.saturation.type == "hill"


# ---------------------------------------------------------------------------
# Adapter factory tests — require real PyMC-Marketing installation
# ---------------------------------------------------------------------------


class TestAdapterFactories:
    @pytest.fixture
    def adapter(self):
        from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter

        return PyMCMarketingAdapter()

    def test_build_adstock_geometric(self, adapter):
        from pymc_marketing.mmm import GeometricAdstock

        obj = adapter._build_adstock({"type": "geometric", "l_max": 8})
        assert isinstance(obj, GeometricAdstock)

    def test_build_adstock_delayed(self, adapter):
        from pymc_marketing.mmm import DelayedAdstock

        obj = adapter._build_adstock({"type": "delayed", "l_max": 10})
        assert isinstance(obj, DelayedAdstock)

    def test_build_adstock_weibull_cdf(self, adapter):
        from pymc_marketing.mmm import WeibullCDFAdstock

        obj = adapter._build_adstock({"type": "weibull_cdf", "l_max": 12})
        assert isinstance(obj, WeibullCDFAdstock)

    def test_build_adstock_weibull_pdf(self, adapter):
        from pymc_marketing.mmm import WeibullPDFAdstock

        obj = adapter._build_adstock({"type": "weibull_pdf", "l_max": 12})
        assert isinstance(obj, WeibullPDFAdstock)

    def test_build_saturation_logistic(self, adapter):
        from pymc_marketing.mmm import LogisticSaturation

        obj = adapter._build_saturation({"type": "logistic"})
        assert isinstance(obj, LogisticSaturation)

    def test_build_saturation_hill(self, adapter):
        from pymc_marketing.mmm import HillSaturation

        obj = adapter._build_saturation({"type": "hill"})
        assert isinstance(obj, HillSaturation)

    def test_build_saturation_michaelis_menten(self, adapter):
        from pymc_marketing.mmm import MichaelisMentenSaturation

        obj = adapter._build_saturation({"type": "michaelis_menten"})
        assert isinstance(obj, MichaelisMentenSaturation)

    def test_build_saturation_tanh_baselined(self, adapter):
        from pymc_marketing.mmm import TanhSaturationBaselined

        obj = adapter._build_saturation({"type": "tanh_baselined"})
        assert isinstance(obj, TanhSaturationBaselined)

    def test_build_adstock_unknown_raises_domain_error(self, adapter):
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError) as exc_info:
            adapter._build_adstock({"type": "magic_decay"})
        assert exc_info.value.code == "INVALID_ADSTOCK_TYPE"

    def test_build_saturation_unknown_raises_domain_error(self, adapter):
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError) as exc_info:
            adapter._build_saturation({"type": "fantasy_curve"})
        assert exc_info.value.code == "INVALID_SATURATION_TYPE"

    def test_build_adstock_defaults_to_geometric_when_empty_dict(self, adapter):
        from pymc_marketing.mmm import GeometricAdstock

        obj = adapter._build_adstock({})
        assert isinstance(obj, GeometricAdstock)

    def test_build_saturation_defaults_to_logistic_when_empty_dict(self, adapter):
        from pymc_marketing.mmm import LogisticSaturation

        obj = adapter._build_saturation({})
        assert isinstance(obj, LogisticSaturation)
