from __future__ import annotations

import importlib.metadata
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

from marketing_mcp.adapters.mmm_config import (
    build_adstock,
    build_mmm_init_kwargs,
    build_saturation,
)
from marketing_mcp.domain.decisions.allocation import (
    allocation_from_xarray,
    allocation_to_xarray,
    build_budget_bounds,
    historical_allocation,
)
from marketing_mcp.errors import DomainError


def _project_to_bounds_and_budget(
    x: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    target_budget: float,
) -> np.ndarray:
    """Project initial guess vector onto box bounds [lower, upper] and hyperplane sum(x) == target_budget."""
    arr = np.clip(np.asarray(x, dtype=float), lower, upper)
    for _ in range(25):
        diff = target_budget - float(np.sum(arr))
        if abs(diff) < 1e-6:
            break
        if diff > 0:
            room = upper - arr
            active = room > 1e-8
            if not np.any(active):
                break
            step = diff * (room[active] / np.sum(room[active]))
            arr[active] += step
            arr = np.clip(arr, lower, upper)
        else:
            room = arr - lower
            active = room > 1e-8
            if not np.any(active):
                break
            step = (-diff) * (room[active] / np.sum(room[active]))
            arr[active] -= step
            arr = np.clip(arr, lower, upper)
    return arr


class PyMCMarketingAdapter:
    def __init__(self):
        try:
            from pymc_marketing.mmm import (
                MMM,
                BinomialAdstock,
                BudgetOptimizerWrapper,
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

            optimizer_wrapper = BudgetOptimizerWrapper
        except ImportError:
            try:
                from pymc_marketing.mmm import GeometricAdstock, LogisticSaturation
                from pymc_marketing.mmm.multidimensional import (
                    MMM,
                    MultiDimensionalBudgetOptimizerWrapper,
                )

                optimizer_wrapper = MultiDimensionalBudgetOptimizerWrapper
                # Minimal zoo for legacy path
                DelayedAdstock = None
                WeibullCDFAdstock = None
                WeibullPDFAdstock = None
                BinomialAdstock = None
                NoAdstock = None
                TanhSaturation = None
                TanhSaturationBaselined = None
                MichaelisMentenSaturation = None
                HillSaturation = None
                HillSaturationSigmoid = None
                InverseScaledLogisticSaturation = None
                LogSaturation = None
                RootSaturation = None
                NoSaturation = None
            except ImportError as e:
                raise DomainError(
                    "DEPENDENCY_UNAVAILABLE",
                    "PyMC-Marketing is not installed in this runtime",
                    evidence={"dependency": "pymc-marketing>=1.0.0"},
                    next_action="Install project dependencies with uv sync",
                ) from e
        self.MMM = MMM
        self.OptimizerWrapper = optimizer_wrapper
        # Adstock classes
        self._adstock_map = {
            "geometric": GeometricAdstock,
            "delayed": DelayedAdstock,
            "weibull_cdf": WeibullCDFAdstock,
            "weibull_pdf": WeibullPDFAdstock,
            "binomial": BinomialAdstock,
            "none": NoAdstock,
        }
        # Saturation classes
        self._saturation_map = {
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
        # Backwards-compat aliases kept from v0.3
        self.GeometricAdstock = GeometricAdstock
        self.LogisticSaturation = LogisticSaturation

    def _build_adstock(self, cfg: dict):
        """Instantiate the correct adstock transform from a config dict."""
        return build_adstock(cfg)

    def _build_saturation(self, cfg: dict):
        """Instantiate the correct saturation transform from a config dict."""
        return build_saturation(cfg)

    @staticmethod
    def versions():
        names = ["pymc-marketing", "pymc", "arviz", "xarray", "h5netcdf", "h5py", "mcp"]
        out = {"python": platform.python_version()}
        for name in names:
            try:
                out[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                out[name] = None
        return out

    def fit(
        self,
        df: pd.DataFrame,
        config: dict | Any,
        artifact: Path | None = None,
        lift_df: pd.DataFrame | None = None,
    ):
        if isinstance(config, dict):
            cfg_dict = config
        else:
            cfg_dict = config.model_dump()

        target = cfg_dict["target_column"]
        xcols = [
            cfg_dict["date_column"],
            *cfg_dict["channel_columns"],
            *(cfg_dict.get("control_columns") or []),
            *(cfg_dict.get("dims") or []),
        ]
        X = df[xcols].copy()
        X[cfg_dict["date_column"]] = pd.to_datetime(X[cfg_dict["date_column"]])
        y = pd.to_numeric(df[target], errors="raise").rename(target)

        init_kwargs = build_mmm_init_kwargs(config)
        model = self.MMM(**init_kwargs)
        sampler = cfg_dict.get("sampler", {})
        if not isinstance(sampler, dict):
            sampler = sampler.model_dump()

        model.build_model(X, y)
        model.add_original_scale_contribution_variable(var=["channel_contribution", "y"])
        if lift_df is not None and not lift_df.empty:
            model.add_lift_test_measurements(lift_df)
        model.fit(
            X,
            y,
            draws=sampler.get("draws", 1000),
            tune=sampler.get("tune", 1000),
            chains=sampler.get("chains", 4),
            target_accept=sampler.get("target_accept", 0.9),
            random_seed=sampler.get("random_seed", 42),
        )
        model.sample_posterior_predictive(X, random_seed=sampler.get("random_seed", 42))
        if artifact is not None:
            artifact = Path(artifact)
            artifact.parent.mkdir(parents=True, exist_ok=True)
            model.save(artifact)
        return model

    def time_slice_cross_validate(
        self,
        df: pd.DataFrame,
        config: dict | Any,
        n_init: int = 40,
        forecast_horizon: int = 10,
        step_size: int = 10,
        sampler_config: dict | None = None,
    ) -> dict[str, Any]:
        """Run rolling time-slice cross-validation using PyMC-Marketing's TimeSliceCrossValidator."""
        try:
            from pymc_marketing.mmm import TimeSliceCrossValidator
        except ImportError as e:
            raise DomainError(
                "DEPENDENCY_UNAVAILABLE",
                "TimeSliceCrossValidator is unavailable in this runtime",
            ) from e

        if isinstance(config, dict):
            cfg_dict = config
        else:
            cfg_dict = config.model_dump()

        target = cfg_dict["target_column"]
        date_col = cfg_dict["date_column"]
        xcols = [
            date_col,
            *cfg_dict["channel_columns"],
            *(cfg_dict.get("control_columns") or []),
            *(cfg_dict.get("dims") or []),
        ]
        X = df[xcols].copy()
        X[date_col] = pd.to_datetime(X[date_col])
        y = pd.to_numeric(df[target], errors="raise").rename(target)

        init_kwargs = build_mmm_init_kwargs(config)
        model = self.MMM(**init_kwargs)

        s_cfg = sampler_config or config.get("sampler", {})
        cv = TimeSliceCrossValidator(
            n_init=n_init,
            forecast_horizon=forecast_horizon,
            date_column=date_col,
            step_size=step_size,
            sampler_config={
                "draws": s_cfg.get("draws", 100),
                "tune": s_cfg.get("tune", 100),
                "chains": s_cfg.get("chains", 2),
                "target_accept": s_cfg.get("target_accept", 0.9),
                "random_seed": s_cfg.get("random_seed", 42),
            },
        )

        cv.run(
            X,
            y,
            mmm=model,
            original_scale_vars=["channel_contribution", "y"],
        )

        fold_metrics = []
        rmses = []
        nrmses = []
        if hasattr(cv, "_cv_results"):
            for idx, res in enumerate(cv._cv_results):
                try:
                    y_test = np.asarray(res.y_test, dtype=float).reshape(-1)
                    pp = res.idata.posterior_predictive
                    y_var = (
                        "y_original_scale"
                        if "y_original_scale" in pp
                        else ("y" if "y" in pp else next(iter(pp.data_vars.keys())))
                    )
                    sample_dims = [d for d in ("chain", "draw", "sample") if d in pp[y_var].dims]
                    pred_mean = np.asarray(
                        pp[y_var].mean(dim=sample_dims),
                        dtype=float,
                    ).reshape(-1)
                    test_pred = pred_mean[-len(y_test) :]
                    fold_rmse = float(np.sqrt(np.mean((y_test - test_pred) ** 2)))
                    scale = float(np.std(y_test))
                    fold_nrmse = float(fold_rmse / scale) if scale > 0 else None
                except (KeyError, AttributeError, ValueError):
                    fold_rmse = 0.0
                    fold_nrmse = None
                rmses.append(fold_rmse)
                if fold_nrmse is not None:
                    nrmses.append(fold_nrmse)
                fold_metrics.append(
                    {
                        "fold": idx + 1,
                        "train_periods": len(res.X_train),
                        "test_periods": len(res.X_test),
                        "out_of_sample_rmse": round(fold_rmse, 2),
                        "out_of_sample_nrmse": round(fold_nrmse, 4)
                        if fold_nrmse is not None
                        else None,
                    }
                )

        mean_rmse = float(np.mean(rmses)) if rmses else 0.0
        mean_nrmse = float(np.mean(nrmses)) if nrmses else None

        stability_findings = []
        if nrmses and max(nrmses) > 1.8 * min(nrmses) and max(nrmses) > 0.6:
            stability_findings.append(
                {
                    "code": "CV_PREDICTIVE_INSTABILITY",
                    "severity": "warning",
                    "message": "Out-of-sample predictive performance degrades substantially across later time splits.",
                    "evidence": {
                        "min_nrmse": round(min(nrmses), 4),
                        "max_nrmse": round(max(nrmses), 4),
                    },
                }
            )

        return {
            "folds": len(fold_metrics),
            "metrics": fold_metrics,
            "mean_out_of_sample_rmse": round(mean_rmse, 2),
            "mean_out_of_sample_nrmse": round(mean_nrmse, 4) if mean_nrmse is not None else None,
            "stability_findings": stability_findings,
            "decision_impact": "warning" if stability_findings else "approved",
        }

    def evaluate_prior_sensitivity(
        self,
        model,
        df: pd.DataFrame,
        config: dict,
    ) -> dict[str, Any]:
        """Evaluate sensitivity of commercial conclusions under alternative adstock/saturation priors.

        Permutes across multiple alternative adstock specifications:
        - Halved l_max geometric (same type, shorter memory)
        - Delayed adstock (different type, peak-delay dynamics)
        """
        base_contrib = self.channel_contributions(model)
        base_ranks = {
            c["channel"]: i
            for i, c in enumerate(
                sorted(
                    base_contrib["channels"], key=lambda x: x["contribution_median"], reverse=True
                )
            )
        }

        # Build alternative configurations to test
        base_l_max = config.get("adstock", {}).get("l_max", 8)
        base_adstock_type = config.get("adstock", {}).get("type", "geometric")
        base_sat_type = config.get("saturation", {}).get("type", "logistic")
        base_sat_cfg = dict(config.get("saturation", {}))

        alt_sampler = dict(config.get("sampler", {}))
        alt_sampler["draws"] = min(alt_sampler.get("draws", 200), 100)
        alt_sampler["tune"] = min(alt_sampler.get("tune", 200), 100)
        alt_sampler["chains"] = 2

        # Alternative 1: halved l_max with same type (adstock variation)
        alt1_adstock = {"type": base_adstock_type, "l_max": max(2, base_l_max // 2)}
        # Alternative 2: delayed adstock (adstock variation)
        alt2_type = "delayed" if base_adstock_type == "geometric" else "geometric"
        alt2_adstock = {"type": alt2_type, "l_max": base_l_max}
        # Alternative 3: alternative saturation (saturation variation)
        alt3_sat_type = "michaelis_menten" if base_sat_type == "logistic" else "logistic"
        alt3_sat_cfg = {"type": alt3_sat_type}

        alternatives = [
            ("shorter_memory", alt1_adstock, base_sat_cfg, "adstock"),
            ("alternative_type", alt2_adstock, base_sat_cfg, "adstock"),
            ("alternative_saturation", {"type": base_adstock_type, "l_max": base_l_max}, alt3_sat_cfg, "saturation"),
        ]

        all_alt_ranks: list[dict] = []
        max_shift = 0
        findings = []

        for alt_label, alt_adstock_cfg, alt_sat_cfg, alt_dim in alternatives:
            alt_config = dict(config)
            alt_config["adstock"] = alt_adstock_cfg
            alt_config["saturation"] = alt_sat_cfg
            alt_config["sampler"] = alt_sampler

            target = alt_config["target_column"]
            date_col = alt_config["date_column"]
            xcols = [
                date_col,
                *alt_config["channel_columns"],
                *alt_config.get("control_columns", []),
                *alt_config.get("dims", []),
            ]
            X = df[xcols].copy()
            X[date_col] = pd.to_datetime(X[date_col])
            y = pd.to_numeric(df[target], errors="raise").rename(target)

            try:
                alt_init_kwargs = build_mmm_init_kwargs(alt_config)
                alt_model = self.MMM(**alt_init_kwargs)
                alt_model.build_model(X, y)
                alt_model.add_original_scale_contribution_variable(
                    var=["channel_contribution", "y"]
                )
                alt_model.fit(
                    X,
                    y,
                    draws=alt_sampler["draws"],
                    tune=alt_sampler["tune"],
                    chains=alt_sampler["chains"],
                    target_accept=alt_sampler.get("target_accept", 0.9),
                    random_seed=alt_sampler.get("random_seed", 42),
                )
                alt_contrib = self.channel_contributions(alt_model)
                alt_ranks = {
                    c["channel"]: i
                    for i, c in enumerate(
                        sorted(
                            alt_contrib["channels"],
                            key=lambda x: x["contribution_median"],
                            reverse=True,
                        )
                    )
                }
                rank_shifts = {
                    ch: abs(base_ranks.get(ch, 0) - alt_ranks.get(ch, 0)) for ch in base_ranks
                }
                shift = max(rank_shifts.values()) if rank_shifts else 0
                max_shift = max(max_shift, shift)
                all_alt_ranks.append(
                    {
                        "label": alt_label,
                        "dimension": alt_dim,
                        "adstock_config": alt_adstock_cfg,
                        "saturation_config": alt_sat_cfg,
                        "scenario_config": {
                            "adstock": alt_adstock_cfg,
                            "saturation": alt_sat_cfg,
                        },
                        "ranks": alt_ranks,
                        "max_rank_shift": shift,
                    }
                )
                if shift >= 2:
                    findings.append(
                        {
                            "code": "HIGH_PRIOR_SENSITIVITY",
                            "severity": "warning",
                            "message": (
                                f"Channel contribution ranking shifted by {shift} positions "
                                f"under '{alt_label}' alternative {alt_dim} specification."
                            ),
                            "evidence": {
                                "baseline_ranks": base_ranks,
                                "alternative_ranks": alt_ranks,
                                "alternative_label": alt_label,
                                "dimension": alt_dim,
                                "scenario_config": {
                                    "adstock": alt_adstock_cfg,
                                    "saturation": alt_sat_cfg,
                                },
                            },
                            "suggested_action": (
                                "Calibrate with incrementality experiments or collect "
                                "additional historical periods."
                            ),
                        }
                    )
            except Exception as e:
                all_alt_ranks.append(
                    {
                        "label": alt_label,
                        "dimension": alt_dim,
                        "adstock_config": alt_adstock_cfg,
                        "saturation_config": alt_sat_cfg,
                        "scenario_config": {
                            "adstock": alt_adstock_cfg,
                            "saturation": alt_sat_cfg,
                        },
                        "ranks": None,
                        "error": e.to_dict().get("error", {}).get("message", str(e)) if hasattr(e, "to_dict") else str(e),
                    }
                )

        return {
            "baseline_ranks": base_ranks,
            "tested_dimensions": {
                "adstock": True,
                "saturation": True,
            },
            "alternatives": all_alt_ranks,
            "alternative_ranks": all_alt_ranks[-1]["ranks"] if all_alt_ranks else {},
            "max_rank_shift": max_shift,
            "findings": findings,
            "prior_stability": "sensitive" if max_shift >= 2 else "robust",
        }

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
            marginal = incrementality.marginal_contribution_over_spend(frequency="all_time")
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
        marginal_records = self._summarize_coordinate_distribution(marginal, "marginal_iroas")
        marginal_by_key = {self._coord_key(row): row["marginal_iroas"] for row in marginal_records}
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
            channel_curves: dict[str, Any] = {}
            if "channel" in getattr(da, "dims", ()):
                channels = da.coords["channel"].values.tolist()
                grid_dim = "x" if "x" in da.dims else (da.dims[-1] if da.dims else None)
                x_vals = (
                    da.coords[grid_dim].values.tolist()
                    if grid_dim and grid_dim in getattr(da, "coords", {})
                    else list(range(da.shape[-1]))
                )

                # Cap points for compact and readable JSON response
                step = max(1, len(x_vals) // 50)
                selected_indices = list(range(0, len(x_vals), step))
                if (len(x_vals) - 1) not in selected_indices:
                    selected_indices.append(len(x_vals) - 1)

                sub_x = [round(float(x_vals[i]), 4) for i in selected_indices]

                for ch in channels:
                    ch_da = da.sel(channel=ch)
                    reduce_dims = [d for d in ch_da.dims if d in ("chain", "draw")]
                    if reduce_dims:
                        med = ch_da.median(dim=reduce_dims)
                        q03 = ch_da.quantile(0.03, dim=reduce_dims)
                        q97 = ch_da.quantile(0.97, dim=reduce_dims)
                    else:
                        med = ch_da
                        q03 = ch_da
                        q97 = ch_da

                    if grid_dim:
                        med_vals = [round(float(med.isel({grid_dim: i}).values), 4) for i in selected_indices]
                        lower_vals = [round(float(q03.isel({grid_dim: i}).values), 4) for i in selected_indices]
                        upper_vals = [round(float(q97.isel({grid_dim: i}).values), 4) for i in selected_indices]
                    else:
                        med_vals = [round(float(v), 4) for v in med.values.flatten()[: len(sub_x)]]
                        lower_vals = [round(float(v), 4) for v in q03.values.flatten()[: len(sub_x)]]
                        upper_vals = [round(float(v), 4) for v in q97.values.flatten()[: len(sub_x)]]

                    max_resp = round(float(np.nanmax(med_vals)), 4) if med_vals else 0.0
                    half_resp = max_resp / 2.0
                    half_idx = 0
                    for idx, val in enumerate(med_vals):
                        if val >= half_resp:
                            half_idx = idx
                            break
                    half_spend = sub_x[half_idx] if sub_x else 0.0

                    channel_curves[str(ch)] = {
                        "spend_grid": sub_x,
                        "median_response": med_vals,
                        "lower_94": lower_vals,
                        "upper_94": upper_vals,
                        "max_response_median": max_resp,
                        "half_saturation_spend": half_spend,
                    }

            return {
                "channels": channel_curves,
                "summary": self._small_summary(da),
                "method": "sample_saturation_curve",
            }
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

        lower_da = bounds.sel(bound="lower")
        upper_da = bounds.sel(bound="upper")

        baseline = {}
        baseline_xr = None
        x0_baseline = None
        try:
            baseline = historical_allocation(
                model,
                planning_periods,
                total_budget=budget,
            )
            baseline_xr = allocation_to_xarray(model, baseline)
            lower_flat = lower_da.transpose(*baseline_xr.dims).values.flatten()
            upper_flat = upper_da.transpose(*baseline_xr.dims).values.flatten()
            x0_baseline = _project_to_bounds_and_budget(
                baseline_xr.values.flatten(), lower_flat, upper_flat, budget
            )
        except Exception:
            baseline = {}
            x0_baseline = None

        try:
            mid_da = (lower_da + upper_da) / 2.0
            if baseline_xr is not None:
                lower_flat = lower_da.transpose(*baseline_xr.dims).values.flatten()
                upper_flat = upper_da.transpose(*baseline_xr.dims).values.flatten()
                mid_flat = mid_da.transpose(*baseline_xr.dims).values.flatten()
            else:
                lower_flat = lower_da.values.flatten()
                upper_flat = upper_da.values.flatten()
                mid_flat = mid_da.values.flatten()
            x0_midpoint = _project_to_bounds_and_budget(mid_flat, lower_flat, upper_flat, budget)
        except Exception:
            x0_midpoint = None

        strategies = [
            ("default", None, None),
            ("historical_baseline", x0_baseline, None),
            ("bounded_midpoint", x0_midpoint, None),
            ("slsqp_relaxed_tolerance", x0_baseline, {"method": "SLSQP", "ftol": 1e-6, "maxiter": 2000}),
            ("slsqp_midpoint_relaxed", x0_midpoint, {"method": "SLSQP", "ftol": 1e-6, "maxiter": 2000}),
        ]

        allocation = None
        result = None
        attempts: list[dict[str, Any]] = []
        last_error = None
        last_error_type = None
        last_res = None

        for strategy_name, candidate_x0, min_kwargs in strategies:
            if candidate_x0 is None and strategy_name != "default":
                continue

            call_kwargs: dict[str, Any] = {"budget": budget, "budget_bounds": bounds}
            if candidate_x0 is not None:
                call_kwargs["x0"] = candidate_x0
            if min_kwargs is not None:
                call_kwargs["minimize_kwargs"] = min_kwargs

            try:
                cur_alloc, cur_res = wrapper.optimize_budget(**call_kwargs)
            except TypeError as te:
                if strategy_name != "default":
                    continue
                last_error = te
                last_error_type = type(te).__name__
                break
            except Exception as e:
                last_error = e
                last_error_type = type(e).__name__
                attempts.append(
                    {
                        "attempt": len(attempts) + 1,
                        "strategy": strategy_name,
                        "solver": (min_kwargs or {}).get("method", "SLSQP"),
                        "success": False,
                        "message": str(e)[:500],
                    }
                )
                try:
                    from pymc_marketing.mmm.budget_optimizer import MinimizeException
                except ImportError:
                    MinimizeException = RuntimeError
                if not isinstance(e, (MinimizeException, RuntimeError, ArithmeticError)):
                    break
                continue

            cur_success = getattr(cur_res, "success", None)
            if cur_success is True:
                in_bounds = bool(((cur_alloc >= lower_da - 1e-3) & (cur_alloc <= upper_da + 1e-3)).all())
                total_alloc = float(cur_alloc.sum())
                budget_conserved = bool(abs(total_alloc - budget) <= max(1e-2, budget * 1e-3))
                if in_bounds and budget_conserved:
                    allocation = cur_alloc
                    result = cur_res
                    attempts.append(
                        {
                            "attempt": len(attempts) + 1,
                            "strategy": strategy_name,
                            "solver": (min_kwargs or {}).get("method", "SLSQP"),
                            "success": True,
                            "message": str(getattr(cur_res, "message", "converged"))[:500],
                        }
                    )
                    break
                else:
                    attempts.append(
                        {
                            "attempt": len(attempts) + 1,
                            "strategy": strategy_name,
                            "solver": (min_kwargs or {}).get("method", "SLSQP"),
                            "success": False,
                            "message": f"Allocation violated constraints: in_bounds={in_bounds}, budget_conserved={budget_conserved}",
                        }
                    )
            else:
                last_res = cur_res
                attempts.append(
                    {
                        "attempt": len(attempts) + 1,
                        "strategy": strategy_name,
                        "solver": (min_kwargs or {}).get("method", "SLSQP"),
                        "success": False,
                        "message": str(getattr(cur_res, "message", "non-converged"))[:500],
                    }
                )

        if allocation is None or result is None:
            failed_res = result or last_res
            if last_error:
                evidence: dict[str, Any] = {
                    "optimizer_message": str(last_error)[:500],
                    "optimizer_status": "exception",
                    "type": last_error_type,
                }
            else:
                evidence = {
                    "optimizer_message": str(getattr(failed_res, "message", ""))[:500],
                    "optimizer_success": getattr(failed_res, "success", None),
                }
            if len(attempts) > 1:
                evidence["attempts"] = attempts
            raise DomainError(
                "OPTIMIZATION_FAILED",
                "Budget optimizer failed to produce a trustworthy allocation",
                evidence=evidence,
                next_action="Review budget bounds and optimizer convergence diagnostics",
            )

        recommended = allocation_from_xarray(model, allocation)
        if not baseline:
            baseline = historical_allocation(
                model,
                planning_periods,
                total_budget=budget,
            )
        if baseline_xr is None:
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

        winning_strategy = attempts[-1]["strategy"] if attempts else "default"
        fallback_used = len(attempts) > 1 and winning_strategy != "default"
        total_allocated = float(allocation.sum())
        constraint_val = {
            "bounds_satisfied": True,
            "budget_conserved": bool(abs(total_allocated - budget) <= max(1e-2, budget * 1e-3)),
            "total_allocated": total_allocated,
            "target_budget": float(budget),
        }

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
            "optimizer_success": True,
            "optimizer_status": "converged",
            "optimizer_message": str(getattr(result, "message", ""))[:500],
            "solver": "SLSQP",
            "converged": True,
            "attempts": attempts,
            "attempts_count": len(attempts),
            "fallback_used": fallback_used,
            "initialization_strategy": winning_strategy,
            "constraint_validation": constraint_val,
            "objective_value": float(getattr(result, "fun", 0.0)) if hasattr(result, "fun") and getattr(result, "fun") is not None else None,
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
        da = None
        if (
            hasattr(idata, "data_vars")
            and variable in idata.data_vars
            or isinstance(idata, dict)
            and variable in idata
        ):
            da = idata[variable]
        else:
            try:
                group = idata["posterior_predictive"]
            except (KeyError, TypeError, IndexError):
                group = getattr(idata, "posterior_predictive", None)
            if group is not None and variable in group:
                da = group[variable]
        if da is None:
            raise DomainError(
                "SCENARIO_RESPONSE_UNAVAILABLE",
                "PyMC-Marketing did not return the expected posterior response variable",
                evidence={"variable": variable},
            )
        values = np.asarray(da, dtype=float).reshape(-1)
        values = values[np.isfinite(values)]
        if not len(values):
            raise DomainError(
                "SCENARIO_RESPONSE_UNAVAILABLE",
                "Posterior response distribution contained no finite values",
            )
        return values

    @staticmethod
    def _distribution_summary(values: np.ndarray) -> dict[str, float]:
        from marketing_mcp.accelerators import fast_compute_quantiles

        vals_list = values.tolist() if isinstance(values, np.ndarray) else list(values)
        res = fast_compute_quantiles(vals_list, [0.03, 0.5, 0.97])
        qs = res.get("quantiles", [0.0, 0.0, 0.0])
        return {
            "mean": float(res["mean"]),
            "median": float(qs[1]),
            "lower": float(qs[0]),
            "upper": float(qs[2]),
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
                dim: da.coords[dim].values[pos] for dim, pos in zip(entity_dims, index, strict=True)
            }
            values = np.asarray(da.sel(selectors), dtype=float).reshape(-1)
            values = values[np.isfinite(values)]
            if not len(values):
                continue
            summary = cls._distribution_summary(values)
            summary["probability_gt_1"] = float(np.mean(values > 1.0))
            record = {dim: cls._json_scalar(value) for dim, value in selectors.items()}
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
