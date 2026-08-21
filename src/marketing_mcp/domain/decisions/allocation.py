from __future__ import annotations

from itertools import product
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from marketing_mcp.errors import DomainError


def _json_scalar(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def model_dimensions(model) -> list[str]:
    return list(getattr(model, "dims", ()) or ())


def _dimension_coords(model) -> dict[str, list[Any]]:
    dims = model_dimensions(model)
    if not dims:
        return {}
    if not hasattr(model, "X"):
        raise DomainError(
            "BUDGET_DATA_UNAVAILABLE",
            "Historical fitted data are unavailable in the model artifact",
        )
    coords = {}
    for dim in dims:
        if dim not in model.X.columns:
            raise DomainError(
                "BUDGET_DATA_UNAVAILABLE",
                f"Dimension {dim} is absent from historical fitted data",
            )
        values = [_json_scalar(v) for v in model.X[dim].drop_duplicates().tolist()]
        if not values:
            raise DomainError(
                "BUDGET_DATA_UNAVAILABLE",
                f"Dimension {dim} has no historical values",
            )
        coords[dim] = values
    return coords


def historical_allocation(
    model,
    planning_periods: int,
    total_budget: float | None = None,
) -> dict[str, Any]:
    if not hasattr(model, "X"):
        raise DomainError(
            "BUDGET_DATA_UNAVAILABLE",
            "Historical fitted media data are unavailable in the model artifact",
        )
    channels = list(model.channel_columns)
    date_column = model.date_column
    frame = model.X.copy()
    if date_column not in frame.columns:
        raise DomainError(
            "BUDGET_DATA_UNAVAILABLE",
            "Historical fitted data do not contain the model date column",
        )
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    unique_dates = pd.DatetimeIndex(dates.dropna().unique()).sort_values()
    if unique_dates.empty:
        raise DomainError("BUDGET_DATA_UNAVAILABLE", "No valid historical dates are available")
    recent_dates = set(unique_dates[-planning_periods:].tolist())
    recent = frame[dates.isin(recent_dates)].copy()
    dims = model_dimensions(model)

    if not dims:
        totals = recent[channels].apply(pd.to_numeric, errors="coerce").sum(axis=0)
        allocation: dict[str, Any] = {channel: float(totals[channel]) for channel in channels}
    else:
        coords = _dimension_coords(model)
        cells = []
        numeric = recent[channels].apply(pd.to_numeric, errors="coerce")
        work = pd.concat(
            [recent[dims].reset_index(drop=True), numeric.reset_index(drop=True)],
            axis=1,
        )
        grouped = work.groupby(dims, dropna=False, sort=False)[channels].sum()
        for channel in channels:
            for values in product(*(coords[dim] for dim in dims)):
                key = values[0] if len(values) == 1 else values
                try:
                    amount = float(grouped.loc[key, channel])
                except KeyError as exc:
                    raise DomainError(
                        "NON_RECTANGULAR_PANEL",
                        "A historical budget cell is missing for a model dimension combination",
                        evidence={
                            "channel": channel,
                            "dimensions": dict(zip(dims, values, strict=True)),
                        },
                    ) from exc
                cells.append(
                    {
                        "channel": channel,
                        "dimensions": dict(zip(dims, values, strict=True)),
                        "amount": amount,
                    }
                )
        allocation = {"dimensions": dims, "cells": cells}

    if total_budget is None:
        return allocation
    xr_allocation = allocation_to_xarray(model, allocation)
    current_total = float(xr_allocation.sum())
    if not np.isfinite(current_total) or current_total <= 0:
        raise DomainError(
            "BASELINE_ALLOCATION_UNAVAILABLE",
            "Recent historical spend cannot define a baseline allocation",
            next_action="Provide a model with positive recent channel spend",
        )
    scaled = xr_allocation * (float(total_budget) / current_total)
    return allocation_from_xarray(model, scaled)


def apply_changes(
    model,
    baseline: dict[str, Any],
    channel_changes: dict[str, Any],
    cell_changes: list[Any],
) -> dict[str, Any]:
    dims = model_dimensions(model)
    channels = list(model.channel_columns)

    def change_value(amount: float, change: Any) -> float:
        change_type = change.type if hasattr(change, "type") else change["type"]
        value = float(change.value if hasattr(change, "value") else change["value"])
        updated = amount * (1 + value) if change_type == "relative" else amount + value
        if updated < 0:
            raise DomainError("INVALID_BUDGET", "Scenario produces negative spend")
        return float(updated)

    unknown_channels = sorted(set(channel_changes) - set(channels))
    if unknown_channels:
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Scenario contains unknown channels",
            evidence={"unknown_channels": unknown_channels, "known_channels": channels},
        )

    if not dims:
        if cell_changes:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Dimension-cell changes are only valid for multidimensional MMMs",
            )
        scenario = {channel: float(baseline[channel]) for channel in channels}
        for channel, change in channel_changes.items():
            scenario[channel] = change_value(scenario[channel], change)
        return scenario

    scenario = {
        "dimensions": list(baseline["dimensions"]),
        "cells": [
            {
                "channel": cell["channel"],
                "dimensions": dict(cell["dimensions"]),
                "amount": float(cell["amount"]),
            }
            for cell in baseline["cells"]
        ],
    }
    for cell in scenario["cells"]:
        if cell["channel"] in channel_changes:
            cell["amount"] = change_value(cell["amount"], channel_changes[cell["channel"]])

    index = {
        (
            cell["channel"],
            tuple((dim, cell["dimensions"][dim]) for dim in dims),
        ): cell
        for cell in scenario["cells"]
    }
    seen = set()
    for change in cell_changes:
        channel = change.channel if hasattr(change, "channel") else change["channel"]
        dimensions = (
            dict(change.dimensions) if hasattr(change, "dimensions") else dict(change["dimensions"])
        )
        _validate_selector(model, channel, dimensions)
        key = (channel, tuple((dim, dimensions[dim]) for dim in dims))
        if key in seen:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Duplicate scenario change for the same channel/dimension cell",
                evidence={"channel": channel, "dimensions": dimensions},
            )
        seen.add(key)
        cell = index.get(key)
        if cell is None:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Scenario cell does not exist in the fitted model",
                evidence={"channel": channel, "dimensions": dimensions},
            )
        cell["amount"] = change_value(cell["amount"], change)
    return scenario


