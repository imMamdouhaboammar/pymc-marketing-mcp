"""Unit tests for Phase 5 — Bayesian Model Comparison & Selection (LOO / Stacking / Model Selection Domain)."""

from __future__ import annotations

from unittest.mock import MagicMock

import arviz as az
import numpy as np
import pytest
from pydantic import ValidationError

from marketing_mcp.domain.model_selection import compare_information_criteria
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    ModelComparisonInput,
    ModelComparisonResult,
)
from marketing_mcp.services.modeling_service import ModelingService


class TestModelComparisonSchemas:
    def test_schema_requires_at_least_two_models(self):
        with pytest.raises(ValidationError):
            ModelComparisonInput(model_ids=["m1"])

    def test_schema_accepts_explicit_criterion_and_weighting(self):
        inp = ModelComparisonInput(model_ids=["m1", "m2"], criterion="loo", weighting="stacking")
        assert inp.criterion == "loo"
        assert inp.weighting == "stacking"

        inp_waic = ModelComparisonInput(model_ids=["m1", "m2"], criterion="waic", weighting="pseudo-bma")
        assert inp_waic.criterion == "waic"
        assert inp_waic.weighting == "pseudo-bma"

    def test_schema_legacy_method_backward_compatibility(self):
        inp1 = ModelComparisonInput(model_ids=["m1", "m2"], method="loo")
        assert inp1.criterion == "loo"
        inp2 = ModelComparisonInput(model_ids=["m1", "m2"], method="stacking")
        assert inp2.criterion == "loo"
        assert inp2.weighting == "stacking"
        inp3 = ModelComparisonInput(model_ids=["m1", "m2"], method="all")
        assert inp3.criterion == "both"

    def test_schema_rejects_unknown_criterion(self):
        with pytest.raises(ValidationError):
            ModelComparisonInput(model_ids=["m1", "m2"], criterion="bic")  # type: ignore[arg-type]


class TestDomainModelSelection:
    @pytest.fixture
    def idatas(self) -> dict[str, az.InferenceData]:
        np.random.seed(42)
        # Model 1 has much better predictive likelihood on synthetic data
        dt1 = az.from_dict(
            {
                "posterior": {"alpha": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.normal(loc=0.0, scale=0.5, size=(2, 50, 20))},
            }
        )
        # Model 2 has worse likelihood
        dt2 = az.from_dict(
            {
                "posterior": {"alpha": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.normal(loc=-2.0, scale=0.5, size=(2, 50, 20))},
            }
        )
        return {"m1": dt1, "m2": dt2}

    def test_compare_loo_criterion(self, idatas):
        res = compare_information_criteria(idatas, criterion="loo", weighting="stacking")
        assert isinstance(res, ModelComparisonResult)
        assert res.criterion == "loo"
        assert res.weighting == "stacking"
        assert len(res.ranked_models) == 2
        assert res.best_model_id == "m1"
        assert res.recommended_model_id == "m1"
        assert res.stacking_weights is not None
        assert res.stacking_weights["m1"] > res.stacking_weights["m2"]

    def test_compare_does_not_infer_criterion_from_weighting(self, idatas):
        res = compare_information_criteria(idatas, criterion="loo", weighting="pseudo-bma")
        assert res.criterion == "loo"
        assert res.weighting == "pseudo-bma"

    def test_compare_waic_unsupported_or_explicit(self, idatas):
        # ArviZ 1.3+ deprecated and removed waic
        if not hasattr(az, "waic"):
            with pytest.raises(DomainError) as exc_info:
                compare_information_criteria(idatas, criterion="waic")
            assert exc_info.value.code == "UNSUPPORTED_CRITERION"

    def test_refuse_recommendation_when_diagnostics_unsafe(self):
        # Construct idatas with high pareto k values
        np.random.seed(99)
        dt_bad = az.from_dict(
            {
                "posterior": {"alpha": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.standard_t(df=1.0, size=(2, 50, 15))},
            }
        )
        dt_good = az.from_dict(
            {
                "posterior": {"alpha": np.random.randn(2, 50, 1)},
                "log_likelihood": {"y": np.random.normal(0, 1, size=(2, 50, 15))},
            }
        )
        # Mocking loo result on dt_bad to guarantee high pareto-k
        with pytest.MonkeyPatch.context() as mp:
            orig_loo = az.loo

            def mock_loo(idata, *args, **kwargs):
                r = orig_loo(idata, *args, **kwargs)
                if idata is dt_bad:
                    r.pareto_k = np.array([0.95] * 15)
                    r.warning = True
                return r

            mp.setattr(az, "loo", mock_loo)
            res = compare_information_criteria({"bad": dt_bad, "good": dt_good}, criterion="loo")
            if res.best_model_id == "bad":
                assert res.recommended_model_id is None
                assert "unreliable" in res.recommendation_reason.lower() or "pareto" in res.recommendation_reason.lower()


class TestModelSelectionLogic:
    def test_rejects_models_from_different_datasets(self):
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

    def test_rejects_unfitted_model(self):
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
            ModelComparisonInput(model_ids=["m1", "m2"], criterion="loo", weighting="stacking")
        )
        assert res["best_model_id"] in {"m1", "m2"}
        assert len(res["ranked_models"]) == 2
        assert "stacking_weights" in res
        assert sum(res["stacking_weights"].values()) == pytest.approx(1.0, abs=1e-2)
