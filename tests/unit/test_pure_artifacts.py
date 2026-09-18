"""Unit tests for pure visual artifact generation and canonical manifest creation (UP-059)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import numpy as np

from marketing_mcp.scientific.artifacts import (
    generate_mmm_artifacts,
)


class MockMMMModel:
    """Mock PyMC-Marketing MMM model with minimal posterior data for fast headless plotting."""

    def __init__(self, channel_columns: list[str] | None = None):
        self.channel_columns = channel_columns or ["tv", "radio", "social"]
        self.date_column = "date"
        self.target_column = "sales"
        self.plot = None
        self.idata = self._build_mock_idata()

    def _build_mock_idata(self):
        idata = MagicMock()
        chains = 2
        draws = 20
        n_ch = len(self.channel_columns)

        class MockDataArray:
            def __init__(self, values, dims):
                self.values = values
                self.dims = dims

            def mean(self, dim=None):
                return MockDataArray(np.mean(self.values, axis=0), ("channel",))

            def sel(self, **kwargs):
                return MockDataArray(self.values[:, :, 0], ("chain", "draw"))

        posterior = {
            "intercept": MockDataArray(np.random.normal(10, 1, (chains, draws)), ("chain", "draw")),
            "beta_channel": MockDataArray(np.random.uniform(0.1, 0.5, (chains, draws, n_ch)), ("chain", "draw", "channel")),
            "saturation_lam": MockDataArray(np.random.uniform(0.5, 1.5, (chains, draws, n_ch)), ("chain", "draw", "channel")),
        }
        idata.posterior = posterior
        return idata


def test_generate_mmm_artifacts_renders_all_plots_and_manifest(tmp_path: Path):
    """UP-059: generate_mmm_artifacts must render PNG plots and save manifest.json."""
    model = MockMMMModel()
    org_id = uuid4()
    project_id = uuid4()
    run_id = uuid4()
    output_dir = tmp_path / "run_artifacts"

    manifests = generate_mmm_artifacts(
        model=model,
        run_id=run_id,
        organization_id=org_id,
        project_id=project_id,
        output_dir=output_dir,
        fmt="png",
    )

    assert len(manifests) == 3
    kinds = {m.kind for m in manifests}
    assert kinds == {"waterfall_plot", "adstock_plot", "channel_contributions"}

    # Check files on disk
    manifest_file = output_dir / "manifest.json"
    assert manifest_file.exists()

    with open(manifest_file) as f:
        manifest_data = json.load(f)

    assert len(manifest_data) == 3

    for m in manifests:
        assert m.organization_id == org_id
        assert m.project_id == project_id
        assert m.run_id == run_id
        assert m.media_type == "image/png"
        assert m.size_bytes > 0
        assert len(m.sha256) == 64
        assert m.producer_service == "analytics-worker"

        # File check
        artifact_path = output_dir / f"{m.kind}.png"
        assert artifact_path.exists()
        assert artifact_path.stat().st_size == m.size_bytes

        # Check PNG magic bytes
        header = artifact_path.read_bytes()[:8]
        assert header == b"\x89PNG\r\n\x1a\n"


def test_generate_mmm_artifacts_svg_format(tmp_path: Path):
    """UP-059: generate_mmm_artifacts must render SVG format when requested."""
    model = MockMMMModel()
    org_id = uuid4()
    project_id = uuid4()
    run_id = uuid4()
    output_dir = tmp_path / "svg_artifacts"

    manifests = generate_mmm_artifacts(
        model=model,
        run_id=run_id,
        organization_id=org_id,
        project_id=project_id,
        output_dir=output_dir,
        fmt="svg",
    )

    assert len(manifests) == 3
    for m in manifests:
        assert m.media_type == "image/svg+xml"
        svg_file = output_dir / f"{m.kind}.svg"
        assert svg_file.exists()
        content = svg_file.read_text(encoding="utf-8")
        assert "<svg" in content


def test_generate_mmm_artifacts_custom_kinds_selection(tmp_path: Path):
    """UP-059: generate_mmm_artifacts must allow selecting specific artifact kinds."""
    model = MockMMMModel()
    org_id = uuid4()
    project_id = uuid4()
    run_id = uuid4()
    output_dir = tmp_path / "subset_artifacts"

    selected_kinds = ["waterfall_plot", "channel_contributions"]
    manifests = generate_mmm_artifacts(
        model=model,
        run_id=run_id,
        organization_id=org_id,
        project_id=project_id,
        output_dir=output_dir,
        kinds=selected_kinds,
    )

    assert len(manifests) == 2
    assert [m.kind for m in manifests] == selected_kinds
    assert (output_dir / "waterfall_plot.png").exists()
    assert (output_dir / "channel_contributions.png").exists()
    assert not (output_dir / "adstock_plot.png").exists()
