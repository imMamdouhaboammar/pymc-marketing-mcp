from __future__ import annotations

import numpy as np
import xarray as xr

from marketing_mcp.domain.diagnostics.engine import diagnose_inferencedata


class FakeIdata(dict):
    pass


def _idata_with_ppc(observed, predictive):
    idata = FakeIdata()
    idata["sample_stats"] = xr.Dataset(
        {"diverging": (("chain", "draw"), np.zeros((2, 20), dtype=int))}
    )
    idata["posterior"] = xr.Dataset(
        {"beta": (("chain", "draw"), np.ones((2, 20)))}
    )
    idata["observed_data"] = xr.Dataset(
        {"y": (("date",), np.asarray(observed, dtype=float))}
    )
    idata["posterior_predictive"] = xr.Dataset(
        {
            "y": (
                ("chain", "draw", "date"),
                np.asarray(predictive, dtype=float),
            )
        }
    )
    return idata


def test_diagnostics_rejects_catastrophically_bad_posterior_predictive_coverage():
    observed = np.arange(10, dtype=float)
    predictive = np.full((2, 20, 10), 1000.0)
    result = diagnose_inferencedata(
        _idata_with_ppc(observed, predictive),
        summary_override={"r_hat": 1.0, "ess_bulk": 1000},
    )

    assert result.decision_status == "rejected"
    assert result.diagnostics["posterior_predictive_coverage_94"] == 0.0
    assert any(f["metric"] == "posterior_predictive_coverage_94" for f in result.failures)


def test_diagnostics_approves_sampler_but_cautions_when_predictive_check_missing():
    idata = FakeIdata()
    idata["sample_stats"] = xr.Dataset(
        {"diverging": (("chain", "draw"), np.zeros((2, 20), dtype=int))}
    )
    idata["posterior"] = xr.Dataset(
        {"beta": (("chain", "draw"), np.ones((2, 20)))}
    )
    result = diagnose_inferencedata(
        idata,
        summary_override={"r_hat": 1.0, "ess_bulk": 1000},
    )

    assert result.decision_status == "approved_with_caution"
    assert any(w.code == "PREDICTIVE_CHECK_UNAVAILABLE" for w in result.warnings)
