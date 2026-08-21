from pathlib import Path

import pandas as pd

from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter


class FakeMMM:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def build_model(self, X, y):
        self.calls.append(("build_model", list(X.columns), y.name))

    def add_original_scale_contribution_variable(self, var):
        self.calls.append(("add_original_scale_contribution_variable", list(var)))

    def fit(self, X, y, **kwargs):
        self.calls.append(("fit", kwargs))

    def sample_posterior_predictive(self, X, **kwargs):
        self.calls.append(("sample_posterior_predictive", kwargs))

    def save(self, artifact):
        self.calls.append(("save", Path(artifact)))


class FakeAdstock:
    def __init__(self, l_max):
        self.l_max = l_max


class FakeSaturation:
    pass


def test_fit_builds_model_and_persists_original_scale_contributions(tmp_path):
    adapter = object.__new__(PyMCMarketingAdapter)
    adapter.MMM = FakeMMM
    adapter.GeometricAdstock = FakeAdstock
    adapter.LogisticSaturation = FakeSaturation

    df = pd.DataFrame(
        {
            "date": pd.date_range("2025-01-06", periods=8, freq="W-MON"),
            "meta": range(8),
            "revenue": range(100, 108),
        }
    )
    config = {
        "date_column": "date",
        "target_column": "revenue",
        "channel_columns": ["meta"],
        "control_columns": [],
        "dims": [],
        "adstock": {"l_max": 4},
        "yearly_seasonality": 2,
        "sampler": {
            "draws": 10,
            "tune": 10,
            "chains": 2,
            "target_accept": 0.9,
            "random_seed": 7,
        },
    }

    model = adapter.fit(df, config, tmp_path / "model.nc")

    assert model.calls[0][0] == "build_model"
    assert model.calls[1] == (
        "add_original_scale_contribution_variable",
        ["channel_contribution", "y"],
    )
    assert model.calls[2][0] == "fit"
    assert model.calls[3][0] == "sample_posterior_predictive"
    assert model.calls[4][0] == "save"
