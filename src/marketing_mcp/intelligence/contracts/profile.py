"""Structural profiling contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NumericDistribution(BaseModel):
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    q25: float | None = None
    q75: float | None = None
    iqr: float | None = None
    zeros_count: int = 0
    zeros_fraction: float = 0.0
    negatives_count: int = 0
    non_finite_count: int = 0
    outlier_candidate_count: int = 0


class CategoricalDistribution(BaseModel):
    cardinality: int = 0
    top_values: list[tuple[str, int]] = Field(default_factory=list)
    rare_values_count: int = 0


class MissingnessDetail(BaseModel):
    missing_count: int = 0
    missing_percentage: float = 0.0
    longest_contiguous_missing: int = 0
    systematic_pattern: bool = False


class ColumnProfile(BaseModel):
    name: str
    physical_dtype: str
    inferred_type: str
    row_count: int
    missingness: MissingnessDetail
    numeric: NumericDistribution | None = None
    categorical: CategoricalDistribution | None = None


class TemporalProfile(BaseModel):
    date_column: str | None = None
    frequency: str | None = None  # daily, weekly, monthly, irregular
    start_date: str | None = None
    end_date: str | None = None
    observed_periods: int = 0
    expected_periods: int = 0
    missing_periods: list[str] = Field(default_factory=list)
    duplicate_dates_count: int = 0
    is_continuous: bool = True
    granularity_days_median: float | None = None


class StructuralProfile(BaseModel):
    rows: int
    columns: int
    memory_bytes: int
    duplicate_rows: int
    temporal: TemporalProfile
    column_profiles: dict[str, ColumnProfile] = Field(default_factory=dict)
