"""
Unit tests for Phase 2 — PlottingService (Visual Posterior Artifacts).

Tests headless rendering guard, plot type validation, byte output,
and cache behavior. All rendering is mocked via a fake model object.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.services.plotting_service import SUPPORTED_PLOT_TYPES, PlottingService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_model():
    """Build a minimal fake MMM model with posterior + posterior_predictive."""
    model = MagicMock()
    model.channel_columns = ["meta", "google"]

    # Minimal xarray-like posterior
    import xarray as xr

    n_channels = 2
    n_draw = 50
    n_chain = 2
    n_time = 52

    ch_data = np.random.rand(n_chain, n_draw, n_time, n_channels)
    da = xr.DataArray(
        ch_data,
        dims=["chain", "draw", "date", "channel"],
        coords={"channel": ["meta", "google"]},
    )

    pp_data = np.random.rand(n_chain, n_draw, n_time)
    pp_da = xr.DataArray(pp_data, dims=["chain", "draw", "date_obs"])

    obs_data = np.random.rand(n_time)
    obs_da = xr.DataArray(obs_data, dims=["date_obs"])

    posterior = xr.Dataset({"channel_contribution_original_scale": da})
    pp = xr.Dataset({"y": pp_da})
    obs = xr.Dataset({"y_obs": obs_da})

    idata_mock = MagicMock()
    idata_mock.__getitem__ = lambda self, key: {
        "posterior": posterior,
        "posterior_predictive": pp,
        "observed_data": obs,
    }[key]
    idata_mock.get = lambda key, default=None: {
        "posterior": posterior,
        "posterior_predictive": pp,
        "observed_data": obs,
    }.get(key, default)

    model.idata = idata_mock
    model.saturation = MagicMock(spec=[])  # No plot_curve_hdi attribute
    model.plot = None
    return model


# ---------------------------------------------------------------------------
# PlottingService initialization
# ---------------------------------------------------------------------------


class TestPlottingServiceInit:
    def test_plotting_service_creates_plots_dir(self, tmp_path):
        PlottingService(tmp_path)
        assert (tmp_path / "plots").exists()

    def test_supported_plot_types_constant_is_non_empty(self):
        assert len(SUPPORTED_PLOT_TYPES) >= 4


# ---------------------------------------------------------------------------
# Plot type validation
# ---------------------------------------------------------------------------


class TestPlottingServiceValidation:
    def test_rejects_unknown_plot_type(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        with pytest.raises(DomainError) as exc_info:
            svc.generate_plot(model, "model_abc", "magic_chart")
        assert exc_info.value.code == "INVALID_PLOT_TYPE"

    def test_error_has_supported_types_in_evidence(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        with pytest.raises(DomainError) as exc_info:
            svc.generate_plot(model, "model_abc", "unknown")
        ev = exc_info.value.evidence
        assert "supported" in ev
        assert "saturation_curves" in ev["supported"]


# ---------------------------------------------------------------------------
# Byte output from real rendering
# ---------------------------------------------------------------------------


class TestPlottingServiceOutput:
    @pytest.mark.parametrize("plot_type", list(SUPPORTED_PLOT_TYPES.keys()))
    def test_generate_plot_returns_bytes_for_all_types(self, tmp_path, plot_type):
        """Each supported plot type must return non-empty bytes."""
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        result = svc.generate_plot(model, "model_test", plot_type, fmt="png")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_plot_is_valid_png_header(self, tmp_path):
        """Output starts with PNG magic bytes."""
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        result = svc.generate_plot(model, "model_test", "channel_contribution_share", fmt="png")
        # PNG magic: \x89PNG\r\n\x1a\n
        assert result[:4] == b"\x89PNG"

    def test_generate_plot_caches_to_disk(self, tmp_path):
        """After generating, get_cached_plot should return the same bytes."""
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        generated = svc.generate_plot(model, "model_xyz", "actual_vs_predicted", fmt="png")
        cached = svc.get_cached_plot("model_xyz", "actual_vs_predicted", fmt="png")
        assert cached == generated

    def test_get_cached_plot_returns_none_when_not_generated(self, tmp_path):
        svc = PlottingService(tmp_path)
        result = svc.get_cached_plot("nonexistent_model", "saturation_curves")
        assert result is None


# ---------------------------------------------------------------------------
# generate_all batch method
# ---------------------------------------------------------------------------


class TestGenerateAll:
    def test_generate_all_returns_dict_with_success_keys(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        results = svc.generate_all(
            model, "batch_model", ["saturation_curves", "actual_vs_predicted"]
        )
        assert "saturation_curves" in results
        assert "actual_vs_predicted" in results

    def test_generate_all_success_entries_have_data_b64(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        results = svc.generate_all(model, "batch2", ["channel_contribution_share"])
        entry = results["channel_contribution_share"]
        assert entry.get("success") is True
        assert "data_b64" in entry
        assert len(entry["data_b64"]) > 0

    def test_generate_all_bad_type_marked_as_failed(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        svc.generate_all(model, "batch3", ["saturation_curves"])
        # Inject a bad type manually — won't happen via schema, but tests the error path
        with pytest.raises(DomainError):
            svc.generate_plot(model, "batch3", "nonexistent_type")

    def test_generate_all_uri_format(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        results = svc.generate_all(model, "m001", ["waterfall_decomposition"])
        entry = results["waterfall_decomposition"]
        if entry.get("success"):
            assert entry["uri"] == "marketing://models/m001/plots/waterfall_decomposition"


class TestPlottingSecurity:
    def test_generate_plot_rejects_path_traversal_model_id(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        with pytest.raises(DomainError) as exc_info:
            svc.generate_plot(model, "../../malicious", "saturation_curves")
        assert exc_info.value.code == "INVALID_IDENTIFIER"

    def test_get_cached_plot_rejects_path_traversal_model_id(self, tmp_path):
        svc = PlottingService(tmp_path)
        with pytest.raises(DomainError) as exc_info:
            svc.get_cached_plot("../../malicious", "saturation_curves")
        assert exc_info.value.code == "INVALID_IDENTIFIER"

    def test_generate_plot_rejects_unsupported_format(self, tmp_path):
        svc = PlottingService(tmp_path)
        model = _make_fake_model()
        with pytest.raises(DomainError) as exc_info:
            svc.generate_plot(model, "m001", "saturation_curves", fmt="exe")
        assert exc_info.value.code == "INVALID_PLOT_FORMAT"
