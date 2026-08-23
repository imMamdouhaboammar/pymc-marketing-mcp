"""MMM Model Configuration Builder.

Builds typed model_config and initialization kwargs for PyMC-Marketing MMM models,
supporting coordinate-aligned per-channel prior parameter overrides.
"""

from __future__ import annotations

from typing import Any

import xarray as xr
from pymc_marketing.mmm import (
    BinomialAdstock,
    DelayedAdstock,
    GeometricAdstock,
    HillSaturation,
    HillSaturationSigmoid,
    InverseScaledLogisticSaturation,
    LogisticSaturation,
    LogSaturation,
    MichaelisMentenSaturation,
    NoAdstock,
    NoSaturation,
    RootSaturation,
    TanhSaturation,
    TanhSaturationBaselined,
    WeibullCDFAdstock,
    WeibullPDFAdstock,
)
from pymc_marketing.model_config import Prior

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    AdstockConfig,
    ChannelPriorConfig,
    FitMMMInput,
    PriorDistributionConfig,
    SaturationConfig,
)

ADSTOCK_MAP = {
    "geometric": GeometricAdstock,
    "delayed": DelayedAdstock,
    "weibull_cdf": WeibullCDFAdstock,
    "weibull_pdf": WeibullPDFAdstock,
    "binomial": BinomialAdstock,
    "none": NoAdstock,
}

SATURATION_MAP = {
    "logistic": LogisticSaturation,
    "tanh": TanhSaturation,
    "tanh_baselined": TanhSaturationBaselined,
    "michaelis_menten": MichaelisMentenSaturation,
    "hill": HillSaturation,
    "hill_sigmoid": HillSaturationSigmoid,
    "inverse_scaled_logistic": InverseScaledLogisticSaturation,
    "log": LogSaturation,
    "root": RootSaturation,
    "none": NoSaturation,
}

# Default distribution definitions for channel parameters
DEFAULT_CHANNEL_PRIORS: dict[str, tuple[str, dict[str, float]]] = {
    "adstock_alpha": ("Beta", {"alpha": 1.0, "beta": 3.0}),
    "adstock_theta": ("HalfNormal", {"sigma": 2.0}),
    "adstock_lam": ("Gamma", {"alpha": 3.0, "beta": 1.0}),
    "adstock_k": ("Gamma", {"alpha": 3.0, "beta": 1.0}),
    "saturation_lam": ("Gamma", {"alpha": 3.0, "beta": 1.0}),
    "saturation_beta": ("HalfNormal", {"sigma": 2.0}),
    "saturation_alpha": ("HalfNormal", {"sigma": 2.0}),
    "saturation_b": ("Gamma", {"alpha": 1.0, "beta": 1.0}),
    "saturation_c": ("HalfNormal", {"sigma": 2.0}),
    "saturation_sigma": ("HalfNormal", {"sigma": 2.0}),
    "saturation_x0": ("HalfNormal", {"sigma": 2.0}),
}

POSITIVE_ONLY_PARAMS = {"alpha", "beta", "sigma", "lam", "k", "theta", "b", "c"}


def build_adstock(cfg: AdstockConfig | dict[str, Any] | None) -> Any:
    if cfg is None:
        return GeometricAdstock(l_max=8)
    if isinstance(cfg, dict):
        adstock_type = cfg.get("type", "geometric")
        l_max = cfg.get("l_max", 8)
        normalize = cfg.get("normalize", True)
    else:
        adstock_type = cfg.type
        l_max = cfg.l_max
        normalize = getattr(cfg, "normalize", True)

    cls = ADSTOCK_MAP.get(adstock_type)
    if cls is None:
        raise DomainError(
            "INVALID_ADSTOCK_TYPE",
            f"Adstock type '{adstock_type}' is not supported",
            evidence={"requested": adstock_type, "available": list(ADSTOCK_MAP.keys())},
        )
    return cls(l_max=l_max, normalize=normalize)


def build_saturation(cfg: SaturationConfig | dict[str, Any] | None) -> Any:
    if cfg is None:
        return LogisticSaturation()
    if isinstance(cfg, dict):
        saturation_type = cfg.get("type", "logistic")
    else:
        saturation_type = cfg.type

    cls = SATURATION_MAP.get(saturation_type)
    if cls is None:
        raise DomainError(
            "INVALID_SATURATION_TYPE",
            f"Saturation type '{saturation_type}' is not supported",
            evidence={"requested": saturation_type, "available": list(SATURATION_MAP.keys())},
        )
    return cls()


def validate_channel_priors(
    channel_priors: dict[str, ChannelPriorConfig | dict[str, Any]],
    channel_columns: list[str],
) -> None:
    unknown_channels = set(channel_priors) - set(channel_columns)
    if unknown_channels:
        raise DomainError(
            "INPUT_INVALID",
            f"channel_priors contains unknown channels: {sorted(unknown_channels)}",
            evidence={"unknown_channels": list(unknown_channels), "channel_columns": channel_columns},
        )

    for ch, p_cfg in channel_priors.items():
        priors_dict: dict[str, Any] = {}
        if isinstance(p_cfg, ChannelPriorConfig):
            priors_dict = p_cfg.priors
        elif isinstance(p_cfg, dict):
            priors_dict = p_cfg.get("priors", {})

        for var_name, prior in priors_dict.items():
            if isinstance(prior, PriorDistributionConfig):
                kwargs = prior.kwargs
            elif isinstance(prior, dict):
                kwargs = prior.get("kwargs", {})
            else:
                continue

            for param_name, param_val in kwargs.items():
                if param_name in POSITIVE_ONLY_PARAMS and param_val <= 0:
                    raise DomainError(
                        "INVALID_PRIOR_PARAMETER",
                        f"Parameter '{param_name}' for variable '{var_name}' on channel '{ch}' must be positive, got {param_val}",
                        evidence={"channel": ch, "variable": var_name, "parameter": param_name, "value": param_val},
                    )


