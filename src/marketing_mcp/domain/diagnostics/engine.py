from __future__ import annotations

from typing import Any

import arviz as az
import numpy as np
import xarray as xr

from marketing_mcp.schemas.models import DiagnosticResult, Finding


def _get_group(idata: Any, name: str):
    try:
        return idata[name]
    except Exception:
        return getattr(idata, name, None)


def _posterior_predictive_metrics(idata: Any) -> tuple[dict[str, Any], list[Finding], list[dict]]:
    metrics: dict[str, Any] = {}
    warnings: list[Finding] = []
    failures: list[dict] = []
    predictive = _get_group(idata, "posterior_predictive")
    observed = _get_group(idata, "observed_data")
    if predictive is None or observed is None:
        warnings.append(
            Finding(
                severity="warning",
                code="PREDICTIVE_CHECK_UNAVAILABLE",
                message="Posterior predictive or observed data are unavailable",
                suggested_action="Persist posterior predictive samples and rerun diagnostics",
            )
        )
        return metrics, warnings, failures

    common = [name for name in observed.data_vars if name in predictive.data_vars]
    if not common:
        warnings.append(
            Finding(
                severity="warning",
                code="PREDICTIVE_CHECK_UNAVAILABLE",
                message="No common target variable exists between observed and posterior predictive data",
                suggested_action="Inspect the fitted artifact and posterior predictive configuration",
            )
        )
        return metrics, warnings, failures

    target = "y" if "y" in common else common[0]
    pred = predictive[target]
    obs = observed[target]
    sample_dims = [d for d in ("chain", "draw", "sample") if d in pred.dims]
    if not sample_dims:
        warnings.append(
            Finding(
                severity="warning",
                code="PREDICTIVE_CHECK_UNAVAILABLE",
                message="Posterior predictive target has no sampling dimensions",
                evidence={"dims": list(pred.dims)},
            )
        )
        return metrics, warnings, failures

    pred_mean = pred.mean(dim=sample_dims)
    lower = pred.quantile(0.03, dim=sample_dims)
    upper = pred.quantile(0.97, dim=sample_dims)
    obs, pred_mean, lower, upper = xr.align(obs, pred_mean, lower, upper, join="inner")

    obs_values = np.asarray(obs, dtype=float).reshape(-1)
    mean_values = np.asarray(pred_mean, dtype=float).reshape(-1)
    lower_values = np.asarray(lower, dtype=float).reshape(-1)
    upper_values = np.asarray(upper, dtype=float).reshape(-1)
    finite = (
        np.isfinite(obs_values)
        & np.isfinite(mean_values)
        & np.isfinite(lower_values)
        & np.isfinite(upper_values)
    )
    if not finite.any():
        warnings.append(
            Finding(
                severity="warning",
                code="PREDICTIVE_CHECK_UNAVAILABLE",
                message="Posterior predictive comparison contains no finite aligned values",
            )
        )
        return metrics, warnings, failures

    obs_values = obs_values[finite]
    mean_values = mean_values[finite]
    lower_values = lower_values[finite]
    upper_values = upper_values[finite]
    coverage = float(
        np.mean((obs_values >= lower_values) & (obs_values <= upper_values))
    )
    rmse = float(np.sqrt(np.mean((obs_values - mean_values) ** 2)))
    scale = float(np.std(obs_values))
    nrmse = float(rmse / scale) if scale > 0 else None
    metrics.update(
        {
            "posterior_predictive_target": target,
            "posterior_predictive_coverage_94": round(coverage, 4),
            "posterior_predictive_rmse": rmse,
            "posterior_predictive_nrmse": nrmse,
        }
    )

    if coverage < 0.50:
        failures.append(
            {
                "metric": "posterior_predictive_coverage_94",
                "observed": round(coverage, 4),
                "required": ">= 0.50",
            }
        )
    elif coverage < 0.80:
        warnings.append(
            Finding(
                severity="warning",
                code="LOW_POSTERIOR_PREDICTIVE_COVERAGE",
                message="Observed outcomes fall inside the 94% posterior predictive interval too infrequently",
                evidence={"coverage_94": round(coverage, 4)},
                suggested_action="Review model specification, controls, priors, and outlier periods",
            )
        )

    if nrmse is not None and nrmse > 1.0:
        warnings.append(
            Finding(
                severity="warning",
                code="HIGH_PREDICTIVE_ERROR",
                message="Posterior predictive mean has high normalized RMSE",
                evidence={"nrmse": round(nrmse, 4)},
                suggested_action="Review residual structure and model specification before high-stakes decisions",
            )
        )

    residual = obs - pred_mean
    if "date" in residual.dims:
        non_date_dims = [d for d in residual.dims if d != "date"]
        residual_by_date = residual.mean(dim=non_date_dims) if non_date_dims else residual
        r = np.asarray(residual_by_date, dtype=float).reshape(-1)
        r = r[np.isfinite(r)]
        if len(r) >= 3 and np.std(r[:-1]) > 0 and np.std(r[1:]) > 0:
            lag1 = float(np.corrcoef(r[:-1], r[1:])[0, 1])
            metrics["residual_lag1_autocorrelation"] = round(lag1, 4)
            if abs(lag1) >= 0.70:
                warnings.append(
                    Finding(
                        severity="warning",
                        code="RESIDUAL_AUTOCORRELATION",
                        message="Residuals show strong lag-1 autocorrelation",
                        evidence={"lag1": round(lag1, 4)},
                        suggested_action="Review omitted temporal structure, trend, seasonality, or carryover",
                    )
                )

    return metrics, warnings, failures


