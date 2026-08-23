"""Unit tests for the MMM model configuration builder.

Task 1 contract:
1. `build_mmm_init_kwargs()` and `build_model_config()` construct valid init kwargs for PyMC-Marketing MMM.
2. Channel-specific prior overrides in `channel_priors` produce `Prior` instances with `xarray.DataArray`
   coordinate-aligned parameter arrays matching `channel_columns`.
3. Channels not explicitly overridden receive default prior parameters.
4. Validation fails on unknown channels, unknown prior parameter names, negative values where forbidden,
   or shape mismatches.
"""

from __future__ import annotations

import pytest
import xarray as xr

from marketing_mcp.adapters.mmm_config import (
    build_mmm_init_kwargs,
    build_model_config,
)
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    AdstockConfig,
    ChannelPriorConfig,
    FitMMMInput,
    PriorDistributionConfig,
    SaturationConfig,
)


def test_build_model_config_default_priors():
    channels = ["tv", "radio", "social"]
    config = FitMMMInput(
        dataset_id="ds1",
        date_column="date",
        target_column="sales",
        channel_columns=channels,
    )
    model_config = build_model_config(config)
    assert isinstance(model_config, dict)
    assert "adstock_alpha" in model_config
    assert "saturation_lam" in model_config
    assert "saturation_beta" in model_config


def test_build_model_config_channel_specific_prior_parameters():
    channels = ["tv", "radio"]
    channel_priors = {
        "tv": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 3.0, "beta": 1.0}),
                "saturation_lam": PriorDistributionConfig(dist="Gamma", kwargs={"alpha": 5.0, "beta": 2.0}),
            }
        ),
        "radio": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 1.0, "beta": 4.0}),
            }
        ),
    }
    config = FitMMMInput(
        dataset_id="ds1",
        date_column="date",
        target_column="sales",
        channel_columns=channels,
        channel_priors=channel_priors,
    )
    model_config = build_model_config(config)

    adstock_alpha = model_config["adstock_alpha"]
    assert adstock_alpha.distribution == "Beta"
    assert adstock_alpha.dims == ("channel",)
    alpha_da = adstock_alpha.parameters["alpha"]
    assert isinstance(alpha_da, xr.DataArray)
    assert list(alpha_da.coords["channel"].values) == channels
    assert float(alpha_da.sel(channel="tv").values) == 3.0
    assert float(alpha_da.sel(channel="radio").values) == 1.0

    beta_da = adstock_alpha.parameters["beta"]
    assert float(beta_da.sel(channel="tv").values) == 1.0
    assert float(beta_da.sel(channel="radio").values) == 4.0


def test_build_model_config_unspecified_channels_receive_defaults():
    channels = ["tv", "radio", "search"]
    channel_priors = {
        "tv": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 5.0, "beta": 1.0}),
            }
        )
    }
    config = FitMMMInput(
        dataset_id="ds1",
        date_column="date",
        target_column="sales",
        channel_columns=channels,
        channel_priors=channel_priors,
    )
    model_config = build_model_config(config)
    adstock_alpha = model_config["adstock_alpha"]
    alpha_da = adstock_alpha.parameters["alpha"]
    assert float(alpha_da.sel(channel="tv").values) == 5.0
    # Default for geometric adstock alpha is 1.0
    assert float(alpha_da.sel(channel="radio").values) == 1.0
    assert float(alpha_da.sel(channel="search").values) == 1.0


def test_build_model_config_rejects_unknown_channel():
    channels = ["tv", "radio"]
    channel_priors = {
        "print": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": 2.0, "beta": 2.0}),
            }
        )
    }
    with pytest.raises(ValueError, match="unknown channels"):
        FitMMMInput(
            dataset_id="ds1",
            date_column="date",
            target_column="sales",
            channel_columns=channels,
            channel_priors=channel_priors,
        )


def test_build_model_config_rejects_invalid_prior_parameters():
    channels = ["tv", "radio"]
    channel_priors = {
        "tv": ChannelPriorConfig(
            priors={
                "adstock_alpha": PriorDistributionConfig(dist="Beta", kwargs={"alpha": -1.0, "beta": 1.0}),
            }
        )
    }
    config = FitMMMInput(
        dataset_id="ds1",
        date_column="date",
        target_column="sales",
        channel_columns=channels,
        channel_priors=channel_priors,
    )
    with pytest.raises(DomainError) as exc_info:
        build_model_config(config)
    assert exc_info.value.code == "INVALID_PRIOR_PARAMETER"


def test_build_mmm_init_kwargs_assembles_transforms_and_config():
    channels = ["tv", "digital"]
    config = FitMMMInput(
        dataset_id="ds1",
        date_column="date",
        target_column="sales",
        channel_columns=channels,
        adstock=AdstockConfig(type="geometric", l_max=12),
        saturation=SaturationConfig(type="logistic"),
        yearly_seasonality=2,
    )
    kwargs = build_mmm_init_kwargs(config)
    assert kwargs["date_column"] == "date"
    assert kwargs["channel_columns"] == channels
    assert kwargs["target_column"] == "sales"
    assert kwargs["yearly_seasonality"] == 2
    assert kwargs["adstock"].l_max == 12
    assert "model_config" in kwargs