def build_model_config(config: FitMMMInput | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, dict):
        channel_columns = config.get("channel_columns", [])
        channel_priors = config.get("channel_priors", {})
        adstock_cfg = config.get("adstock")
        saturation_cfg = config.get("saturation")
    else:
        channel_columns = config.channel_columns
        channel_priors = config.channel_priors
        adstock_cfg = config.adstock
        saturation_cfg = config.saturation

    validate_channel_priors(channel_priors, channel_columns)

    # Instantiate transforms to get their default priors
    adstock = build_adstock(adstock_cfg)
    saturation = build_saturation(saturation_cfg)

    model_config: dict[str, Any] = {}

    # Extract adstock default priors
    if hasattr(adstock, "default_priors"):
        for param, prior in adstock.default_priors.items():
            var_name = f"adstock_{param}"
            model_config[var_name] = prior

    # Extract saturation default priors
    if hasattr(saturation, "default_priors"):
        for param, prior in saturation.default_priors.items():
            var_name = f"saturation_{param}"
            model_config[var_name] = prior

    # Process per-channel prior overrides
    # Find all variable names mentioned in channel_priors
    overridden_vars: set[str] = set()
    for ch, p_cfg in channel_priors.items():
        if isinstance(p_cfg, ChannelPriorConfig):
            overridden_vars.update(p_cfg.priors.keys())
        elif isinstance(p_cfg, dict):
            overridden_vars.update(p_cfg.get("priors", {}).keys())

    for var_name in overridden_vars:
        default_info = DEFAULT_CHANNEL_PRIORS.get(var_name)
        if default_info is None:
            # Fall back to existing model_config entry if available
            existing_prior = model_config.get(var_name)
            if existing_prior is not None:
                default_dist = existing_prior.distribution
                default_kwargs = existing_prior.parameters
            else:
                default_dist = "Normal"
                default_kwargs = {"mu": 0.0, "sigma": 1.0}
        else:
            default_dist, default_kwargs = default_info

        # Gather distribution family and parameter values for each channel
        dist_name = default_dist
        param_arrays: dict[str, list[float]] = {p: [] for p in default_kwargs}

        for ch in channel_columns:
            ch_cfg = channel_priors.get(ch)
            ch_prior = None
            if isinstance(ch_cfg, ChannelPriorConfig):
                ch_prior = ch_cfg.priors.get(var_name)
            elif isinstance(ch_cfg, dict):
                ch_prior = ch_cfg.get("priors", {}).get(var_name)

            if ch_prior is not None:
                if isinstance(ch_prior, PriorDistributionConfig):
                    dist_name = ch_prior.dist
                    ch_kwargs = ch_prior.kwargs
                elif isinstance(ch_prior, dict):
                    dist_name = ch_prior.get("dist", default_dist)
                    ch_kwargs = ch_prior.get("kwargs", {})
                else:
                    ch_kwargs = {}
                for p in default_kwargs:
                    val = float(ch_kwargs.get(p, default_kwargs[p]))
                    param_arrays[p].append(val)
            else:
                for p in default_kwargs:
                    param_arrays[p].append(float(default_kwargs[p]))

        # Build DataArray for each parameter
        da_kwargs: dict[str, Any] = {}
        for p, vals in param_arrays.items():
            da_kwargs[p] = xr.DataArray(vals, dims=["channel"], coords={"channel": channel_columns})

        model_config[var_name] = Prior(dist_name, dims="channel", **da_kwargs)

    return model_config


def build_mmm_init_kwargs(config: FitMMMInput | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, dict):
        date_column = config["date_column"]
        channel_columns = config["channel_columns"]
        target_column = config.get("target_column", "y")
        control_columns = config.get("control_columns")
        yearly_seasonality = config.get("yearly_seasonality")
        dims = config.get("dims")
        adstock_cfg = config.get("adstock")
        saturation_cfg = config.get("saturation")
    else:
        date_column = config.date_column
        channel_columns = config.channel_columns
        target_column = config.target_column
        control_columns = config.control_columns or None
        yearly_seasonality = config.yearly_seasonality
        dims = tuple(config.dims) if config.dims else None
        adstock_cfg = config.adstock
        saturation_cfg = config.saturation

    adstock = build_adstock(adstock_cfg)
    saturation = build_saturation(saturation_cfg)
    model_config = build_model_config(config)

    kwargs: dict[str, Any] = {
        "date_column": date_column,
        "channel_columns": channel_columns,
        "target_column": target_column,
        "adstock": adstock,
        "saturation": saturation,
        "model_config": model_config,
    }

    if control_columns:
        kwargs["control_columns"] = control_columns
    if yearly_seasonality:
        kwargs["yearly_seasonality"] = yearly_seasonality
    if dims:
        kwargs["dims"] = dims

    return kwargs
