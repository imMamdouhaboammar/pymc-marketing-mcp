from __future__ import annotations

import numpy as np
import pytest

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter


def test_cv_failure_attribution_and_naive_skill_score():
    """Verify CV failure attribution, Seasonal Naive baseline comparison, and ranked hypotheses."""
    adapter = PyMCMarketingAdapter()

    # Simulate cross-validation results where MMM prediction is poor (NRMSE ~ 0.95)
    # while seasonal naive baseline is much better (NRMSE ~ 0.35)
    n_folds = 3
    y_tests = [
        np.array([100.0, 105.0, 102.0, 98.0, 101.0, 106.0, 103.0]),
        np.array([104.0, 108.0, 105.0, 101.0, 103.0, 109.0, 107.0]),
        np.array([108.0, 112.0, 110.0, 106.0, 108.0, 115.0, 112.0]),
    ]
    # Poor model predictions that drift wildly
    test_preds = [
        np.array([70.0, 75.0, 68.0, 65.0, 69.0, 72.0, 70.0]),
        np.array([140.0, 145.0, 142.0, 138.0, 141.0, 148.0, 145.0]),
        np.array([60.0, 62.0, 58.0, 55.0, 59.0, 63.0, 61.0]),
    ]
    y_trains = [
        np.array([95.0, 98.0, 96.0, 94.0, 97.0, 101.0, 99.0]),
        np.array([100.0, 105.0, 102.0, 98.0, 101.0, 106.0, 103.0]),
        np.array([104.0, 108.0, 105.0, 101.0, 103.0, 109.0, 107.0]),
    ]

    attribution = adapter.compute_cv_attribution(
        y_tests=y_tests,
        test_preds=test_preds,
        y_trains=y_trains,
    )

    assert "naive_baseline" in attribution
    naive = attribution["naive_baseline"]
    assert "mean_naive_nrmse" in naive
    assert "skill_score" in naive
    assert naive["skill_score"] < 0.0, "Poor MMM should have negative skill vs naive baseline"
    assert naive["skill_verdict"] == "inferior"

    assert "residual_diagnostics" in attribution
    res_diag = attribution["residual_diagnostics"]
    assert "mean_lag1_autocorr" in res_diag
    assert "autocorr_verdict" in res_diag

    assert "fold_stability" in attribution
    stab = attribution["fold_stability"]
    assert "fold_variance" in stab

    assert "ranked_hypotheses" in attribution
    hypotheses = attribution["ranked_hypotheses"]
    assert len(hypotheses) >= 1
    top_hyp = hypotheses[0]
    assert top_hyp["rank"] == 1
    assert top_hyp["confidence"] >= 0.80
    assert "naive baseline" in top_hyp["hypothesis"].lower() or "baseline" in top_hyp["hypothesis"].lower()
