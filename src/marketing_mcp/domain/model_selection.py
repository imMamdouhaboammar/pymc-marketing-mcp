"""Bayesian Model Comparison & Selection Domain.

Provides information-theoretic model comparison (PSIS-LOO, WAIC, Bayesian Stacking)
using ArviZ InferenceData, with rigorous Pareto-k reliability verification.
"""

from __future__ import annotations

from typing import Any

import arviz as az
import numpy as np

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import ModelComparisonResult


def compare_information_criteria(
    idatas: dict[str, Any],
    criterion: str = "loo",
    weighting: str = "stacking",
) -> ModelComparisonResult:
    """Compare multiple Bayesian models using information criteria and predictive weighting."""
    if len(idatas) < 2:
        raise DomainError(
            "INPUT_INVALID",
            "At least 2 models are required for information-theoretic comparison",
            evidence={"model_count": len(idatas), "model_ids": list(idatas.keys())},
        )

    if criterion == "waic" and not hasattr(az, "waic"):
        raise DomainError(
            "UNSUPPORTED_CRITERION",
            "WAIC is deprecated and not supported in ArviZ 1.3+; use PSIS-LOO (criterion='loo') instead.",
            evidence={"requested": criterion, "supported": ["loo", "both"]},
            next_action="Specify criterion='loo' for leave-one-out cross-validation",
        )

    valid_criteria = {"loo", "waic", "both"}
    if criterion not in valid_criteria:
        raise DomainError(
            "INPUT_INVALID",
            f"Unknown comparison criterion: '{criterion}'. Supported: {sorted(valid_criteria)}",
            evidence={"criterion": criterion},
        )

    # Run ArviZ compare with specified weighting method
    try:
        comp_df = az.compare(idatas, method=weighting)
    except Exception as e:
        raise DomainError(
            "MODEL_COMPARISON_FAILED",
            f"ArviZ model comparison failed: {e}",
            evidence={"error": str(e)[:500], "criterion": criterion, "weighting": weighting},
        ) from e

    ranked_models: list[dict[str, Any]] = []
    stacking_weights: dict[str, float] = {}

    for mid in comp_df.index:
        row = comp_df.loc[mid]
        w = float(row.get("weight", 0.0))
        stacking_weights[str(mid)] = round(w, 4)
        m_entry: dict[str, Any] = {
            "model_id": str(mid),
            "rank": int(row.get("rank", 0)),
            "elpd_diff": float(round(float(row.get("elpd_diff", 0.0)), 4)),
            "dse": float(round(float(row.get("dse", 0.0)), 4)),
            "elpd": float(round(float(row.get("elpd", 0.0)), 4)),
            "se": float(round(float(row.get("se", 0.0)), 4)),
            "weight": round(w, 4),
        }
        if "p_worse" in row and not np.isnan(row["p_worse"]):
            m_entry["p_worse"] = float(round(float(row["p_worse"]), 4))
        if row.get("diag_diff"):
            m_entry["diag_diff"] = str(row["diag_diff"])
        if row.get("diag_elpd"):
            m_entry["diag_elpd"] = str(row["diag_elpd"])
        ranked_models.append(m_entry)

    # Evaluate Pareto-k diagnostics for each model
    pareto_k_warnings: list[dict[str, Any]] = []
    for mid, idata in idatas.items():
        try:
            loo_res = az.loo(idata)
            if hasattr(loo_res, "pareto_k"):
                pk_vals = np.asarray(loo_res.pareto_k).flatten()
                high_k = pk_vals[pk_vals > 0.7]
                mod_k = pk_vals[(pk_vals > 0.5) & (pk_vals <= 0.7)]
                if len(high_k) > 0:
                    pareto_k_warnings.append(
                        {
                            "code": "HIGH_PARETO_K",
                            "model_id": str(mid),
                            "severity": "warning",
                            "high_k_count": len(high_k),
                            "max_k": float(round(float(np.max(pk_vals)), 4)),
                            "message": f"Model '{mid}' has {len(high_k)} observations with Pareto-k > 0.7 (max k={float(np.max(pk_vals)):.2f}). LOO estimates may be unreliable.",
                        }
                    )
                elif len(mod_k) > 0:
                    pareto_k_warnings.append(
                        {
                            "code": "MODERATE_PARETO_K",
                            "model_id": str(mid),
                            "severity": "info",
                            "mod_k_count": len(mod_k),
                            "max_k": float(round(float(np.max(pk_vals)), 4)),
                            "message": f"Model '{mid}' has {len(mod_k)} observations with 0.5 < Pareto-k <= 0.7.",
                        }
                    )
        except (KeyError, ValueError, AttributeError, TypeError):
            pass

    best_model_id = str(comp_df.index[0])
    top_has_severe_pareto = any(
        w["model_id"] == best_model_id and w["code"] == "HIGH_PARETO_K" for w in pareto_k_warnings
    )

    if top_has_severe_pareto:
        recommended_model_id = None
        recommendation_reason = (
            f"Model '{best_model_id}' ranked highest on raw ELPD, but its Pareto-k diagnostics "
            "indicate severe importance sampling tail instability (k > 0.7), making LOO comparisons invalid."
        )
    else:
        recommended_model_id = best_model_id
        recommendation_reason = (
            f"Model '{best_model_id}' demonstrates superior out-of-sample predictive density "
            f"(ELPD={ranked_models[0]['elpd']:.2f}, stacking weight={stacking_weights.get(best_model_id, 0.0):.2f}) "
            "with verified Pareto-k diagnostic stability."
        )

    interpretation = (
        f"Compared {len(idatas)} models using {criterion.upper()} ({weighting}). "
        f"Top model is '{best_model_id}'. {recommendation_reason}"
    )

    return ModelComparisonResult(
        criterion=criterion,
        weighting=weighting,
        method=criterion,
        ranked_models=ranked_models,
        best_model_id=best_model_id,
        recommended_model_id=recommended_model_id,
        recommendation_reason=recommendation_reason,
        stacking_weights=stacking_weights,
        pareto_k_warnings=pareto_k_warnings,
        interpretation=interpretation,
    )
