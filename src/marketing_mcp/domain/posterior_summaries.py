"""Domain-level posterior summaries shared by plots and analytical tools.

Statistical contract: aggregate over time/panel dimensions PER POSTERIOR DRAW
first, then summarize across chain/draw. Plot code renders only these outputs
so visual claims stay numerically identical to analytical summaries.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr
from arviz import InferenceData

from marketing_mcp.errors import DomainError

CONTRIBUTION_VARS = ("channel_contribution_original_scale", "channel_contribution")
HDI_QUANTILES = (0.03, 0.5, 0.97)

_TIME_DIM_CANDIDATES = ("date", "date_week", "week", "time", "period")


def _group_dataset(idata: Any, group: str) -> xr.Dataset:
    """Normalize a group (DataTree root/InferenceData/Dataset) into a Dataset."""
    if isinstance(idata, xr.Dataset):
        return idata
    node = idata.get(group) if hasattr(idata, "get") else None
    if node is None:
        raise DomainError(
            "DATA_INVALID",
            f"Inference data group '{group}' is not available",
        )
    ds = getattr(node, "dataset", None)
    if ds is None:
        ds = node if isinstance(node, xr.Dataset) else None
    if ds is None:
        raise DomainError(
            "DATA_INVALID",
            f"Group '{group}' does not expose a dataset",
        )
    return ds


def _find_time_dim(da: xr.DataArray) -> str:
    """Identify the time dimension by name/coordinate, never by position."""
    for name in _TIME_DIM_CANDIDATES:
        if name in da.dims:
            return name
    for dim in da.dims:
        coord = da.coords.get(dim)
        if coord is not None and np.issubdtype(np.asarray(coord).dtype, np.datetime64):
            return dim
    raise DomainError(
        "DATA_INVALID",
        "Could not identify a time dimension for posterior predictive summary",
        evidence={"dims": list(map(str, da.dims))},
    )


def _pick_contribution_var(posterior: xr.Dataset) -> str:
    var = next((v for v in CONTRIBUTION_VARS if v in posterior), None)
    if var is None:
        raise DomainError(
            "DATA_INVALID",
            "No channel contribution variable exists in the posterior",
            evidence={"available": list(map(str, posterior.data_vars))},
        )
    return var


def summarize_channel_contributions(
    idata: InferenceData,
    group_dims: tuple[str, ...] = (),
) -> xr.Dataset:
    """Summarize total channel contributions over the modeled horizon.

    Sums contributions over all non-(chain, draw, channel) dims PER DRAW, then
    computes the posterior median and a 94% interval across chain/draw.

    Args:
        idata: Fitted model inference data containing a channel contribution variable.
        group_dims: Panel dims to keep explicitly (e.g. ``("geo",)``); each kept
            dimension receives its own per-draw aggregation and summary.

    Returns:
        Dataset with ``median``, ``lower``, ``upper`` data variables over
        ``channel`` (plus any ``group_dims``).
    """
    posterior = _group_dataset(idata, "posterior")
    var = _pick_contribution_var(posterior)
    da = posterior[var]

    keep = {"chain", "draw", "channel", *group_dims}
    reduce_dims = [d for d in da.dims if d not in keep]
    per_draw = da.sum(dim=reduce_dims) if reduce_dims else da

    sample_dims = ["chain", "draw"]
    lower = per_draw.quantile(HDI_QUANTILES[0], dim=sample_dims).drop_vars("quantile")
    median = per_draw.quantile(HDI_QUANTILES[1], dim=sample_dims).drop_vars("quantile")
    upper = per_draw.quantile(HDI_QUANTILES[2], dim=sample_dims).drop_vars("quantile")

    return xr.Dataset({"median": median, "lower": lower, "upper": upper})


def summarize_predictions(
    idata: InferenceData,
) -> xr.Dataset:
    """Summarize posterior predictive y over chain/draw, keeping the time axis.

    The time dimension is identified by coordinate/name (never ``shape[-1]``),
    so panel-first storage orders are handled identically to date-last.

    Returns:
        Dataset with ``median``, ``lower``, ``upper`` over the identified time
        dimension, retaining its coordinate labels.
    """
    pp = _group_dataset(idata, "posterior_predictive")
    if pp is None:
        raise DomainError(
            "DATA_INVALID",
            "No posterior predictive group available for summarization",
        )
    y_var = next((v for v in pp.data_vars if "y" in v.lower()), None)
    if y_var is None:
        raise DomainError(
            "DATA_INVALID",
            "Posterior predictive contains no y-like variable",
            evidence={"available": list(map(str, pp.data_vars))},
        )
    da = pp[y_var]

    time_dim = _find_time_dim(da)
    others = [d for d in da.dims if d != time_dim]

    if others:
        q = da.quantile(list(HDI_QUANTILES), dim=others)
        out = {
            name: q.isel(quantile=idx).drop_vars("quantile")
            for idx, name in enumerate(("lower", "median", "upper"))
        }
    else:
        out = {"lower": da, "median": da, "upper": da}

    return xr.Dataset(out)