def allocation_to_xarray(model, allocation: dict[str, Any]) -> xr.DataArray:
    channels = list(model.channel_columns)
    dims = model_dimensions(model)
    if not dims:
        unknown = sorted(set(allocation) - set(channels))
        missing = sorted(set(channels) - set(allocation))
        if unknown or missing:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Allocation must contain exactly the fitted model channels",
                evidence={"unknown_channels": unknown, "missing_channels": missing},
            )
        values = [float(allocation[channel]) for channel in channels]
        if any(value < 0 for value in values):
            raise DomainError("INVALID_BUDGET", "Allocation values must be non-negative")
        return xr.DataArray(values, dims=["channel"], coords={"channel": channels})

    if allocation.get("dimensions") != dims:
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Allocation dimensions do not match the fitted model",
            evidence={"expected": dims, "received": allocation.get("dimensions")},
        )
    coords = _dimension_coords(model)
    shape = [len(channels), *(len(coords[dim]) for dim in dims)]
    values = np.full(shape, np.nan, dtype=float)
    array = xr.DataArray(
        values,
        dims=["channel", *dims],
        coords={"channel": channels, **coords},
    )
    seen = set()
    for cell in allocation.get("cells", []):
        channel = cell["channel"]
        dimensions = dict(cell.get("dimensions", {}))
        _validate_selector(model, channel, dimensions)
        key = (channel, tuple((dim, dimensions[dim]) for dim in dims))
        if key in seen:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Allocation contains duplicate channel/dimension cells",
                evidence={"channel": channel, "dimensions": dimensions},
            )
        seen.add(key)
        amount = float(cell["amount"])
        if amount < 0:
            raise DomainError("INVALID_BUDGET", "Allocation values must be non-negative")
        array.loc[{"channel": channel, **dimensions}] = amount
    if bool(array.isnull().any()):
        missing_count = int(array.isnull().sum())
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Allocation is missing channel/dimension cells",
            evidence={"missing_cells": missing_count, "dims": ["channel", *dims]},
        )
    return array


