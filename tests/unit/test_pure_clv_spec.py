"""Tests for UP-057: Pure CLV modeling core driven by canonical CLV specs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from marketing_mcp.scientific.clv import (
    CLVFitResult,
    build_clv_purchase_from_spec,
    build_clv_value_from_spec,
    fit_clv_purchase_from_spec,
    fit_clv_value_from_spec,
)


@pytest.fixture
def golden_purchase_df() -> pd.DataFrame:
    path = (
        Path(__file__).resolve().parents[3]
        / "migration/baselines/golden_datasets/pymc_harsh_clv_valid_fixture.csv"
    )
    if not path.exists():
        pytest.skip(f"Golden dataset not found at {path}")
    return pd.read_csv(path)


@pytest.fixture
def golden_value_df() -> pd.DataFrame:
    path = (
        Path(__file__).resolve().parents[3]
        / "migration/baselines/golden_datasets/pymc_harsh_clv_value_fixture.csv"
    )
    if not path.exists():
        pytest.skip(f"Golden dataset not found at {path}")
    return pd.read_csv(path)


def test_build_clv_purchase_from_spec():
    spec_dict = {
        "analysis_kind": "clv_purchase",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "datetime_column": "recency",
            "model_type": "bg_nbd",
        },
    }

    model = build_clv_purchase_from_spec(spec_dict)
    assert model.__class__.__name__ in ("BetaGeoModel", "BGModel")


def test_build_clv_from_canonical_pydantic_specs():
    try:
        from packages.contracts.python.models import (
            CLVPurchaseConfiguration,
            CLVPurchaseModelSpec,
            CLVValueConfiguration,
            CLVValueModelSpec,
        )
    except ImportError:
        pytest.skip("packages.contracts not available on PYTHONPATH")

    p_spec = CLVPurchaseModelSpec(
        dataset_version_id=uuid4(),
        configuration=CLVPurchaseConfiguration(
            customer_id_column="customer_id",
            datetime_column="recency",
            model_type="bg_nbd",
        ),
    )
    p_model = build_clv_purchase_from_spec(p_spec)
    assert p_model.__class__.__name__ in ("BetaGeoModel", "BGModel")

    v_spec = CLVValueModelSpec(
        dataset_version_id=uuid4(),
        configuration=CLVValueConfiguration(
            customer_id_column="customer_id",
            monetary_value_column="monetary_value",
            frequency_column="frequency",
        ),
    )
    v_model = build_clv_value_from_spec(v_spec)
    assert v_model.__class__.__name__ in ("GammaGammaModel", "GammaModel")


def test_build_clv_value_from_spec():
    spec_dict = {
        "analysis_kind": "clv_value",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "monetary_value_column": "monetary_value",
            "frequency_column": "frequency",
        },
    }

    model = build_clv_value_from_spec(spec_dict)
    assert model.__class__.__name__ in ("GammaGammaModel", "GammaModel")


def test_fit_clv_purchase_on_golden_dataset(golden_purchase_df):
    # Use first 25 customers for fast test execution
    slice_df = golden_purchase_df.iloc[:25].copy()

    spec_dict = {
        "analysis_kind": "clv_purchase",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "datetime_column": "recency",
            "model_type": "bg_nbd",
        },
    }

    result = fit_clv_purchase_from_spec(
        spec_dict,
        slice_df,
        draws=15,
        tune=15,
        chains=2,
    )

    assert isinstance(result, CLVFitResult)
    assert result.model is not None
    assert isinstance(result.parameter_estimates, dict)
    assert len(result.parameter_estimates) > 0
    # Common BG/NBD parameters: a, b, alpha, r
    assert any(k in result.parameter_estimates for k in ("a", "b", "alpha", "r"))


def test_fit_clv_value_on_golden_dataset(golden_value_df):
    # Filter customers with frequency > 0 and monetary_value > 0
    valid_df = golden_value_df[
        (golden_value_df["frequency"] > 0) & (golden_value_df["monetary_value"] > 0)
    ].iloc[:25].copy()

    spec_dict = {
        "analysis_kind": "clv_value",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "monetary_value_column": "monetary_value",
            "frequency_column": "frequency",
        },
    }

    result = fit_clv_value_from_spec(
        spec_dict,
        valid_df,
        draws=15,
        tune=15,
        chains=2,
    )

    assert isinstance(result, CLVFitResult)
    assert result.model is not None
    assert isinstance(result.parameter_estimates, dict)
    assert len(result.parameter_estimates) > 0
    # Common Gamma-Gamma parameters: p, q, v
    assert any(k in result.parameter_estimates for k in ("p", "q", "v"))