def diagnose_inferencedata(
    idata: Any, summary_override: dict[str, float] | None = None
) -> DiagnosticResult:
    failures: list[dict] = []
    warnings: list[Finding] = []
    metrics: dict[str, Any] = {}
    try:
        ss = _get_group(idata, "sample_stats")
        divergences = int(ss["diverging"].sum().item()) if "diverging" in ss else 0
    except Exception:
        divergences = 0
        warnings.append(
            Finding(
                severity="warning",
                code="SAMPLE_STATS_UNAVAILABLE",
                message="Sampler statistics were unavailable",
                suggested_action="Check saved InferenceData groups",
            )
        )
    metrics["divergences"] = divergences
    if divergences > 0:
        failures.append({"metric": "divergences", "observed": divergences, "required": 0})

    if summary_override:
        max_rhat = float(summary_override.get("r_hat", np.nan))
        min_ess = float(summary_override.get("ess_bulk", np.nan))
    else:
        try:
            posterior = _get_group(idata, "posterior")
            summary = az.summary(posterior, kind="diagnostics")
            max_rhat = float(summary["r_hat"].replace([np.inf, -np.inf], np.nan).max())
            min_ess = float(summary["ess_bulk"].replace([np.inf, -np.inf], np.nan).min())
        except Exception:
            max_rhat = float("nan")
            min_ess = float("nan")
            warnings.append(
                Finding(
                    severity="warning",
                    code="POSTERIOR_DIAGNOSTICS_UNAVAILABLE",
                    message="R-hat or ESS could not be summarized",
                    suggested_action="Inspect the posterior artifact",
                )
            )
    metrics["max_rhat"] = None if np.isnan(max_rhat) else round(max_rhat, 4)
    metrics["minimum_ess_bulk"] = None if np.isnan(min_ess) else round(min_ess, 1)
    if not np.isnan(max_rhat) and max_rhat > 1.01:
        failures.append(
            {"metric": "r_hat", "observed": round(max_rhat, 4), "required": "<= 1.01"}
        )
    if not np.isnan(min_ess) and min_ess < 400:
        warnings.append(
            Finding(
                severity="warning",
                code="LOW_EFFECTIVE_SAMPLE_SIZE",
                message="Some parameters have low bulk ESS",
                evidence={"minimum_ess_bulk": round(min_ess, 1)},
                suggested_action="Increase draws/tune or revise parameterization",
            )
        )

    predictive_metrics, predictive_warnings, predictive_failures = _posterior_predictive_metrics(
        idata
    )
    metrics.update(predictive_metrics)
    warnings.extend(predictive_warnings)
    failures.extend(predictive_failures)

    if failures:
        status = "rejected"
    elif warnings:
        status = "approved_with_caution"
    else:
        status = "approved"
    return DiagnosticResult(
        decision_status=status,
        diagnostics=metrics,
        warnings=warnings,
        failures=failures,
        decision_tools_enabled=status != "rejected",
    )