def allocation_from_xarray(model, allocation: xr.DataArray) -> dict[str, Any]:
    channels = list(model.channel_columns)
    dims = model_dimensions(model)
    if not dims:
        array = allocation.transpose("channel")
        return {channel: float(array.sel(channel=channel).item()) for channel in channels}
    array = allocation.transpose("channel", *dims)
    cells = []
    for channel in channels:
        for values in product(*(array.coords[dim].values.tolist() for dim in dims)):
            selector = dict(zip(dims, values, strict=True))
            cells.append(
                {
                    "channel": channel,
                    "dimensions": {dim: _json_scalar(value) for dim, value in selector.items()},
                    "amount": float(array.sel(channel=channel, **selector).item()),
                }
            )
    return {"dimensions": dims, "cells": cells}


def build_budget_bounds(
    model,
    budget: float,
    channel_constraints: dict[str, Any],
    cell_constraints: list[dict[str, Any]],
) -> xr.DataArray:
    channels = list(model.channel_columns)
    dims = model_dimensions(model)
    if dims and channel_constraints:
        raise DomainError(
            "DIMENSIONAL_CONSTRAINT_REQUIRED",
            "Channel-level min/max/fixed constraints are ambiguous for a multidimensional MMM",
            evidence={"dims": dims, "channels": sorted(channel_constraints)},
            next_action=(
                "Use cell_constraints with an exact dimension selector for each constrained cell"
            ),
        )

    coords = _dimension_coords(model) if dims else {}
    shape = [len(channels), *(len(coords[dim]) for dim in dims), 2]
    values = np.empty(shape, dtype=float)
    values[..., 0] = 0.0
    values[..., 1] = float(budget)
    bounds = xr.DataArray(
        values,
        dims=["channel", *dims, "bound"],
        coords={"channel": channels, **coords, "bound": ["lower", "upper"]},
    )

    if not dims:
        unknown = sorted(set(channel_constraints) - set(channels))
        if unknown:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "Budget constraints contain unknown channels",
                evidence={"unknown_channels": unknown, "known_channels": channels},
            )
        for channel, constraint in channel_constraints.items():
            _apply_bound(bounds, {"channel": channel}, constraint)
        if cell_constraints:
            raise DomainError(
                "INVALID_CONSTRAINT",
                "cell_constraints are only valid for multidimensional MMMs",
            )
    else:
        seen = set()
        for constraint in cell_constraints:
            channel = constraint["channel"]
            dimensions = dict(constraint.get("dimensions", {}))
            _validate_selector(model, channel, dimensions)
            key = (channel, tuple((dim, dimensions[dim]) for dim in dims))
            if key in seen:
                raise DomainError(
                    "INVALID_CONSTRAINT",
                    "Duplicate constraint for the same channel/dimension cell",
                    evidence={"channel": channel, "dimensions": dimensions},
                )
            seen.add(key)
            _apply_bound(bounds, {"channel": channel, **dimensions}, constraint)

    sum_min = float(bounds.sel(bound="lower").sum())
    sum_max = float(bounds.sel(bound="upper").sum())
    if sum_min > budget or sum_max < budget:
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Budget constraints are infeasible",
            evidence={"sum_min": sum_min, "sum_max": sum_max, "budget": budget},
        )
    return bounds


def _apply_bound(bounds: xr.DataArray, selector: dict[str, Any], constraint: Any) -> None:
    data = constraint if isinstance(constraint, dict) else constraint.model_dump(exclude_none=True)
    fixed = data.get("fixed")
    if fixed is not None:
        bounds.loc[{**selector, "bound": "lower"}] = float(fixed)
        bounds.loc[{**selector, "bound": "upper"}] = float(fixed)
        return
    if data.get("min") is not None:
        bounds.loc[{**selector, "bound": "lower"}] = float(data["min"])
    if data.get("max") is not None:
        bounds.loc[{**selector, "bound": "upper"}] = float(data["max"])


