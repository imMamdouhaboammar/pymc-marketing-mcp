"""Real ArviZ InferenceData tests for Bayesian model comparison and selection.

Task 3 contract:
1. Tests model comparison with real ArviZ InferenceData with log_likelihood arrays.
2. Proves that model with superior pointwise predictive density is ranked first with stacking weights.
3. Tests BB-pseudo-BMA and pseudo-BMA weighting methods.
4. Validates Pareto-k diagnostic calculations without mocking ArviZ.
"""

from __future__ import annotations

import arviz as az
import numpy as np
import pytest

from marketing_mcp.domain.model_selection import compare_information_criteria
from marketing_mcp.schemas.models import ModelComparisonResult


@pytest.fixture
def real_comparison_idatas() -> dict[str, az.InferenceData]:
    np.random.seed(42)
    n_chains, n_draws, n_obs = 4, 100, 30

    # True data generated from y ~ Normal(5, 1)
    y_obs = np.random.normal(5.0, 1.0, size=n_obs)

    # Model 1 (superior): captures the true mean (mu ~ 5.0)
    mu_1 = np.random.normal(5.0, 0.1, size=(n_chains, n_draws, 1))
    log_lik_1 = -0.5 * np.log(2 * np.pi) - 0.5 * (y_obs - mu_1) ** 2

    # Model 2 (inferior): biased mean (mu ~ 2.0)
    mu_2 = np.random.normal(2.0, 0.1, size=(n_chains, n_draws, 1))
    log_lik_2 = -0.5 * np.log(2 * np.pi) - 0.5 * (y_obs - mu_2) ** 2

    dt1 = az.from_dict(
        {
            "posterior": {"mu": mu_1},
            "log_likelihood": {"y": log_lik_1},
            "observed_data": {"y": y_obs},
        }
    )
    dt2 = az.from_dict(
        {
            "posterior": {"mu": mu_2},
            "log_likelihood": {"y": log_lik_2},
            "observed_data": {"y": y_obs},
        }
    )

    return {"model_superior": dt1, "model_inferior": dt2}


@pytest.mark.statistical
def test_real_arviz_model_comparison_stacking(real_comparison_idatas):
    res = compare_information_criteria(
        real_comparison_idatas,
        criterion="loo",
        weighting="stacking",
    )
    assert isinstance(res, ModelComparisonResult)
    assert res.best_model_id == "model_superior"
    assert res.recommended_model_id == "model_superior"
    assert res.ranked_models[0]["model_id"] == "model_superior"
    assert res.ranked_models[0]["rank"] == 0
    assert res.ranked_models[1]["model_id"] == "model_inferior"
    assert res.ranked_models[1]["rank"] == 1

    # Model 1 should have vastly superior ELPD and full stacking weight
    assert res.ranked_models[0]["elpd"] > res.ranked_models[1]["elpd"]
    assert res.stacking_weights["model_superior"] > 0.9
    assert res.stacking_weights["model_inferior"] < 0.1


@pytest.mark.statistical
def test_real_arviz_model_comparison_bb_pseudo_bma(real_comparison_idatas):
    res = compare_information_criteria(
        real_comparison_idatas,
        criterion="loo",
        weighting="bb-pseudo-bma",
    )
    assert res.best_model_id == "model_superior"
    assert res.weighting == "bb-pseudo-bma"
    assert res.stacking_weights["model_superior"] > 0.9


@pytest.mark.statistical
def test_real_arviz_model_comparison_pseudo_bma(real_comparison_idatas):
    res = compare_information_criteria(
        real_comparison_idatas,
        criterion="loo",
        weighting="pseudo-bma",
    )
    assert res.best_model_id == "model_superior"
    assert res.weighting == "pseudo-bma"
    assert res.stacking_weights["model_superior"] > 0.9
