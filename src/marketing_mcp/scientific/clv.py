"""Pure CLV modeling core driving canonical CLV purchase and value specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from marketing_mcp.errors import DomainError


@dataclass
class CLVFitResult:
    """Canonical result from pure CLV model fitting."""
    model: Any
    parameter_estimates: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    idata: Any = None


def _get_spec_dict(spec: Any) -> dict[str, Any]:
    if isinstance(spec, dict):
        return spec
    if hasattr(spec, "model_dump"):
        return spec.model_dump()
    if hasattr(spec, "dict"):
        return spec.dict()
    return dict(spec)


def _extract_clv_parameters(idata: Any, candidates: list[str]) -> dict[str, float]:
    estimates: dict[str, float] = {}
    if idata is None or not hasattr(idata, "posterior"):
        return estimates

    posterior = idata.posterior
    for param in candidates:
        if param in posterior:
            arr = posterior[param]
            try:
                mean_val = float(arr.mean().item())
                estimates[param] = round(mean_val, 4)
            except Exception:
                continue
    return estimates


def build_clv_purchase_from_spec(spec: Any) -> Any:
    """Instantiate a PyMC-Marketing purchase model (BG/NBD) from canonical spec."""
    import pymc_marketing.clv as clv_module

    spec_dict = _get_spec_dict(spec)
    cfg = spec_dict.get("configuration") or spec_dict
    model_type = cfg.get("model_type", "bg_nbd")

    if model_type == "bg_nbd":
        return clv_module.BetaGeoModel()
    elif model_type in ("shifted_beta_geo", "shifted_beta_geometric"):
        cls = getattr(clv_module, "ShiftedBetaGeoModel", getattr(clv_module, "ShiftedBetaGeometricModelIndividual", None))
        if cls is None:
            raise DomainError("MODEL_UNAVAILABLE", "ShiftedBetaGeoModel is not available in this PyMC-Marketing version")
        return cls()

    raise DomainError("INVALID_CLV_MODEL_TYPE", f"Unsupported CLV purchase model type: {model_type}")


def fit_clv_purchase_from_spec(
    spec: Any,
    df: pd.DataFrame,
    draws: int = 500,
    tune: int = 500,
    chains: int = 2,
    target_accept: float = 0.85,
    artifact_path: Path | None = None,
) -> CLVFitResult:
    """Fit a BG/NBD purchase model directly from a canonical CLVPurchaseModelSpec and RFM DataFrame."""
    spec_dict = _get_spec_dict(spec)
    cfg = spec_dict.get("configuration") or spec_dict

    cust_col = cfg.get("customer_id_column", "customer_id")
    # Verify required RFM columns
    for col in ("frequency", "recency", "T"):
        if col not in df.columns:
            raise DomainError("MISSING_RFM_COLUMNS", f"Required RFM column '{col}' is missing")

    # Normalized DataFrame
    rfm_df = pd.DataFrame({
        "customer_id": df[cust_col],
        "frequency": pd.to_numeric(df["frequency"]),
        "recency": pd.to_numeric(df["recency"]),
        "T": pd.to_numeric(df["T"]),
    }).reset_index(drop=True)

    random_seed = spec_dict.get("random_seed", 42)
    model = build_clv_purchase_from_spec(spec)

    fit_kwargs = {
        "draws": draws,
        "tune": tune,
        "chains": chains,
        "target_accept": target_accept,
        "random_seed": random_seed,
    }

    try:
        model.fit(data=rfm_df, **fit_kwargs)
    except TypeError:
        # Fallback if signature requires X or different args
        model.fit(rfm_df, **fit_kwargs)

    idata = getattr(model, "idata", None)
    estimates = _extract_clv_parameters(idata, ["a", "b", "alpha", "r"])

    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "save"):
            model.save(str(path))
        else:
            path.touch()

    return CLVFitResult(
        model=model,
        parameter_estimates=estimates,
        diagnostics={"fit_samples": draws * chains},
        idata=idata,
    )


def build_clv_value_from_spec(spec: Any) -> Any:
    """Instantiate a PyMC-Marketing customer monetary value model (Gamma-Gamma) from canonical spec."""
    import pymc_marketing.clv as clv_module

    return clv_module.GammaGammaModel()


def fit_clv_value_from_spec(
    spec: Any,
    df: pd.DataFrame,
    draws: int = 500,
    tune: int = 500,
    chains: int = 2,
    target_accept: float = 0.85,
    artifact_path: Path | None = None,
) -> CLVFitResult:
    """Fit a Gamma-Gamma monetary value model directly from a canonical CLVValueModelSpec."""
    spec_dict = _get_spec_dict(spec)
    cfg = spec_dict.get("configuration") or spec_dict

    cust_col = cfg.get("customer_id_column", "customer_id")
    freq_col = cfg.get("frequency_column", "frequency")
    mon_col = cfg.get("monetary_value_column", "monetary_value")

    for col in (freq_col, mon_col):
        if col not in df.columns:
            raise DomainError("MISSING_RFM_COLUMNS", f"Required column '{col}' is missing")

    # Gamma-Gamma requires positive frequency and monetary value
    valid_mask = (df[freq_col] > 0) & (df[mon_col] > 0)
    if not valid_mask.any():
        raise DomainError("INVALID_RFM_DATA", "Gamma-Gamma requires repeat customers with positive spend")

    val_df = pd.DataFrame({
        "customer_id": df.loc[valid_mask, cust_col],
        "frequency": pd.to_numeric(df.loc[valid_mask, freq_col]),
        "monetary_value": pd.to_numeric(df.loc[valid_mask, mon_col]),
    }).reset_index(drop=True)

    random_seed = spec_dict.get("random_seed", 42)
    model = build_clv_value_from_spec(spec)

    fit_kwargs = {
        "draws": draws,
        "tune": tune,
        "chains": chains,
        "target_accept": target_accept,
        "random_seed": random_seed,
    }

    try:
        model.fit(data=val_df, **fit_kwargs)
    except TypeError:
        model.fit(val_df, **fit_kwargs)

    idata = getattr(model, "idata", None)
    estimates = _extract_clv_parameters(idata, ["p", "q", "v"])

    if artifact_path is not None:
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "save"):
            model.save(str(path))
        else:
            path.touch()

    return CLVFitResult(
        model=model,
        parameter_estimates=estimates,
        diagnostics={"fit_samples": draws * chains},
        idata=idata,
    )