def _validate_selector(model, channel: str, dimensions: dict[str, Any]) -> None:
    channels = list(model.channel_columns)
    dims = model_dimensions(model)
    if channel not in channels:
        raise DomainError(
            "INVALID_CONSTRAINT",
            f"Unknown channel {channel}",
            evidence={"known_channels": channels},
        )
    if set(dimensions) != set(dims):
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Dimension selector must specify every fitted model dimension exactly once",
            evidence={"expected_dimensions": dims, "received_dimensions": sorted(dimensions)},
        )
    coords = _dimension_coords(model)
    unknown_values = {dim: value for dim, value in dimensions.items() if value not in coords[dim]}
    if unknown_values:
        raise DomainError(
            "INVALID_CONSTRAINT",
            "Dimension selector contains values not present in the fitted model",
            evidence={"unknown_values": unknown_values, "known_values": coords},
        )


def check_extrapolation_risk(
    model,
    allocation: dict[str, Any],
    planning_periods: int,
    threshold_ratio: float = 1.5,
) -> list[dict[str, Any]]:
    """Detect when allocated weekly spend materially exceeds historical observed support."""
    if not hasattr(model, "X") or planning_periods <= 0:
        return []

    channels = list(model.channel_columns)
    dims = model_dimensions(model)
    warnings = []

    if not dims:
        for ch in channels:
            if ch not in allocation or ch not in model.X.columns:
                continue
            hist_vals = pd.to_numeric(model.X[ch], errors="coerce").dropna().values
            if len(hist_vals) == 0:
                continue
            p95 = float(np.percentile(hist_vals, 95))
            weekly_spend = float(allocation[ch]) / float(planning_periods)
            if p95 > 0 and weekly_spend > threshold_ratio * p95:
                ratio = round(weekly_spend / p95, 2)
                warnings.append(
                    {
                        "code": "EXTRAPOLATION_RISK",
                        "channel": ch,
                        "recommended_weekly_spend": round(weekly_spend, 2),
                        "historical_p95": round(p95, 2),
                        "ratio_to_p95": ratio,
                        "message": (
                            f"Allocated weekly spend for {ch} ({round(weekly_spend, 2)}) is {ratio}x "
                            f"higher than historical 95th percentile ({round(p95, 2)})."
                        ),
                    }
                )
    else:
        for cell in allocation.get("cells", []):
            ch = cell.get("channel")
            cell_dims = cell.get("dimensions", {})
            amount = cell.get("amount", 0.0)
            if ch not in channels or ch not in model.X.columns:
                continue
            mask = np.ones(len(model.X), dtype=bool)
            for d_name, d_val in cell_dims.items():
                if d_name in model.X.columns:
                    mask = mask & (model.X[d_name] == d_val)
            hist_vals = pd.to_numeric(model.X.loc[mask, ch], errors="coerce").dropna().values
            if len(hist_vals) == 0:
                continue
            p95 = float(np.percentile(hist_vals, 95))
            weekly_spend = float(amount) / float(planning_periods)
            if p95 > 0 and weekly_spend > threshold_ratio * p95:
                ratio = round(weekly_spend / p95, 2)
                warnings.append(
                    {
                        "code": "EXTRAPOLATION_RISK",
                        "channel": ch,
                        "dimensions": cell_dims,
                        "recommended_weekly_spend": round(weekly_spend, 2),
                        "historical_p95": round(p95, 2),
                        "ratio_to_p95": ratio,
                        "message": (
                            f"Allocated weekly spend for {ch} in {cell_dims} ({round(weekly_spend, 2)}) "
                            f"is {ratio}x higher than historical 95th percentile ({round(p95, 2)})."
                        ),
                    }
                )

    return warnings
