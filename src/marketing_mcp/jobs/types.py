"""Statistical job types and definitions."""

from __future__ import annotations

from enum import Enum


class StatisticalJobType(str, Enum):
    """Canonical statistical background job types."""

    MMM_FIT = "mmm.fit"
    MMM_CROSS_VALIDATE = "mmm.cross_validate"
    MMM_PRIOR_SENSITIVITY = "mmm.prior_sensitivity"
    MMM_CALIBRATE = "mmm.calibrate"
    MMM_BUDGET_OPTIMIZE = "mmm.budget_optimize"
    MMM_FLIGHTING_OPTIMIZE = "mmm.flighting_optimize"
    DATASET_TRANSFORM = "dataset.transform_ad_export"
    CLV_FIT_PURCHASE = "clv.fit_purchase"
    CLV_FIT_VALUE = "clv.fit_value"
    MODEL_COMPARE_EXPENSIVE = "model.compare_expensive"


__all__ = ["StatisticalJobType"]
