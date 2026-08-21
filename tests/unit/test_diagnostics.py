import numpy as np
import xarray as xr

from marketing_mcp.domain.diagnostics.engine import diagnose_inferencedata


class FakeIdata(dict):
    pass


def test_diagnostics_rejects_divergent_sampler():
    idata = FakeIdata()
    idata["sample_stats"] = xr.Dataset(
        {"diverging": (("chain", "draw"), np.ones((2, 20), dtype=int))}
    )
    idata["posterior"] = xr.Dataset(
        {"beta": (("chain", "draw"), np.random.default_rng(1).normal(size=(2, 20)))}
    )
    result = diagnose_inferencedata(idata, summary_override={"r_hat": 1.0, "ess_bulk": 1000})
    assert result.decision_status == "rejected"
    assert result.diagnostics["divergences"] == 40
