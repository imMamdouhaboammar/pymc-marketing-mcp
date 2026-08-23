"""Unit tests for Phase 3 — Customer Lifetime Value (CLV) models & schemas."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import ValidationError

from marketing_mcp.adapters.clv_adapter import CLVAdapter
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    CLVModelConfig,
    EstimateCLVInput,
    FitPurchaseModelInput,
    FitValueModelInput,
    PredictCLVInput,
    PredictExpectedPurchasesInput,
    PredictExpectedSpendInput,
    PredictProbabilityAliveInput,
)
from marketing_mcp.services.clv_service import CLVService


class TestCLVSchemas:
    def test_clv_config_requires_monetary_for_gamma_gamma(self):
        with pytest.raises(ValidationError) as exc_info:
            CLVModelConfig(
                model_type="gamma_gamma",
                customer_id_column="customer_id",
                frequency_column="frequency",
                recency_column="recency",
                T_column="T",
                monetary_value_column=None,
            )
        assert "monetary_value_column" in str(exc_info.value)

    def test_clv_config_accepts_bg_nbd_without_monetary(self):
        cfg = CLVModelConfig(
            model_type="bg_nbd",
            customer_id_column="customer_id",
            frequency_column="frequency",
            recency_column="recency",
            T_column="T",
        )
        assert cfg.model_type == "bg_nbd"
        assert cfg.monetary_value_column is None

    def test_fit_purchase_model_schema_defaults(self):
        inp = FitPurchaseModelInput(dataset_id="ds_1")
        assert inp.model_type == "bg_nbd"
        assert inp.customer_id_col == "customer_id"
        assert inp.frequency_col == "frequency"

    def test_fit_value_model_schema(self):
        inp = FitValueModelInput(dataset_id="ds_1", monetary_value_col="spend")
        assert inp.model_type == "gamma_gamma"
        assert inp.monetary_value_col == "spend"

    def test_predict_inputs_bounds(self):
        with pytest.raises(ValidationError):
            PredictExpectedPurchasesInput(model_id="m1", future_t=0)
        with pytest.raises(ValidationError):
            PredictExpectedPurchasesInput(model_id="m1", future_t=200)
        with pytest.raises(ValidationError):
            PredictProbabilityAliveInput(model_id="m1", top_n=0)
        with pytest.raises(ValidationError):
            PredictExpectedSpendInput(model_id="m1", top_n=0)
        with pytest.raises(ValidationError):
            PredictCLVInput(model_id="clv_123", top_n_customers=0)

    def test_estimate_clv_input_validation(self):
        inp = EstimateCLVInput(purchase_model_id="p1", value_model_id="v1", future_t=24, discount_rate=0.02)
        assert inp.purchase_model_id == "p1"
        assert inp.value_model_id == "v1"
        with pytest.raises(ValidationError):
            EstimateCLVInput(purchase_model_id="p1", value_model_id="v1", discount_rate=-0.1)


class TestCLVDataNormalization:
    def test_normalizes_custom_column_names_for_bg_nbd(self):
        adapter = CLVAdapter()
        df = pd.DataFrame(
            {
                "user_pk": ["u1", "u2"],
                "orders": [1, 3],
                "last_order_day": [10.0, 20.0],
                "tenure": [30.0, 30.0],
            }
        )
        norm = adapter.normalize_data(
            df,
            "bg_nbd",
            {
                "customer_id_col": "user_pk",
                "frequency_col": "orders",
                "recency_col": "last_order_day",
                "T_col": "tenure",
            },
        )
        assert list(norm.columns) == ["customer_id", "frequency", "recency", "T"]
        assert len(norm) == 2
        assert norm.iloc[0]["customer_id"] == "u1"

    def test_normalizes_and_filters_zero_frequency_for_gamma_gamma(self):
        adapter = CLVAdapter()
        df = pd.DataFrame(
            {
                "user_pk": ["u1", "u2", "u3"],
                "orders": [0, 2, 5],
                "avg_val": [0.0, 25.0, 50.0],
            }
        )
        norm = adapter.normalize_data(
            df,
            "gamma_gamma",
            {
                "customer_id_col": "user_pk",
                "frequency_col": "orders",
                "monetary_value_col": "avg_val",
            },
        )
        assert list(norm.columns) == ["customer_id", "frequency", "monetary_value"]
        # Customer u1 with 0 orders filtered out
        assert len(norm) == 2
        assert list(norm["customer_id"]) == ["u2", "u3"]

    def test_gamma_gamma_rejects_dataset_with_no_repeat_customers(self):
        adapter = CLVAdapter()
        df = pd.DataFrame(
            {
                "user_pk": ["u1", "u2"],
                "orders": [0, 0],
                "avg_val": [0.0, 0.0],
            }
        )
        with pytest.raises(DomainError) as exc_info:
            adapter.normalize_data(
                df,
                "gamma_gamma",
                {"customer_id_col": "user_pk", "frequency_col": "orders", "monetary_value_col": "avg_val"},
            )
        assert exc_info.value.code == "INVALID_RFM_DATA"


class TestCLVValidation:
    def test_clv_validation_rejects_negative_frequency(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        df = pd.DataFrame(
            {
                "customer_id": ["c1", "c2"],
                "frequency": [-1, 2],
                "recency": [5, 10],
                "T": [15, 20],
            }
        )
        cfg = CLVModelConfig(
            customer_id_column="customer_id",
            frequency_column="frequency",
            recency_column="recency",
            T_column="T",
        )
        with pytest.raises(DomainError) as exc_info:
            service._validate_rfm_data(df, cfg)
        assert exc_info.value.code == "INVALID_RFM_DATA"

    def test_clv_validation_rejects_duplicate_customer_ids(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        df = pd.DataFrame(
            {
                "customer_id": ["c1", "c1"],
                "frequency": [1, 2],
                "recency": [5, 10],
                "T": [15, 20],
            }
        )
        cfg = CLVModelConfig(
            customer_id_column="customer_id",
            frequency_column="frequency",
            recency_column="recency",
            T_column="T",
        )
        with pytest.raises(DomainError) as exc_info:
            service._validate_rfm_data(df, cfg)
        assert exc_info.value.code == "DUPLICATE_CUSTOMER_IDS"

    def test_clv_validation_rejects_missing_columns(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        df = pd.DataFrame(
            {
                "customer_id": ["c1", "c2"],
                "recency": [5, 10],
                "T": [15, 20],
            }
        )
        cfg = CLVModelConfig(
            customer_id_column="customer_id",
            frequency_column="frequency",
            recency_column="recency",
            T_column="T",
        )
        with pytest.raises(DomainError) as exc_info:
            service._validate_rfm_data(df, cfg)
        assert exc_info.value.code == "MISSING_RFM_COLUMNS"


class TestCLVServiceInvariants:
    def test_predict_expected_purchases_rejects_value_model(self, tmp_path):
        mock_meta = MagicMock()
        mock_meta.get_clv_model.return_value = {
            "model_id": "v1",
            "model_type": "gamma_gamma",
            "artifact_path": str(tmp_path / "v1.nc"),
        }
        service = CLVService(metadata=mock_meta, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.predict_expected_purchases(PredictExpectedPurchasesInput(model_id="v1"))
        assert exc_info.value.code == "INVALID_MODEL_TYPE"

    def test_predict_expected_spend_rejects_purchase_model(self, tmp_path):
        mock_meta = MagicMock()
        mock_meta.get_clv_model.return_value = {
            "model_id": "p1",
            "model_type": "bg_nbd",
            "artifact_path": str(tmp_path / "p1.nc"),
        }
        service = CLVService(metadata=mock_meta, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.predict_expected_spend(PredictExpectedSpendInput(model_id="p1"))
        assert exc_info.value.code == "INVALID_MODEL_TYPE"

    def test_estimate_clv_rejects_mismatched_models(self, tmp_path):
        mock_meta = MagicMock()
        mock_meta.get_clv_model.side_effect = lambda mid: {
            "model_id": mid,
            "model_type": "gamma_gamma" if mid == "v1" else "bg_nbd",
            "artifact_path": str(tmp_path / f"{mid}.nc"),
        }
        service = CLVService(metadata=mock_meta, artifact_dir=tmp_path)
        # Passing two value models
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="v1", value_model_id="v1")
            )
        assert exc_info.value.code == "INCOMPATIBLE_MODELS"


class TestCLVSecurityAndPersistence:
    def test_churn_risk_rejects_invalid_threshold_bounds(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.get_churn_risk_cohorts("clv_valid123", threshold=-0.5)
        assert exc_info.value.code == "INVALID_THRESHOLD"

        with pytest.raises(DomainError) as exc_info:
            service.get_churn_risk_cohorts("clv_valid123", threshold=1.5)
        assert exc_info.value.code == "INVALID_THRESHOLD"

    def test_churn_risk_rejects_path_traversal_model_id(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.get_churn_risk_cohorts("../../../etc/passwd", threshold=0.3)
        assert exc_info.value.code == "INVALID_IDENTIFIER"

    def test_predict_clv_rejects_path_traversal_model_id(self, tmp_path):
        service = CLVService(metadata=None, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.predict_clv(PredictCLVInput(model_id="../../secret"))
        assert exc_info.value.code == "INVALID_IDENTIFIER"

    def test_clv_metadata_persists_in_sqlite(self, tmp_path):
        from marketing_mcp.storage.metadata import SQLiteMetadataStore

        db = SQLiteMetadataStore(tmp_path / "metadata.db")
        db.put_clv_model(
            {
                "model_id": "clv_test_001",
                "model_type": "bg_nbd",
                "status": "completed",
                "dataset_id": "ds_1",
            }
        )
        retrieved = db.get_clv_model("clv_test_001")
        assert retrieved["model_id"] == "clv_test_001"
        assert retrieved["model_type"] == "bg_nbd"

        db.close()
        # Reopen to verify persistence
        db2 = SQLiteMetadataStore(tmp_path / "metadata.db")
        retrieved2 = db2.get_clv_model("clv_test_001")
        assert retrieved2["model_id"] == "clv_test_001"
        db2.close()
