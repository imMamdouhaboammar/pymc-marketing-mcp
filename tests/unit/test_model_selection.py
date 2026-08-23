"""
Unit tests for Phase 5 — Bayesian Model Comparison & Selection (LOO / Stacking).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydantic import ValidationError

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    ModelComparisonInput,
)
from marketing_mcp.services.modeling_service import ModelingService


class TestModelComparisonSchemas:
    def test_schema_requires_at_least_two_models(self):
        with pytest.raises(ValidationError):
            ModelComparisonInput(model_ids=["m1"])

    def test_schema_accepts_valid_methods(self):
        inp = ModelComparisonInput(model_ids=["m1", "m2"], method="loo")
        assert inp.method == "loo"
        inp = ModelComparisonInput(model_ids=["m1", "m2"], method="stacking")
        assert inp.method == "stacking"

    def test_schema_rejects_unknown_method(self):
        with pytest.raises(ValidationError):
            ModelComparisonInput(model_ids=["m1", "m2"], method="bic")


class TestModelSelectionLogic:
    def test_rejects_models_from_different_datasets(self, tmp_path):
        metadata_mock = MagicMock()
        metadata_mock.get_model.side_effect = lambda mid: {
            "model_id": mid,
            "dataset_id": f"dataset_{mid}",
            "status": "completed",
            "validation_state": "approved",
            "config": {},
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        service = ModelingService(
            metadata=metadata_mock,
            artifacts=MagicMock(),
            datasets=MagicMock(),
            adapter_factory=MagicMock,
        )
        with pytest.raises(DomainError) as exc_info:
            service.select_best_model(ModelComparisonInput(model_ids=["m1", "m2"]))
        assert exc_info.value.code == "INCOMPATIBLE_MODELS"

    def test_rejects_unfitted_model(self, tmp_path):
        metadata_mock = MagicMock()
        metadata_mock.get_model.side_effect = lambda mid: {
            "model_id": mid,
            "dataset_id": "dataset_same",
            "status": "running" if mid == "m2" else "completed",
            "validation_state": "approved",
            "config": {},
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }
        service = ModelingService(
            metadata=metadata_mock,
            artifacts=MagicMock(),
            datasets=MagicMock(),
            adapter_factory=MagicMock,
        )
        with pytest.raises(DomainError) as exc_info:
            service.select_best_model(ModelComparisonInput(model_ids=["m1", "m2"]))
        assert exc_info.value.code == "MODEL_NOT_FITTED"

    def test_select_best_model_with_real_arviz_compare(self, tmp_path):
        import arviz as az

        dt1 = az.from_dict(
            {
                "posterior": {"a": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.randn(2, 50, 10)},
            }
        )
        dt2 = az.from_dict(
            {
                "posterior": {"a": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.randn(2, 50, 10)},
            }
        )

        mock_m1 = MagicMock()
        mock_m1.idata = dt1
        mock_m2 = MagicMock()
        mock_m2.idata = dt2

        metadata_mock = MagicMock()
        metadata_mock.get_model.side_effect = lambda mid: {
            "model_id": mid,
            "dataset_id": "dataset_common",
            "status": "completed",
            "validation_state": "approved",
            "config": {},
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        artifacts_mock = MagicMock()
        artifacts_mock.require.side_effect = lambda mid: tmp_path / f"{mid}.nc"

        adapter_mock = MagicMock()
        adapter_mock.load.side_effect = lambda p: mock_m1 if "m1" in str(p) else mock_m2

        service = ModelingService(
            metadata=metadata_mock,
            artifacts=artifacts_mock,
            datasets=MagicMock(),
            adapter_factory=lambda: adapter_mock,
        )

        res = service.select_best_model(
            ModelComparisonInput(model_ids=["m1", "m2"], method="stacking")
        )
        assert res["best_model_id"] in {"m1", "m2"}
        assert len(res["ranked_models"]) == 2
        assert "stacking_weights" in res
        assert sum(res["stacking_weights"].values()) == pytest.approx(1.0, abs=1e-2)
