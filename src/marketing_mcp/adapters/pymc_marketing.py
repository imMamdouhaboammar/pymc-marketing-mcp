from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.metadata

import numpy as np
import pandas as pd
import xarray as xr

from marketing_mcp.domain.decisions.allocation import (
    allocation_from_xarray,
    allocation_to_xarray,
    build_budget_bounds,
    historical_allocation,
)
from marketing_mcp.errors import DomainError


class PyMCMarketingAdapter:
    def __init__(self):
        try:
            from pymc_marketing.mmm import GeometricAdstock, LogisticSaturation
            try:
                # PyMC-Marketing 0.19.x canonical multidimensional path.
                from pymc_marketing.mmm.multidimensional import (
                    MMM,
                    MultiDimensionalBudgetOptimizerWrapper,
                )
                optimizer_wrapper = MultiDimensionalBudgetOptimizerWrapper
            except ImportError:
                # Forward-compatible fallback for the post-0.19 rename.
                from pymc_marketing.mmm.mmm import MMM, BudgetOptimizerWrapper
                optimizer_wrapper = BudgetOptimizerWrapper
        except ImportError as e:
            raise DomainError(
                "DEPENDENCY_UNAVAILABLE",
                "PyMC-Marketing is not installed in this runtime",
                evidence={"dependency": "pymc-marketing>=0.19.4,<0.20"},
                next_action="Install project dependencies with uv sync",
            ) from e
        self.MMM = MMM
        self.GeometricAdstock = GeometricAdstock
        self.LogisticSaturation = LogisticSaturation
        self.OptimizerWrapper = optimizer_wrapper

    @staticmethod
    def versions():
        names = ["pymc-marketing", "pymc", "arviz", "mcp"]
        out = {}
        for name in names:
            try:
                out[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                out[name] = None
        return out

    def fit(self, df: pd.DataFrame, config: dict, artifact: Path):
        target = config["target_column"]
        xcols = [
            config["date_column"],
            *config["channel_columns"],
            *config.get("control_columns", []),
            *config.get("dims", []),
        ]
        X = df[xcols].copy()
        X[config["date_column"]] = pd.to_datetime(X[config["date_column"]])
        y = pd.to_numeric(df[target], errors="raise").rename(target)
        model = self.MMM(
            date_column=config["date_column"],
            channel_columns=config["channel_columns"],
            control_columns=config.get("control_columns") or None,
            target_column=target,
            adstock=self.GeometricAdstock(l_max=config["adstock"]["l_max"]),
            saturation=self.LogisticSaturation(),
            yearly_seasonality=config.get("yearly_seasonality"),
            dims=tuple(config.get("dims", [])),
        )
        sampler = config["sampler"]
        model.build_model(X, y)
        model.add_original_scale_contribution_variable(
            var=["channel_contribution", "y"]
        )
        model.fit(
            X,
            y,
            draws=sampler["draws"],
            tune=sampler["tune"],
            chains=sampler["chains"],
            target_accept=sampler["target_accept"],
            random_seed=sampler["random_seed"],
        )
        model.sample_posterior_predictive(X, random_seed=sampler["random_seed"])
        artifact.parent.mkdir(parents=True, exist_ok=True)
        model.save(artifact)
        return model

    def load(self, artifact: Path):
        return self.MMM.load(artifact)

    def channel_contributions(self, model) -> dict[str, Any]:
        posterior = model.idata["posterior"]
        candidates = ["channel_contribution_original_scale", "channel_contribution"]
        var = next((v for v in candidates if v in posterior), None)
        if not var:
            raise DomainError(
                "ANALYSIS_UNAVAILABLE",
                "No channel contribution variable exists in the fitted artifact",
                next_action="Refit with original-scale contribution deterministics enabled",
            )
        da = posterior[var]
        reduce = [d for d in da.dims if d not in {"channel"}]
        summed = (
            da.sum([d for d in reduce if d not in {"chain", "draw"}])
            if any(d not in {"chain", "draw", "channel"} for d in da.dims)
            else da
        )
        if "channel" not in summed.dims:
            raise DomainError(
                "ANALYSIS_UNAVAILABLE",
                "Contribution variable does not expose a channel dimension",
            )
        out = []
        for ch in summed.coords["channel"].values.tolist():
            vals = np.asarray(summed.sel(channel=ch)).reshape(-1)
            vals = vals[np.isfinite(vals)]
            if not len(vals):
                continue
            lower, median, upper = np.quantile(vals, [0.03, 0.5, 0.97])
            out.append(
                {
                    "channel": str(ch),
                    "contribution_median": float(median),
                    "credible_interval": {
                        "lower": float(lower),
                        "upper": float(upper),
                        "probability": 0.94,
                    },
                }
            )
        return {"variable": var, "channels": out}

    def incremental_roas(self, model) -> dict[str, Any]:
        """Return total and marginal iROAS from PyMC-Marketing's incrementality API."""
        try:
            incrementality = model.incrementality
            total = incrementality.contribution_over_spend(frequency="all_time")
            marginal = incrementality.marginal_contribution_over_spend(
                frequency="all_time"
            )
        except Exception as e:
            raise DomainError(
                "INCREMENTALITY_FAILED",
                "PyMC-Marketing incrementality analysis failed",
                evidence={"type": type(e).__name__, "message": str(e)[:500]},
                next_action=(
                    "Verify channel data are continuous float-valued media inputs and "
                    "the fitted artifact contains compatible incrementality data"
                ),
            ) from e

        total_records = self._summarize_coordinate_distribution(total, "total_iroas")
        marginal_records = self._summarize_coordinate_distribution(
            marginal, "marginal_iroas"
        )
        marginal_by_key = {
            self._coord_key(row): row["marginal_iroas"] for row in marginal_records
        }
        channels = []
        for row in total_records:
            key = self._coord_key(row)
            merged = dict(row)
            merged["marginal_iroas"] = marginal_by_key.get(key)
            channels.append(merged)
        return {
            "method": "pymc_marketing_incrementality",
            "frequency": "all_time",
            "channels": channels,
            "interpretation": {
                "total_iroas": "Incremental contribution per unit of historical spend",
                "marginal_iroas": (
                    "Incremental contribution per additional unit of spend at "
                    "the current operating point"
                ),
            },
        }

    def response_curves(self, model) -> dict[str, Any]:
        if hasattr(model, "sample_saturation_curve"):
            da = model.sample_saturation_curve()
            return {"summary": self._small_summary(da), "method": "sample_saturation_curve"}
        raise DomainError(
            "RESPONSE_CURVES_UNAVAILABLE", "No compatible response-curve API is available"
        )

    def simulate_budget(
        self,
        model,
        baseline_allocation: dict[str, Any],
        scenario_allocation: dict[str, Any],
        planning_periods: int,
    ) -> dict[str, Any]:
        wrapper, dates = self._budget_wrapper(model, planning_periods)
        baseline_xr = allocation_to_xarray(model, baseline_allocation)
        scenario_xr = allocation_to_xarray(model, scenario_allocation)

        baseline_samples = wrapper.sample_response_distribution(
            allocation_strategy=baseline_xr,
            noise_level=0.0,
            include_carryover=True,
        )
        scenario_samples = wrapper.sample_response_distribution(
            allocation_strategy=scenario_xr,
            noise_level=0.0,
            include_carryover=True,
        )
        baseline_values = self._response_values(baseline_samples)
        scenario_values = self._response_values(scenario_samples)
        return {
            "baseline_response": self._distribution_summary(baseline_values),
            "scenario_response": self._distribution_summary(scenario_values),
            "comparison": self._compare_distributions(
                baseline_values,
                scenario_values,
                alternative_label="scenario",
            ),
            "response_variable": "total_media_contribution_original_scale",
            "planning_start": str(dates.min().date()),
            "planning_end": str(dates.max().date()),
        }

    def optimize_budget(
        self,
        model,
        budget: float,
        planning_periods: int,
        constraints: dict,
        cell_constraints: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        wrapper, dates = self._budget_wrapper(model, planning_periods)
        bounds = build_budget_bounds(
            model,
            budget,
            constraints,
            cell_constraints or [],
        )
        allocation, result = wrapper.optimize_budget(
            budget=budget,
            budget_bounds=bounds,
        )
        recommended = allocation_from_xarray(model, allocation)
        baseline = historical_allocation(
            model,
            planning_periods,
            total_budget=budget,
        )
        baseline_xr = allocation_to_xarray(model, baseline)
        recommended_xr = allocation_to_xarray(model, recommended)
        baseline_samples = wrapper.sample_response_distribution(
            allocation_strategy=baseline_xr,
            noise_level=0.0,
            include_carryover=True,
        )
        recommended_samples = wrapper.sample_response_distribution(
            allocation_strategy=recommended_xr,
            noise_level=0.0,
            include_carryover=True,
        )
        baseline_values = self._response_values(baseline_samples)
        recommended_values = self._response_values(recommended_samples)
        return {
            "baseline_allocation": baseline,
            "recommended_allocation": recommended,
            "baseline_response": self._distribution_summary(baseline_values),
            "recommended_response": self._distribution_summary(recommended_values),
            "comparison": self._compare_distributions(
                baseline_values,
                recommended_values,
                alternative_label="recommended",
            ),
            "response_variable": "total_media_contribution_original_scale",
            "optimizer_success": bool(getattr(result, "success", True)),
            "optimizer_message": str(getattr(result, "message", ""))[:500],
            "planning_start": str(dates.min().date()),
            "planning_end": str(dates.max().date()),
        }

    def _budget_wrapper(self, model, planning_periods: int):
        date_col = model.date_column
        if not hasattr(model, "X"):
            raise DomainError(
                "BUDGET_DATA_UNAVAILABLE",
                "Historical fitted media data are unavailable in the model artifact",
            )
        dates_hist = pd.to_datetime(model.X[date_col]).sort_values().drop_duplicates()
        last = dates_hist.max()
        freq = pd.infer_freq(dates_hist) or "W-MON"
        dates = pd.date_range(last, periods=planning_periods + 1, freq=freq)[1:]
        wrapper = self.OptimizerWrapper(
            model=model,
            start_date=str(dates.min().date()),
            end_date=str(dates.max().date()),
        )
        return wrapper, dates

    @staticmethod
    def _response_values(idata) -> np.ndarray:
        variable = "total_media_contribution_original_scale"
        try:
            group = idata["posterior_predictive"]
        except Exception:
            group = getattr(idata, "posterior_predictive", None)
        if group is None or variable not in group:
            raise DomainError(
                "SCENARIO_RESPONSE_UNAVAILABLE",
                "PyMC-Marketing did not return the expected posterior response variable",
                evidence={"variable": variable},
            )
        values = np.asarray(group[variable], dtype=float).reshape(-1)
        values = values[np.isfinite(values)]
        if not len(values):
            raise DomainError(
                "SCENARIO_RESPONSE_UNAVAILABLE",
                "Posterior response distribution contained no finite values",
            )
        return values

    @staticmethod
    def _distribution_summary(values: np.ndarray) -> dict[str, float]:
        lower, median, upper = np.quantile(values, [0.03, 0.5, 0.97])
        return {
            "mean": float(np.mean(values)),
            "median": float(median),
            "lower": float(lower),
            "upper": float(upper),
            "interval_probability": 0.94,
        }

    @classmethod
    def _compare_distributions(
        cls, baseline: np.ndarray, alternative: np.ndarray, alternative_label: str
    ) -> dict[str, Any]:
        if baseline.shape != alternative.shape:
            raise DomainError(
                "SCENARIO_COMPARISON_FAILED",
                "Posterior response distributions are not aligned",
                evidence={
                    "baseline_samples": int(baseline.size),
                    "alternative_samples": int(alternative.size),
                },
            )
        delta = alternative - baseline
        summary = cls._distribution_summary(delta)
        baseline_median = float(np.median(baseline))
        summary.update(
            {
                f"probability_{alternative_label}_beats_baseline": float(np.mean(delta > 0)),
                "expected_change_pct": (
                    float(100.0 * np.median(delta) / baseline_median)
                    if baseline_median != 0
                    else None
                ),
            }
        )
        return summary

    @classmethod
    def _summarize_coordinate_distribution(
        cls, da: xr.DataArray, value_key: str
    ) -> list[dict[str, Any]]:
        sample_dims = [d for d in ("chain", "draw", "sample") if d in da.dims]
        entity_dims = [d for d in da.dims if d not in sample_dims]
        if "channel" not in entity_dims:
            raise DomainError(
                "INCREMENTALITY_UNAVAILABLE",
                "Incrementality output does not expose a channel dimension",
                evidence={"dims": list(da.dims)},
            )
        records: list[dict[str, Any]] = []
        shape = [da.sizes[d] for d in entity_dims]
        for index in np.ndindex(*shape):
            selectors = {
                dim: da.coords[dim].values[pos]
                for dim, pos in zip(entity_dims, index, strict=True)
            }
            values = np.asarray(da.sel(selectors), dtype=float).reshape(-1)
            values = values[np.isfinite(values)]
            if not len(values):
                continue
            summary = cls._distribution_summary(values)
            summary["probability_gt_1"] = float(np.mean(values > 1.0))
            record = {
                dim: cls._json_scalar(value) for dim, value in selectors.items()
            }
            record[value_key] = summary
            records.append(record)
        return records

    @staticmethod
    def _coord_key(row: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
        return tuple(
            sorted(
                (key, value)
                for key, value in row.items()
                if key not in {"total_iroas", "marginal_iroas"}
            )
        )

    @staticmethod
    def _json_scalar(value):
        return value.item() if hasattr(value, "item") else value

    def _small_summary(self, obj):
        if hasattr(obj, "to_array"):
            arr = np.asarray(obj.to_array())
        else:
            arr = np.asarray(obj)
        return {
            "shape": list(arr.shape),
            "median": float(np.nanmedian(arr)),
            "lower_94": float(np.nanquantile(arr, 0.03)),
            "upper_94": float(np.nanquantile(arr, 0.97)),
        }
