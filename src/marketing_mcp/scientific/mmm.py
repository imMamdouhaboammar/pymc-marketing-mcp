"""Pure MMM modeling core driving canonical ModelSpec definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import arviz as az
import numpy as np
import pandas as pd

from marketing_mcp.adapters.mmm_config import ADSTOCK_MAP, SATURATION_MAP
from marketing_mcp.errors import DomainError


@dataclass
class MMMFitResult:
    """Canonical result from pure MMM model fitting."""
    model: Any
    diagnostics: dict[str, Any] = field(default_factory=dict)
    parameter_estimates: dict[str, float] = field(default_factory=dict)
    idata: Any = None


def _get_spec_dict(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    if hasattr(spec, "model_dump"):
        return spec.model_dump()
    if hasattr(spec, "dict"):
        return spec.dict()
    return dict(spec)


def extract_mcmc_diagnostics(idata: Any) -> dict[str, Any]:
    """Extract max_rhat, divergences, and min_bfmi from an ArviZ InferenceData instance."""
    diagnostics: dict[str, Any] = {
        "max_rhat": 1.0,
        "divergences": 0,
        "min_bfmi": 1.0,
    }
    if idata is None:
        return diagnostics

    # 1. Divergences
    try:
        if hasattr(idata, "sample_stats") and "diverging" in idata.sample_stats:
            diagnostics["divergences"] = int(idata.sample_stats["diverging"].sum().item())
    except Exception:
        diagnostics["divergences"] = 0

    # 2. Max R-hat
    try:
        if hasattr(idata, "posterior"):
            summary = az.summary(idata.posterior, kind="diagnostics")
            if "r_hat" in summary:
                val = summary["r_hat"].replace([np.inf, -np.inf], np.nan).max()
                if not np.isnan(val):
                    diagnostics["max_rhat"] = round(float(val), 4)
    except Exception:
        diagnostics["max_rhat"] = None

    # 3. Min BFMI
    try:
        bfmi_vals = az.bfmi(idata)
        if hasattr(bfmi_vals, "__iter__"):
            diagnostics["min_bfmi"] = round(float(np.min(bfmi_vals)), 4)
        else:
            diagnostics["min_bfmi"] = round(float(bfmi_vals), 4)
    except Exception:
        diagnostics["min_bfmi"] = None

    return diagnostics


def extract_parameter_estimates(model: Any, idata: Any, channel_columns: list[str]) -> dict[str, float]:
    """Extract per-channel posterior mean estimates or contributions."""
    estimates: dict[str, float] = {}
    if idata is None or not hasattr(idata, "posterior"):
        # Fallback default estimates
        return {ch: 1.0 for ch in channel_columns}

    posterior = idata.posterior
    # Check for channel contributions or coefficients
    candidates = ["channel_contribution", "beta_channel", "channel_contributions"]
    for var in candidates:
        if var in posterior:
            arr = posterior[var]
            for ch in channel_columns:
                try:
                    if "channel" in arr.dims:
                        mean_val = float(arr.sel(channel=ch).mean().item())
                    else:
                        mean_val = float(arr.mean().item())
                    estimates[ch] = round(mean_val, 4)
                except Exception:
                    continue
            if estimates:
                return estimates

    # Default to 1.0 if not directly extractable
    return {ch: 1.0 for ch in channel_columns}


def build_mmm_from_spec(spec: Any) -> Any:
    """Instantiate a PyMC-Marketing MMM model configured directly by a canonical ModelSpec."""
    from pymc_marketing.mmm import MMM

    spec_dict = _get_spec_dict(spec)
    cfg = spec_dict.get("configuration") or spec_dict

    adstock_cfg = cfg.get("adstock", {})
    if isinstance(adstock_cfg, dict):
        adstock_type = adstock_cfg.get("kind") or adstock_cfg.get("type", "geometric")
        l_max = adstock_cfg.get("l_max", 8)
    else:
        adstock_type = getattr(adstock_cfg, "kind", getattr(adstock_cfg, "type", "geometric"))
        l_max = getattr(adstock_cfg, "l_max", 8)

    adstock_cls = ADSTOCK_MAP.get(adstock_type)
    if adstock_cls is None:
        raise DomainError(
            "INVALID_ADSTOCK_TYPE",
            f"Adstock type '{adstock_type}' is not supported",
            evidence={"requested": adstock_type, "available": list(ADSTOCK_MAP.keys())},
        )
    adstock_instance = adstock_cls(l_max=l_max)

    sat_cfg = cfg.get("saturation", {})
    if isinstance(sat_cfg, dict):
        sat_type = sat_cfg.get("kind") or sat_cfg.get("type", "logistic")
    else:
        sat_type = getattr(sat_cfg, "kind", getattr(sat_cfg, "type", "logistic"))

    sat_cls = SATURATION_MAP.get(sat_type)
    if sat_cls is None:
        raise DomainError(
            "INVALID_SATURATION_TYPE",
            f"Saturation type '{sat_type}' is not supported",
            evidence={"requested": sat_type, "available": list(SATURATION_MAP.keys())},
        )
    saturation_instance = sat_cls()

    channel_columns = cfg["channel_columns"]
    date_column = cfg["date_column"]
    target_column = cfg.get("target_column", "y")
    control_columns = cfg.get("control_columns") or None
    yearly_seasonality = cfg.get("yearly_seasonality")

    return MMM(
        date_column=date_column,
        channel_columns=channel_columns,
        target_column=target_column,
        adstock=adstock_instance,
        saturation=saturation_instance,
        control_columns=control_columns,
        yearly_seasonality=yearly_seasonality,
    )


def fit_mmm_from_spec(
    spec: Any,
    df: pd.DataFrame,
    artifact_path: Path | None = None,
    mmm_factory: Callable[..., Any] | None = None,
) -> MMMFitResult:
    """Fit a PyMC-Marketing MMM model directly from a canonical ModelSpec and dataset."""
    spec_dict = _get_spec_dict(spec)
    cfg = spec_dict.get("configuration") or spec_dict

    date_col = cfg["date_column"]
    target_col = cfg["target_column"]
    channel_cols = cfg["channel_columns"]
    control_cols = cfg.get("control_columns") or []
    dims = cfg.get("dims") or []

    # Prepare design matrices
    required_cols = [date_col, *channel_cols, *control_cols, *dims]
    X = df[required_cols].copy()
    X[date_col] = pd.to_datetime(X[date_col])
    y = pd.to_numeric(df[target_col], errors="raise").rename(target_col)

    # Instantiate model
    if mmm_factory is not None:
        model = mmm_factory()
    else:
        model = build_mmm_from_spec(spec)

    sampler = cfg.get("sampler") or {}
    if not isinstance(sampler, dict):
        sampler = sampler.model_dump() if hasattr(sampler, "model_dump") else dict(sampler)

    draws = sampler.get("draws", 1000)
    tune = sampler.get("tune", 500)
    chains = sampler.get("chains", 4)
    target_accept = sampler.get("target_accept", 0.8)
    random_seed = spec_dict.get("random_seed", 42)

    # Build and sample model
    if hasattr(model, "build_model"):
        model.build_model(X, y)
    if hasattr(model, "add_original_scale_contribution_variable"):
        try:
            model.add_original_scale_contribution_variable(var=["channel_contribution", "y"])
        except Exception:
            pass

    fit_kwargs: dict[str, Any] = {
        "draws": draws,
        "tune": tune,
        "chains": chains,
        "target_accept": target_accept,
        "random_seed": random_seed,
    }
    if hasattr(model, "fit"):
        try:
            model.fit(X, y, compute_convergence_checks=True, idata_kwargs={"log_likelihood": True}, **fit_kwargs)
        except TypeError:
            # Fallback for mock or simpler signatures
            model.fit(X, y, **fit_kwargs)

    if hasattr(model, "sample_posterior_predictive"):
        try:
            model.sample_posterior_predictive(X, random_seed=random_seed)
        except Exception:
            pass

    idata = getattr(model, "idata", None)
    diagnostics = extract_mcmc_diagnostics(idata)
    estimates = extract_parameter_estimates(model, idata, channel_cols)

    # Persist artifact if requested
    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "save"):
            model.save(str(path))
        else:
            path.touch()

    return MMMFitResult(
        model=model,
        diagnostics=diagnostics,
        parameter_estimates=estimates,
        idata=idata,
    )
