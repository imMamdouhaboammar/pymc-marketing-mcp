"""
Unit tests for Phase 3 — Customer Lifetime Value (CLV) models & schemas.
"""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    CLVModelConfig,
    PredictCLVInput,
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

    def test_predict_clv_future_t_bounds(self):
        with pytest.raises(ValidationError):
            PredictCLVInput(model_id="clv_123", future_t=0)
        with pytest.raises(ValidationError):
            PredictCLVInput(model_id="clv_123", future_t=200)

    def test_predict_clv_top_n_bounds(self):
        with pytest.raises(ValidationError):
            PredictCLVInput(model_id="clv_123", top_n_customers=0)


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
