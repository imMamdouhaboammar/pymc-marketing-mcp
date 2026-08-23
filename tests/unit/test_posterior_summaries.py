"""Unit tests for domain-level posterior summaries used by plotting (Task 6).

Contract:
1. Contributions are aggregated over time/panel dims PER POSTERIOR DRAW before
   median/HDI are computed across chain/draw.
2. Panel dimensions are preserved explicitly when requested.
3. The time dimension for predictions is identified by coordinate/name,
   never by positional shape[-1].
"""

from __future__ import annotations

import numpy as np
import pytest
import xarray as xr


def _idata(groups: dict[str, xr.Dataset]) -> xr.DataTree:
    """Build a DataTree-backed idata matching the pinned ArviZ 1.3 stack."""
    return xr.DataTree.from_dict({k: v for k, v in groups.items()})


def _contrib_idata() -> xr.DataTree:
    """3 draws x 4 dates; channel A per-draw totals are 4, 10, 30."""
    ch_a = np.array(
        [
            [[1.0, 1.0, 1.0, 1.0], [2.0, 2.0, 2.0, 2.0]],
            [[10.0, 0.0, 0.0, 0.0], [5.0, 5.0, 0.0, 0.0]],
            [[0.0, 0.0, 0.0, 30.0], [7.0, 7.0, 8.0, 8.0]],
        ]
    )  # dims: (draw, chain, date)
    ch_a = ch_a.transpose(1, 0, 2)  # (chain, draw, date)
    ch_b = np.full((2, 3, 4), 1.0)
    da = xr.DataArray(
        np.stack([ch_a, ch_b], axis=-1),
        dims=("chain", "draw", "date", "channel"),
        coords={
            "chain": [0, 1],
            "draw": [0, 1, 2],
            "date": list(range(4)),
            "channel": ["alpha", "beta"],
        },
    )
    return _idata({"posterior": xr.Dataset({"channel_contribution": da})})


class TestSummarizeChannelContributions:
    def test_aggregates_per_draw_before_median(self):
        from marketing_mcp.domain.posterior_summaries import (
            summarize_channel_contributions,
        )

        result = summarize_channel_contributions(_contrib_idata())

        # Channel alpha per-draw time-sums are 4, 10, 30 -> median 10.
        # A flatten-first implementation would report 0.5 (median of raw cells).
        assert float(result["median"].sel(channel="alpha")) == pytest.approx(10.0)
        # Channel beta is 1.0 everywhere: every draw sums to 4 over the horizon.
        assert float(result["median"].sel(channel="beta")) == pytest.approx(4.0)
        assert set(result.data_vars) == {"median", "lower", "upper"}
        assert list(result.coords["channel"].values.tolist()) == ["alpha", "beta"]

    def test_hdi_bounds_bracket_draw_level_totals(self):
        from marketing_mcp.domain.posterior_summaries import (
            summarize_channel_contributions,
        )

        result = summarize_channel_contributions(_contrib_idata())
        alpha_stats = result.sel(channel="alpha")
        lower_alpha = float(alpha_stats["lower"])
        median_alpha = float(alpha_stats["median"])
        upper_alpha = float(alpha_stats["upper"])
        # With 3 draws ({4, 10, 30}) and a 94% quantile interval, bounds are
        # interpolations strictly inside the empirical range.
        assert 4.0 <= lower_alpha < median_alpha < upper_alpha <= 30.0

    def test_panel_dimension_preserved_on_request(self):
        from marketing_mcp.domain.posterior_summaries import (
            summarize_channel_contributions,
        )

        da = _contrib_idata()["posterior"].dataset["channel_contribution"]
        # Give the two geos genuinely different per-draw totals.
        expanded = xr.concat(
            [da, da * 3.0], dim=xr.DataArray(["north", "south"], dims="geo")
        ).transpose("chain", "draw", "geo", "date", "channel")
        idata = _idata({"posterior": xr.Dataset({"channel_contribution": expanded})})

        result = summarize_channel_contributions(idata, group_dims=("geo",))

        assert "geo" in result.dims
        assert result.sizes["geo"] == 2
        north = result["median"].sel(geo="north", channel="alpha")
        south = result["median"].sel(geo="south", channel="alpha")
        assert float(north) != pytest.approx(float(south))


def _predictions_idata(time_last: bool) -> xr.DataTree:
    """Posterior predictive whose DATE dim is NOT last when time_last=False.

    Values are constant per period so quantiles equal that value, making the
    returned time series unambiguous regardless of reduction order.
    """
    period_values = np.array([10.0, 20.0, 30.0, 40.0])  # per date
    core = np.broadcast_to(period_values, (2, 3, 4)).copy()  # (chain, draw, date)
    if time_last:
        dims = ("chain", "draw", "date")
    else:
        core = core.transpose(2, 0, 1)  # (date, chain, draw) -> date FIRST
        dims = ("date", "chain", "draw")
    da = xr.DataArray(
        core,
        dims=dims,
        coords={"chain": [0, 1], "draw": [0, 1, 2], "date": list(range(4))},
    )
    obs = xr.DataArray(period_values, dims="date", coords={"date": list(range(4))})
    return _idata(
        {
            "posterior_predictive": xr.Dataset({"y": da}),
            "observed_data": xr.Dataset({"y": obs}),
        }
    )


class TestSummarizePredictions:
    def test_identifies_time_dim_by_name_not_position(self):
        from marketing_mcp.domain.posterior_summaries import summarize_predictions

        result = summarize_predictions(_predictions_idata(time_last=False))

        assert result.sizes["date"] == 4
        np.testing.assert_allclose(
            np.asarray(result["median"].values), [10.0, 20.0, 30.0, 40.0]
        )

    def test_works_when_time_is_last_dim(self):
        from marketing_mcp.domain.posterior_summaries import summarize_predictions

        result = summarize_predictions(_predictions_idata(time_last=True))
        np.testing.assert_allclose(
            np.asarray(result["median"].values), [10.0, 20.0, 30.0, 40.0]
        )

    def test_returns_lower_median_upper_keys(self):
        from marketing_mcp.domain.posterior_summaries import summarize_predictions

        result = summarize_predictions(_predictions_idata(time_last=True))
        assert set(result.data_vars) == {"median", "lower", "upper"}
