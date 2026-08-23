"""Statistical tests for PyMC-Marketing CLV models (BG/NBD, Gamma-Gamma, Shifted-Beta-Geometric).

Task 4 contract:
1. Real MCMC sampling on deterministic RFM fixtures without mocking PyMC-Marketing.
2. Separate verification of purchase model, value model, and combined CLV.
3. Verification that total_customers represents the complete population even when top_n is applied.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from marketing_mcp.schemas.models import (
    EstimateCLVInput,
    FitPurchaseModelInput,
    FitValueModelInput,
    PredictExpectedPurchasesInput,
    PredictExpectedSpendInput,
    PredictProbabilityAliveInput,
    SamplerConfig,
)
from marketing_mcp.services.clv_service import CLVService
from marketing_mcp.storage.metadata import SQLiteMetadataStore


@pytest.fixture
def rfm_dataset(tmp_path) -> tuple[str, Path]:
    df = pd.DataFrame(
        {
            "client_id": [f"c_{i}" for i in range(8)],
            "tx_count": [0, 2, 1, 4, 3, 0, 1, 5],
            "days_since_last": [0.0, 10.0, 5.0, 25.0, 15.0, 0.0, 8.0, 22.0],
            "total_days": [30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0],
            "avg_spend": [0.0, 25.0, 15.0, 50.0, 35.0, 0.0, 20.0, 45.0],
        }
    )
    data_path = tmp_path / "rfm.csv"
    df.to_csv(data_path, index=False)
    return "ds_rfm_001", data_path


@pytest.fixture
def contractual_dataset(tmp_path) -> tuple[str, Path]:
    df = pd.DataFrame(
        {
            "sub_id": [f"sub_{i}" for i in range(6)],
            "last_period": [2, 1, 3, 2, 1, 3],
            "max_period": [3, 3, 3, 3, 3, 3],
            "cohort_group": ["2025-01", "2025-01", "2025-01", "2025-02", "2025-02", "2025-02"],
        }
    )
    data_path = tmp_path / "contractual.csv"
    df.to_csv(data_path, index=False)
    return "ds_contractual_001", data_path


@pytest.fixture
def clv_service(tmp_path, rfm_dataset, contractual_dataset) -> CLVService:
    rfm_id, rfm_path = rfm_dataset
    sub_id, sub_path = contractual_dataset
    db_path = tmp_path / "metadata.db"
    store = SQLiteMetadataStore(db_path)
    store.put_dataset(
        {
            "dataset_id": rfm_id,
            "path": str(rfm_path),
            "fingerprint": "abc",
            "row_count": 8,
            "columns": ["client_id", "tx_count", "days_since_last", "total_days", "avg_spend"],
            "created_at": "2025-01-01T00:00:00",
        }
    )
    store.put_dataset(
        {
            "dataset_id": sub_id,
            "path": str(sub_path),
            "fingerprint": "xyz",
            "row_count": 6,
            "columns": ["sub_id", "last_period", "max_period", "cohort_group"],
            "created_at": "2025-01-01T00:00:00",
        }
    )
    return CLVService(metadata=store, artifact_dir=tmp_path / "artifacts")


@pytest.mark.statistical
def test_real_bg_nbd_and_gamma_gamma_workflow(clv_service):
    sampler = SamplerConfig(draws=50, tune=50, chains=2, target_accept=0.85, random_seed=42)

    # 1. Fit BG/NBD purchase model with custom column mappings
    p_rec = clv_service.fit_purchase_model(
        FitPurchaseModelInput(
            dataset_id="ds_rfm_001",
            customer_id_col="client_id",
            frequency_col="tx_count",
            recency_col="days_since_last",
            T_col="total_days",
            model_type="bg_nbd",
            sampler=sampler,
        )
    )
    assert p_rec.status == "completed"
    assert p_rec.model_type == "bg_nbd"

    # 2. Predict Expected Purchases
    ep_res = clv_service.predict_expected_purchases(
        PredictExpectedPurchasesInput(model_id=p_rec.model_id, future_t=12, top_n=3)
    )
    assert ep_res["total_customers"] == 8
    assert ep_res["returned_customers"] == 3
    assert len(ep_res["customers"]) == 3
    assert ep_res["summary"]["mean_expected_purchases"] > 0

    # 3. Predict Probability Alive
    pa_res = clv_service.predict_probability_alive(
        PredictProbabilityAliveInput(model_id=p_rec.model_id, top_n=4)
    )
    assert pa_res["total_customers"] == 8
    assert pa_res["returned_customers"] == 4
    assert len(pa_res["customers"]) == 4
    assert 0.0 <= pa_res["summary"]["mean_p_alive"] <= 1.0

    # 4. Fit Gamma-Gamma value model
    v_rec = clv_service.fit_value_model(
        FitValueModelInput(
            dataset_id="ds_rfm_001",
            customer_id_col="client_id",
            frequency_col="tx_count",
            monetary_value_col="avg_spend",
            model_type="gamma_gamma",
            sampler=sampler,
        )
    )
    assert v_rec.status == "completed"
    assert v_rec.model_type == "gamma_gamma"

    # 5. Predict Expected Spend
    es_res = clv_service.predict_expected_spend(
        PredictExpectedSpendInput(model_id=v_rec.model_id, top_n=2)
    )
    # Only customers with tx_count > 0 are modeled in Gamma-Gamma (6 repeat customers out of 8)
    assert es_res["total_customers"] == 6
    assert es_res["returned_customers"] == 2
    assert es_res["summary"]["mean_expected_spend"] > 0

    # 6. Combined CLV Estimation
    clv_res = clv_service.estimate_customer_lifetime_value(
        EstimateCLVInput(
            purchase_model_id=p_rec.model_id,
            value_model_id=v_rec.model_id,
            future_t=12,
            discount_rate=0.01,
            top_n=3,
        )
    )
    assert clv_res["total_customers"] == 6
    assert clv_res["returned_customers"] == 3
    assert clv_res["summary"]["mean_clv"] > 0
    assert clv_res["summary"]["total_portfolio_clv"] > 0


@pytest.mark.statistical
def test_real_shifted_beta_geo_workflow(clv_service):
    sampler = SamplerConfig(draws=50, tune=50, chains=2, target_accept=0.85, random_seed=42)

    # Fit Shifted Beta Geometric model with contractual discrete period data
    sbg_rec = clv_service.fit_purchase_model(
        FitPurchaseModelInput(
            dataset_id="ds_contractual_001",
            customer_id_col="sub_id",
            recency_col="last_period",
            T_col="max_period",
            cohort_col="cohort_group",
            model_type="shifted_beta_geo",
            sampler=sampler,
        )
    )
    assert sbg_rec.status == "completed"
    assert sbg_rec.model_type == "shifted_beta_geo"

    pa_res = clv_service.predict_probability_alive(
        PredictProbabilityAliveInput(model_id=sbg_rec.model_id, top_n=None)
    )
    assert pa_res["total_customers"] == 6
    assert len(pa_res["customers"]) == 6
    assert 0.0 <= pa_res["summary"]["mean_p_alive"] <= 1.0
