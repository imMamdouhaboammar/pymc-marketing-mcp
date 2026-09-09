from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pandas as pd

from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.schemas.models import CalibrateMMMInput, LiftTestMeasurement
from marketing_mcp.services.modeling_service import ModelingService


def test_calibration_maps_only_declared_upstream_lift_fields_without_mutating_parent(tmp_path):
    now = datetime.now(UTC).isoformat()
    parent = {
        "model_id": "mmm_parent",
        "dataset_id": "dataset_1",
        "dataset_fingerprint": "fingerprint_1",
        "status": "completed",
        "artifact_path": str(tmp_path / "parent.nc"),
        "config": {"target_column": "sales", "sampler": {"draws": 100}},
        "package_provenance": {"pymc-marketing": "1.0.0"},
        "created_at": now,
        "updated_at": now,
        "validation_state": "approved",
        "diagnostics": {"diagnostics": {"max_rhat": 1.01}},
        "override_history": [{"reason": "parent-only evidence"}],
    }
    parent_before = deepcopy(parent)

    metadata = MagicMock()
    metadata.get_model.return_value = deepcopy(parent)
    artifacts = MagicMock()
    artifacts.put_file.return_value = ArtifactRef(
        uri="blob://namespace/checksum",
        sha256="a" * 64,
        size_bytes=10,
        version="v1",
        owner="local",
        tenant_id=None,
        content_type="application/x-netcdf",
    )
    datasets = MagicMock()
    datasets.load.return_value = pd.DataFrame({"sales": [1.0]})
    adapter = MagicMock()
    adapter.versions.return_value = {"pymc-marketing": "1.0.0"}
    service = ModelingService(metadata, artifacts, datasets, lambda: adapter)

    child = service.calibrate(
        CalibrateMMMInput(
            model_id="mmm_parent",
            lift_tests=[
                LiftTestMeasurement(
                    channel="meta",
                    geo="north",
                    x=500.0,
                    delta_x=100.0,
                    delta_y=80.0,
                    sigma=25.0,
                    description="Geo holdout",
                )
            ],
            sampler={"draws": 50, "tune": 50, "chains": 2, "random_seed": 7},
        )
    )

    lift_df = adapter.fit.call_args.kwargs["lift_df"]
    assert lift_df.to_dict(orient="records") == [
        {
            "channel": "meta",
            "geo": "north",
            "x": 500.0,
            "delta_x": 100.0,
            "delta_y": 80.0,
            "sigma": 25.0,
        }
    ]
    assert parent == parent_before
    assert all(
        call.args[0]["model_id"] == child.model_id for call in metadata.put_model.call_args_list
    )
    assert child.parent_model_id == "mmm_parent"
    assert child.lineage_stage == "calibrated"
    assert child.diagnostics is None
    assert child.validation_state == "not_diagnosed"
    assert child.override_history == []
